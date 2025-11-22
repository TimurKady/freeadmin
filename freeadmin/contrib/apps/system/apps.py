# -*- coding: utf-8 -*-
"""
apps

Application configuration for the built-in system app.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from importlib import import_module
from typing import ClassVar, TYPE_CHECKING

from .urls import SystemURLRegistrar

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from freeadmin.core.interface.site import AdminSite


class SystemAppConfig:
    """App configuration mirroring Django's :class:`~django.apps.AppConfig`."""

    name: ClassVar[str] = "freeadmin.contrib.apps.system"
    label: ClassVar[str] = "system"
    verbose_name: ClassVar[str] = "System Administration"

    def __init__(self) -> None:
        """Initialize registrars required by the system application."""

        self._urls = SystemURLRegistrar()
        self._admin_imported = False

    def ensure_admin_imported(self) -> None:
        """Import system admin configuration exactly once."""

        if self._admin_imported:
            return
        import_module("freeadmin.contrib.apps.system.admin")
        self._admin_imported = True

    @property
    def urls(self) -> SystemURLRegistrar:
        """Return the URL registrar responsible for wiring system routes."""

        return self._urls

    def ready(self, site: "AdminSite") -> None:
        """Register built-in URLs and menus against ``site``."""

        self.ensure_admin_imported()
        self._urls.register(site)


default_app_config = SystemAppConfig()


# The End
