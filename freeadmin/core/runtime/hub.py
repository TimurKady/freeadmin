# -*- coding: utf-8 -*-
"""
hub

Admin hub configuration and autodiscovery helpers.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional, Set, TYPE_CHECKING

from fastapi import FastAPI

from ..configuration.conf import (
    FreeAdminSettings,
    current_settings,
    register_settings_observer,
)
from ...contrib.adapters import BaseAdapter
from ..interface.app import AppConfig
from ..interface.site import AdminSite
from ..interface.discovery import DiscoveryService
from ..network.router import AdminRouter
from freeadmin.core.boot import admin as boot_admin

if TYPE_CHECKING:  # pragma: no cover
    from freeadmin.core.boot.manager import BootManager


class AdminHub:
    """Encapsulates admin site configuration and setup."""

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        title: str | None = None,
        *,
        settings: FreeAdminSettings | None = None,
        adapter: BaseAdapter | None = None,
        boot_manager: "BootManager | None" = None,
    ) -> None:
        """Initialize the admin site using the provided adapter."""

        self._settings = settings or current_settings()
        site_title = title or self._settings.admin_site_title
        selected_adapter = self._select_adapter(adapter=adapter, boot_manager=boot_manager)
        self.admin_site = AdminSite(
            selected_adapter, title=site_title, settings=self._settings
        )
        self.discovery = DiscoveryService()
        self._app_configs: Dict[str, AppConfig] = {}
        self._started_configs: Set[str] = set()
        self._router: AdminRouter | None = None
        register_settings_observer(self._handle_settings_update)

    def _select_adapter(
        self, *, adapter: BaseAdapter | None, boot_manager: "BootManager | None"
    ) -> BaseAdapter:
        """Choose the adapter from explicit input, boot manager, or default."""

        if boot_manager is not None:
            return boot_manager.adapter
        if adapter is not None:
            return adapter
        return boot_admin.adapter

    def autodiscover(self, packages: Iterable[str]) -> List[AppConfig]:
        """Discover application resources within ``packages``."""

        roots = list(packages)
        if not roots:
            return []
        configs = self.discovery.discover_all(roots)
        new_config_registered = False
        for config in configs:
            if config.import_path in self._app_configs:
                continue
            self._app_configs[config.import_path] = config
            new_config_registered = True
        if new_config_registered:
            self._invalidate_router_cache()
        if self.logger.isEnabledFor(logging.DEBUG):
            adapter = getattr(self.admin_site.adapter, "name", None)
            model_modules = list(getattr(self.admin_site.adapter, "model_modules", []))
            self.logger.debug(
                "AdminHub autodiscover complete",
                extra={
                    "adapter": adapter,
                    "model_modules": model_modules,
                    "packages": roots,
                    "discovered_app_configs": [config.import_path for config in configs],
                    "registered_app_configs": list(self._app_configs.keys()),
                    "model_admins": len(self.admin_site.model_reg),
                    "main_menu_items": len(
                        self.admin_site.menu_builder.build_main_menu(self.admin_site.registry)
                    ),
                    "user_menu_items": len(
                        self.admin_site.menu_builder.build_user_menu(self.admin_site.registry)
                    ),
                },
            )
        return configs

    def init_app(self, app: FastAPI, *, packages: Optional[List[str]] = None) -> None:
        """Convenience shortcut: autodiscover followed by mounting the admin."""
        if packages:
            self.autodiscover(packages)
        router = self._get_router()
        router.mount(app)

    async def start_app_configs(self) -> None:
        """Invoke startup hooks for discovered application configurations."""

        if self.logger.isEnabledFor(logging.DEBUG):
            adapter = getattr(self.admin_site.adapter, "name", None)
            model_modules = list(getattr(self.admin_site.adapter, "model_modules", []))
            self.logger.debug(
                "AdminHub app configs startup beginning",
                extra={
                    "adapter": adapter,
                    "model_modules": model_modules,
                    "pending_app_configs": [
                        path for path in self._app_configs.keys() if path not in self._started_configs
                    ],
                    "model_admins": len(self.admin_site.model_reg),
                    "main_menu_items": len(
                        self.admin_site.menu_builder.build_main_menu(self.admin_site.registry)
                    ),
                    "user_menu_items": len(
                        self.admin_site.menu_builder.build_user_menu(self.admin_site.registry)
                    ),
                },
            )
        for path, config in list(self._app_configs.items()):
            if path in self._started_configs:
                continue
            try:
                await config.ready()
            except Exception:  # pragma: no cover - runtime guard
                self.logger.exception(
                    "Application configuration %s failed during startup", path
                )
                continue
            self._started_configs.add(path)
        if self.logger.isEnabledFor(logging.DEBUG):
            adapter = getattr(self.admin_site.adapter, "name", None)
            model_modules = list(getattr(self.admin_site.adapter, "model_modules", []))
            self.logger.debug(
                "AdminHub app configs startup complete",
                extra={
                    "adapter": adapter,
                    "model_modules": model_modules,
                    "started_app_configs": list(self._started_configs),
                    "model_admins": len(self.admin_site.model_reg),
                    "main_menu_items": len(
                        self.admin_site.menu_builder.build_main_menu(self.admin_site.registry)
                    ),
                    "user_menu_items": len(
                        self.admin_site.menu_builder.build_user_menu(self.admin_site.registry)
                    ),
                },
            )

    def _handle_settings_update(self, settings: FreeAdminSettings) -> None:
        """Propagate new configuration to managed services."""
        self._settings = settings
        self.admin_site._settings = settings
        self._invalidate_router_cache()
        if hasattr(self.admin_site.cards, "apply_settings"):
            self.admin_site.cards.apply_settings(settings)
        else:  # pragma: no cover - compatibility branch
            self.admin_site.cards._settings = settings
            self.admin_site.cards.configure_event_cache(path=settings.event_cache_path)

    def _get_router(self) -> AdminRouter:
        """Return the cached admin router wrapper for mounting."""

        if self._router is None:
            self._router = AdminRouter(self.admin_site, settings=self._settings)
        return self._router

    def _invalidate_router_cache(self) -> None:
        """Drop cached router so future mounts rebuild discovery state."""

        router = self._router
        if router is None:
            return
        aggregator = getattr(router, "aggregator", None)
        invalidate = getattr(aggregator, "invalidate_admin_router", None)
        if callable(invalidate):
            invalidate()
        self._router = None


hub = AdminHub()
admin_site = hub.admin_site

# The End

