# -*- coding: utf-8 -*-
"""
network_router

Coordinator for creating, caching, and mounting admin routers.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING
from weakref import WeakSet

from fastapi import APIRouter, FastAPI

from freeadmin.admin import AdminSite
from freeadmin.config import FreeAdminSettings, current_settings
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.interface.templates import TemplateService
from freeadmin.core.interface.templates import service as template_service_module
from freeadmin.core.interface.templates.rendering import TemplateRenderer

if TYPE_CHECKING:  # pragma: no cover - convenience for type checkers
    from freeadmin.core.interface.permissions.checker import PermissionChecker as PermissionCheckerType
    from freeadmin.core.runtime.provider import TemplateProvider


class RouterFoundation:
    """Provide shared helpers for router managers."""

    def __init__(
        self,
        *,
        settings: FreeAdminSettings | None = None,
        template_service: TemplateService | None = None,
    ) -> None:
        """Initialise configuration and template integration helpers."""

        self._settings = settings or current_settings()
        existing_renderer_service = getattr(TemplateRenderer, "_service", None)

        if template_service is not None:
            active_service = template_service
        elif existing_renderer_service is not None:
            active_service = existing_renderer_service
        else:
            active_service = TemplateService(settings=self._settings)

        self._template_service = active_service

        if template_service_module.DEFAULT_TEMPLATE_SERVICE is None:
            template_service_module.DEFAULT_TEMPLATE_SERVICE = active_service

        if template_service is not None or existing_renderer_service is None:
            TemplateRenderer.configure(active_service)

    @property
    def template_service(self) -> TemplateService:
        """Return the template service used for admin integration."""

        return self._template_service

    @property
    def provider(self) -> "TemplateProvider":
        """Return the template provider configured for admin integration."""

        return self._template_service.get_provider()

    def ensure_site_templates(self, site: AdminSite) -> None:
        """Attach template environment to ``site`` when missing."""

        self._template_service.ensure_site_templates(site)

    def mount_static_resources(self, app: FastAPI, prefix: str) -> None:
        """Expose admin static files, favicon, and media on ``app``."""

        self._template_service.mount_static_resources(app, prefix)


class AdminRouter:
    """Encapsulates mounting the admin interface onto an application."""

    def __init__(
        self,
        site: AdminSite,
        prefix: str | None = None,
        *,
        settings: FreeAdminSettings | None = None,
        template_service: TemplateService | None = None,
    ) -> None:
        """Create an aggregator-backed admin router."""

        self._aggregator = RouterAggregator(
            site=site,
            prefix=prefix,
            settings=settings,
            template_service=template_service,
        )

    def mount(self, app: FastAPI) -> None:
        """Mount the admin interface onto the given application."""

        self._aggregator.mount(app)

    @property
    def aggregator(self) -> "RouterAggregator":
        """Return the router aggregator powering this wrapper."""

        return self._aggregator


class RouterAggregator(RouterFoundation):
    """Coordinate creation and mounting of admin routers."""

    def __init__(
        self,
        site: AdminSite,
        prefix: str | None = None,
        *,
        settings: FreeAdminSettings | None = None,
        additional_routers: Iterable[tuple[APIRouter, str | None]] | None = None,
        template_service: TemplateService | None = None,
    ) -> None:
        """Initialise the aggregator with the admin site and base settings."""

        super().__init__(settings=settings, template_service=template_service)
        self.site = site
        default_prefix = system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, self._settings.admin_path
        )
        self._prefix = (prefix or default_prefix).rstrip("/")
        self._admin_router: APIRouter | None = None
        self._mounted_apps: WeakSet[FastAPI] = WeakSet()
        self._additional_routers: list[tuple[APIRouter, str | None]] = list(
            additional_routers or ()
        )

    @property
    def prefix(self) -> str:
        """Return the current prefix used for mounting the admin router."""

        return self._prefix

    def create_admin_router(self) -> APIRouter:
        """Instantiate the FastAPI router for the admin site."""

        return self.site.build_router(self.provider)

    def get_admin_router(self) -> APIRouter:
        """Return the cached admin router, creating it when necessary."""

        if self._admin_router is None:
            self._admin_router = self.create_admin_router()
        return self._admin_router

    def invalidate_admin_router(self) -> None:
        """Drop the cached admin router so it rebuilds on next access."""

        self._admin_router = None

    def mount(self, app: FastAPI, prefix: str | None = None) -> None:
        """Mount the admin router and any configured extras onto the app."""

        self._prefix = (prefix or self._prefix).rstrip("/")
        self.ensure_site_templates(self.site)
        app.state.admin_site = self.site
        if app in self._mounted_apps:
            return

        router = self.get_admin_router()
        app.include_router(router, prefix=self._prefix)
        self.mount_static_resources(app, self._prefix)
        self.register_additional_routers(app)
        self._mounted_apps.add(app)

    def register_additional_routers(self, app: FastAPI) -> None:
        """Register optional routers configured for the aggregator."""

        for router, router_prefix in self._iter_additional_routers():
            app.include_router(router, prefix=router_prefix or "")
        for router in self.get_public_routers():
            app.include_router(router, prefix="")

    def add_additional_router(
        self, router: APIRouter, prefix: str | None = None
    ) -> None:
        """Register ``router`` so it is mounted alongside the admin router."""

        self._additional_routers.append((router, prefix))

    def get_additional_routers(self) -> Iterable[tuple[APIRouter, str | None]]:
        """Return routers that should be mounted alongside the admin router."""

        return ()

    def get_public_routers(self) -> Iterable[APIRouter]:
        """Return routers exposing public pages registered on the site."""

        return self.site.pages.iter_public_routers()

    def _iter_additional_routers(self) -> Iterable[tuple[APIRouter, str | None]]:
        yield from self._additional_routers
        if (
            self.__class__.get_additional_routers
            is not RouterAggregator.get_additional_routers  # type: ignore[misc]
        ):
            yield from self.get_additional_routers()


class ExtendedRouterAggregator(RouterAggregator):
    """Compose admin and public routers within a single aggregator."""

    def __init__(
        self,
        site: AdminSite,
        prefix: str | None = None,
        *,
        settings: FreeAdminSettings | None = None,
        additional_routers: Iterable[tuple[APIRouter, str | None]] | None = None,
        public_first: bool = True,
        template_service: TemplateService | None = None,
    ) -> None:
        """Initialise the aggregator and configure registration order."""

        super().__init__(
            site=site,
            prefix=prefix,
            settings=settings,
            additional_routers=additional_routers,
            template_service=template_service,
        )
        self._public_first = public_first
        self._public_routers: list[APIRouter] = []
        self._router: APIRouter | None = None
        retained: list[tuple[APIRouter, str | None]] = []
        for router, router_prefix in self._additional_routers:
            if router_prefix in (None, ""):
                self._public_routers.append(router)
            else:
                retained.append((router, router_prefix))
        self._additional_routers = retained

    def add_admin_router(
        self, router: APIRouter, prefix: str | None = None
    ) -> None:
        """Register ``router`` so it is exposed under the admin prefix."""

        super().add_additional_router(router, prefix or self.prefix)
        self._invalidate_router_cache()

    def add_additional_router(
        self, router: APIRouter, prefix: str | None = None
    ) -> None:
        """Register ``router`` without a prefix for public exposure."""

        if prefix not in (None, ""):
            super().add_additional_router(router, prefix)
        else:
            self._public_routers.append(router)
        self._invalidate_router_cache()

    def get_routers(self) -> list[tuple[APIRouter, str | None]]:
        """Return all registered routers respecting the configured order."""

        self.ensure_site_templates(self.site)
        admin_entries = self._collect_admin_entries()
        public_entries = [(router, None) for router in self._public_routers]
        public_entries.extend((router, None) for router in self.get_public_routers())
        if self._public_first:
            return [*public_entries, *admin_entries]
        return [*admin_entries, *public_entries]

    def mount(self, app: FastAPI, prefix: str | None = None) -> None:
        """Mount public and admin routers onto ``app`` respecting order."""

        self._prefix = (prefix or self._prefix).rstrip("/")
        self.ensure_site_templates(self.site)
        app.state.admin_site = self.site
        if app in self._mounted_apps:
            return

        for router, router_prefix in self.get_routers():
            app.include_router(router, prefix=router_prefix or "")
        self.mount_static_resources(app, self._prefix)
        self._mounted_apps.add(app)

    @property
    def router(self) -> APIRouter:
        """Return an ``APIRouter`` aggregating all registered routers."""

        if self._router is None:
            aggregated = APIRouter()
            for router, router_prefix in self.get_routers():
                aggregated.include_router(router, prefix=router_prefix or "")
            self._router = aggregated
        return self._router

    def invalidate_admin_router(self) -> None:
        """Drop cached admin and aggregate routers to rebuild mappings."""

        super().invalidate_admin_router()
        self._invalidate_router_cache()

    def _collect_admin_entries(self) -> list[tuple[APIRouter, str | None]]:
        entries: list[tuple[APIRouter, str | None]] = [
            (self.get_admin_router(), self.prefix)
        ]
        entries.extend(self._additional_routers)
        if (
            self.__class__.get_additional_routers
            is not RouterAggregator.get_additional_routers  # type: ignore[misc]
        ):
            entries.extend(self.get_additional_routers())
        return entries

    def _invalidate_router_cache(self) -> None:
        self._router = None


__all__ = [
    "AdminRouter",
    "ExtendedRouterAggregator",
    "RouterAggregator",
    "RouterFoundation",
]


# The End

