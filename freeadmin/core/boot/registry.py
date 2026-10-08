# -*- coding: utf-8 -*-
"""
boot.registry

Utility helpers for bootstrapping the admin app.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Iterable, TYPE_CHECKING

from ..interface.app import AppConfig


LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover
    from ...contrib.adapters import BaseAdapter


class ModelModuleRegistry:
    """Track adapter and app-specific model modules for registration."""

    def __init__(self) -> None:
        self._configs: dict[str, AppConfig] = {}
        self._modules_by_label: dict[str, set[str]] = {}
        self._registered: dict[str, set[str]] = {}

    def register_base(self, app_label: str, modules: Iterable[str]) -> None:
        """Record adapter-provided ``modules`` for ``app_label``."""

        if not modules:
            return
        self._modules_by_label.setdefault(app_label, set()).update(modules)

    def register_config(self, config: AppConfig) -> None:
        """Store ``config`` and record its model modules."""

        key = config.import_path
        if key in self._configs:
            return
        self._configs[key] = config
        modules = tuple(config.get_models_modules())
        if not modules:
            return
        self._modules_by_label.setdefault(config.app_label, set()).update(modules)

    def iter_pending(self) -> Iterable[tuple[str, list[str]]]:
        """Yield app labels and modules that still require registration."""

        for app_label, modules in self._modules_by_label.items():
            registered = self._registered.get(app_label, set())
            pending = sorted(module for module in modules if module not in registered)
            if pending:
                yield app_label, pending

    def mark_registered(self, app_label: str, modules: Iterable[str]) -> None:
        """Mark ``modules`` for ``app_label`` as registered."""

        if not modules:
            return
        bucket = self._registered.setdefault(app_label, set())
        bucket.update(modules)

    def clear(self) -> None:
        """Reset stored configuration and registration metadata."""

        self._configs.clear()
        self._modules_by_label.clear()
        self._registered.clear()


class ModelRegistrar:
    """Coordinate model discovery and adapter-specific registration."""

    def __init__(self) -> None:
        self._registry = ModelModuleRegistry()
        self._imported_modules: set[str] = set()
        self._missing_modules: set[str] = set()

    def add_adapter(self, adapter: "BaseAdapter") -> None:
        """Collect adapter-provided modules and import them once."""

        base_modules = getattr(adapter, "model_modules", [])
        base_label = getattr(adapter, "system_app_label", "admin")
        available_modules: list[str] = []
        for dotted in base_modules:
            if dotted in self._missing_modules:
                continue
            if self._import_module(dotted):
                available_modules.append(dotted)
        self._registry.register_base(base_label, available_modules)
        if getattr(adapter, "name", None) == "tortoise":
            from tortoise import Tortoise

            # Tortoise 1.x exposes ``apps`` as ``None`` until a context is initialised.
            apps = Tortoise.apps
            if apps is not None and base_label in apps:
                self._registry.mark_registered(base_label, available_modules)

    def add_config(self, config: AppConfig) -> None:
        """Store ``config`` metadata and stage its models for registration."""

        self._registry.register_config(config)

    def sync_with_adapter(self, adapter: "BaseAdapter") -> None:
        """Register pending modules with ``adapter`` when required."""

        pending = list(self._registry.iter_pending())
        for app_label, modules in pending:
            available_modules: list[str] = []
            for dotted in modules:
                if dotted in self._missing_modules:
                    continue
                if self._import_module(dotted):
                    available_modules.append(dotted)

            if getattr(adapter, "name", None) == "tortoise":
                from tortoise import Tortoise

                if not available_modules:
                    LOGGER.warning(
                        "Skipping Tortoise model registration for '%s': no modules available",
                        app_label,
                    )
                    continue
                Tortoise.init_models(available_modules, app_label=app_label)
            if available_modules:
                self._registry.mark_registered(app_label, available_modules)

    def clear(self) -> None:
        """Reset cached import and registration metadata."""

        self._registry.clear()
        self._imported_modules.clear()
        self._missing_modules.clear()

    def _import_module(self, dotted_path: str) -> bool:
        if dotted_path in self._imported_modules:
            return True
        if dotted_path in self._missing_modules:
            return False
        try:
            import_module(dotted_path)
        except ModuleNotFoundError as exc:
            missing_name = exc.name or ""
            if missing_name and (
                missing_name == dotted_path or dotted_path.startswith(f"{missing_name}.")
            ):
                self._missing_modules.add(dotted_path)
                self._missing_modules.add(missing_name)
                LOGGER.debug("Model module '%s' is unavailable: %s", dotted_path, exc)
                return False
            raise
        self._imported_modules.add(dotted_path)
        return True


# The End

