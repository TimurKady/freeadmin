# -*- coding: utf-8 -*-
"""
config

Declarative ORM configuration helpers for FreeAdmin projects.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import importlib.util
import logging
import re
import warnings
from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping
from warnings import WarningMessage

from fastapi import FastAPI
from tortoise import Tortoise
from tortoise import exceptions as tortoise_exceptions

from ...contrib.adapters import registry
from ...utils.migration_errors import MigrationErrorClassifier


class ORMLifecycle:
    """Manage Tortoise ORM startup and shutdown hooks for FastAPI.

    The lifecycle delegates configuration concerns to :class:`ORMConfig` and
    orchestrates :func:`tortoise.Tortoise.init`/``close_connections`` calls
    using the stored declarative settings.
    """

    _logger = logging.getLogger(__name__)
    _migration_error_classifier = MigrationErrorClassifier()

    def __init__(self, *, config: ORMConfig) -> None:
        """Persist the configuration used to initialise the ORM."""

        self._config = config

    @property
    def adapter_name(self) -> str:
        """Return the name of the adapter that powers the ORM lifecycle."""

        return self._config.adapter_name

    @property
    def modules(self) -> Dict[str, List[str]]:
        """Return the modules mapping derived from the stored configuration.

        The mapping mirrors the ``apps`` section of the stored configuration and
        therefore includes FreeAdmin-specific ``admin`` and ``aerich`` entries
        when present.
        """

        return self._config.modules

    async def startup(self) -> None:
        """Initialise ORM connections when the FastAPI application boots.

        Modern configurations rely on the declarative dictionary stored in the
        :class:`ORMConfig` instance.  A compatibility shim keeps supporting
        legacy subclasses that expect the historic ``db_url``/``modules`` call
        signature.
        """

        try:
            await self._initialise_orm()
        except Exception as exc:
            if self._migration_error_classifier.is_missing_schema(exc):
                self._handle_startup_failure(exc)
                return
            raise

    async def _initialise_orm(self) -> None:
        """Attempt ORM initialisation honouring legacy call patterns."""

        default_showwarning = warnings.showwarning
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", RuntimeWarning)
            try:
                await Tortoise.init(config=self._config.config)
            except TypeError:  # pragma: no cover - compatibility shim
                await Tortoise.init(
                    db_url=self._config.connection_dsn,
                    modules=self.modules,
                )
        self._handle_startup_warnings(captured, default_showwarning)

    def _handle_startup_failure(self, error: BaseException) -> None:
        """Log a helpful error message when ORM initialisation fails."""

        self._logger.error(
            "Failed to initialise ORM: %s. Run your migrations before starting FreeAdmin.",
            error,
        )
        self._mark_migrations_required()

    def _mark_migrations_required(self) -> None:
        """Mark the global configuration as requiring pending migrations."""

        try:
            from ..interface.settings import system_config

            system_config.flag_migrations_required()
        except Exception:  # pragma: no cover - defensive fall-through
            self._logger.debug("Unable to flag migration requirement", exc_info=True)

    def _handle_startup_warnings(
        self,
        captured: Iterable[WarningMessage],
        showwarning: Callable[[Any, type, str, int, Any | None, Any | None], None],
    ) -> None:
        """Report ORM startup warnings emitted by the underlying ORM engine."""

        missing_models: set[str] = set()
        for warning in captured:
            message = str(warning.message)
            module_name = self._extract_missing_model_module(message)
            if module_name is None:
                showwarning(
                    warning.message,
                    warning.category,
                    warning.filename,
                    warning.lineno,
                    warning.file,
                    warning.line,
                )
                continue
            if module_name in missing_models:
                continue
            missing_models.add(module_name)
            self._logger.warning(
                "Module %s does not declare ORM models. Update the configuration or add model definitions.",
                module_name,
            )

    def _extract_missing_model_module(self, message: str) -> str | None:
        """Return the module name mentioned in a "has no models" warning message."""

        if "has no models" not in message.lower():
            return None
        match = re.search(r"Module\s+\"(?P<module>[^\"']+)\"\s+has\s+no\s+models", message)
        if match is None:
            return None
        return match.group("module")

    async def shutdown(self) -> None:
        """Tear down all ORM connections during FastAPI shutdown."""

        await Tortoise.close_connections()

    def bind(self, app: FastAPI) -> None:
        """Attach lifecycle hooks to a FastAPI application instance."""

        app.add_event_handler("startup", self.startup)
        app.add_event_handler("shutdown", self.shutdown)


class ORMConfig:
    """Declarative container for ORM connection and discovery settings.

    The class serves as the single source of truth for ORM metadata.  It can be
    instantiated with traditional ``dsn``/``modules`` arguments or via the
    :meth:`build` helper that accepts a full Tortoise ORM configuration mapping.
    """

    lifecycle_class = ORMLifecycle

    def __init__(
        self,
        *,
        adapter_name: str = "tortoise",
        dsn: str | None = None,
        modules: Mapping[str, Iterable[str]] | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        """Store adapter label, connection string, and module declarations."""

        self._adapter_name = adapter_name
        self._default_connection = "default"
        self._dsn = dsn or "sqlite://:memory:"
        self._project_modules = self._normalize_modules(modules or {})
        self._modules = self._merge_adapter_modules(self._project_modules)
        self._config = self._initialize_config(config)

    @property
    def adapter_name(self) -> str:
        """Return the name of the registered adapter powering the ORM."""

        return self._adapter_name

    @property
    def connection_dsn(self) -> str:
        """Return the database connection string used for ORM startup.

        When the configuration was created via :meth:`build`, the value is
        pulled from the default connection entry of the stored configuration
        mapping.  Legacy subclasses continue to receive the explicitly supplied
        ``dsn`` value.
        """

        connection = self._config["connections"].get(self._default_connection)
        if isinstance(connection, str):
            return connection
        if connection is None:
            return self._dsn
        return repr(connection)

    @property
    def modules(self) -> Dict[str, List[str]]:
        """Return the module mapping passed to :func:`Tortoise.init`.

        The mapping reflects the ``apps`` declaration inside the stored
        configuration, ensuring adapter-provided ``admin`` and ``aerich`` apps
        are always present.
        """

        return deepcopy(self._modules)

    @property
    def config(self) -> Dict[str, Any]:
        """Return the normalized Tortoise ORM configuration mapping.

        A deep copy is returned to keep the internal representation immutable
        from the caller's perspective.
        """

        return deepcopy(self._config)

    @property
    def default_connection_name(self) -> str:
        """Return the name of the default connection registered in config.

        The property is helpful when a project exposes multiple named
        connections and the caller needs to discover which one backs the admin
        services.
        """

        return self._default_connection

    def describe(self) -> dict[str, str]:
        """Return a human-readable summary of the ORM configuration.

        The summary reports the adapter identifier, the default connection name
        and the resolved DSN (when available) for logging and diagnostics.
        """

        description: dict[str, str] = {"adapter": self._adapter_name}
        if self._default_connection:
            description["default_connection"] = self._default_connection
        dsn = self.connection_dsn
        if dsn:
            description["dsn"] = dsn
        return description

    def create_lifecycle(self) -> ORMLifecycle:
        """Instantiate an ORM lifecycle manager for FastAPI integration."""

        return self.lifecycle_class(config=self)

    @classmethod
    def build(
        cls,
        *,
        adapter_name: str,
        config: Mapping[str, Any],
    ) -> "ORMConfig":
        """Construct an :class:`ORMConfig` instance from a Tortoise config.

        Args:
            adapter_name: Name of the registered admin adapter to use.
            config: Raw configuration dictionary supplied by an application.

        Returns:
            ORMConfig: Instance encapsulating the normalized configuration.

        The method validates the provided mapping, ensures built-in adapter
        modules are declared, and injects ``admin``/``aerich`` application
        entries that FreeAdmin relies on.  The resulting object can be passed
        directly to :class:`ORMLifecycle`.
        """

        return cls(adapter_name=adapter_name, config=config)

    def _normalize_modules(
        self, modules: Mapping[str, Iterable[str]]
    ) -> Dict[str, List[str]]:
        normalized: Dict[str, List[str]] = {}
        for label, values in modules.items():
            normalized[label] = [str(module) for module in values]
        return normalized

    def _merge_adapter_modules(
        self, modules: MutableMapping[str, List[str]]
    ) -> Dict[str, List[str]]:
        merged = deepcopy(modules)
        adapter = registry.get(self._adapter_name)
        adapter_modules = list(getattr(adapter, "model_modules", []))
        project_models = merged.setdefault("models", [])
        for module in adapter_modules:
            if module not in project_models:
                project_models.append(module)
        admin_modules = merged.setdefault("admin", [])
        for module in adapter_modules:
            if module not in admin_modules:
                admin_modules.append(module)
        aerich_modules = merged.setdefault("aerich", [])
        if self._has_aerich_support() and "aerich.models" not in aerich_modules:
            aerich_modules.append("aerich.models")
        return merged

    def _initialize_config(self, config: Mapping[str, Any] | None) -> Dict[str, Any]:
        if config is None:
            legacy_config = self._compose_legacy_config()
            self._modules = self._extract_modules(legacy_config)
            return legacy_config
        normalized = self._normalize_config_mapping(config)
        self._modules = self._extract_modules(normalized)
        return normalized

    def _compose_legacy_config(self) -> Dict[str, Any]:
        connections = {self._default_connection: self._dsn}
        apps = {
            label: {
                "models": list(modules),
                "default_connection": self._default_connection,
            }
            for label, modules in self._modules.items()
        }
        return {"connections": connections, "apps": apps}

    def _normalize_config_mapping(self, config: Mapping[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        connections = self._normalize_connections(config.get("connections"))
        normalized["connections"] = connections
        self._default_connection = self._determine_default_connection(connections)
        default_value = connections.get(self._default_connection)
        if isinstance(default_value, str):
            self._dsn = default_value
        apps = self._normalize_apps(config.get("apps"))
        normalized["apps"] = apps
        for key, value in config.items():
            if key in {"connections", "apps"}:
                continue
            normalized[key] = deepcopy(value)
        return normalized

    def _normalize_connections(
        self, connections: Mapping[str, Any] | None
    ) -> Dict[str, Any]:
        if not connections:
            return {self._default_connection: self._dsn}
        normalized: Dict[str, Any] = {}
        for label, value in connections.items():
            normalized[str(label)] = deepcopy(value)
        if self._default_connection not in normalized:
            first_key = next(iter(normalized))
            self._default_connection = first_key
        return normalized

    def _determine_default_connection(self, connections: Mapping[str, Any]) -> str:
        if self._default_connection in connections:
            return self._default_connection
        if connections:
            return next(iter(connections))
        return "default"

    def _normalize_apps(self, apps: Mapping[str, Any] | None) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for label, app_config in (apps or {}).items():
            normalized[str(label)] = self._normalize_app_config(app_config)
        self._ensure_admin_app(normalized)
        self._ensure_aerich_app(normalized)
        self._ensure_project_app_modules(normalized)
        return normalized

    def _normalize_app_config(self, app_config: Any) -> Dict[str, Any]:
        config: Dict[str, Any]
        if isinstance(app_config, Mapping):
            config = {str(key): deepcopy(value) for key, value in app_config.items()}
        else:
            config = {"models": [str(app_config)]}
        models = config.get("models", [])
        if isinstance(models, (str, bytes)):
            models = [str(models)]
        else:
            models = [str(module) for module in models]
        config["models"] = models
        default_connection = config.get("default_connection", self._default_connection)
        config["default_connection"] = str(default_connection)
        return config

    def _ensure_admin_app(self, apps: MutableMapping[str, Dict[str, Any]]) -> None:
        adapter = registry.get(self._adapter_name)
        adapter_modules = list(getattr(adapter, "model_modules", []))
        admin_app = apps.setdefault(
            "admin",
            {
                "models": [],
                "default_connection": self._default_connection,
            },
        )
        admin_modules = admin_app.setdefault("models", [])
        for module in adapter_modules:
            if module not in admin_modules:
                admin_modules.append(module)
        default_name = admin_app.get("default_connection", self._default_connection)
        admin_app["default_connection"] = str(default_name)

    def _ensure_aerich_app(self, apps: MutableMapping[str, Dict[str, Any]]) -> None:
        aerich_app = apps.setdefault(
            "aerich",
            {
                "models": ["aerich.models"],
                "default_connection": self._default_connection,
            },
        )
        models = aerich_app.setdefault("models", [])
        if self._has_aerich_support():
            if "aerich.models" not in models:
                models.append("aerich.models")
        else:
            models[:] = [module for module in models if module != "aerich.models"]
        default_name = aerich_app.get("default_connection", self._default_connection)
        aerich_app["default_connection"] = str(default_name)

    def _ensure_project_app_modules(
        self, apps: MutableMapping[str, Dict[str, Any]]
    ) -> None:
        adapter = registry.get(self._adapter_name)
        adapter_modules = list(getattr(adapter, "model_modules", []))
        project_app = apps.get("models")
        if project_app is None:
            return
        modules = project_app.setdefault("models", [])
        for module in adapter_modules:
            if module not in modules:
                modules.append(module)
        default_name = project_app.get("default_connection", self._default_connection)
        project_app["default_connection"] = str(default_name)

    def _extract_modules(self, config: Mapping[str, Any]) -> Dict[str, List[str]]:
        modules: Dict[str, List[str]] = {}
        for label, app_config in config.get("apps", {}).items():
            models = app_config.get("models", [])
            modules[str(label)] = [str(module) for module in models]
        return modules

    def _has_aerich_support(self) -> bool:
        try:
            spec = importlib.util.find_spec("aerich.models")
        except ModuleNotFoundError:
            return False
        return spec is not None


__all__ = ["ORMConfig", "ORMLifecycle"]

# The End

