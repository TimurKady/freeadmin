# -*- coding: utf-8 -*-
"""
application.factory

Factories for assembling FastAPI applications with FreeAdmin integration.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from inspect import Parameter, signature
from typing import Any, Protocol, runtime_checkable

from fastapi import FastAPI

from freeadmin.core.boot import BootManager
from freeadmin.core.orm import ORMConfig, ORMLifecycle

LifecycleHook = Callable[[], Awaitable[None] | None]


@runtime_checkable
class RouterManager(Protocol):
    """Protocol describing router aggregators capable of mounting routes."""

    def mount(self, app: FastAPI, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - structural
        """Mount managed routers onto ``app``."""


class ApplicationFactory:
    """Create configured FastAPI applications backed by FreeAdmin."""

    def __init__(
        self,
        *,
        settings: Any | None = None,
        orm_config: ORMConfig | None = None,
        router_manager: RouterManager | None = None,
        packages: Iterable[str] | None = None,
        boot_manager: BootManager | None = None,
    ) -> None:
        """Persist configuration and supporting services for application builds."""

        self._settings = settings
        self._orm_config = orm_config or ORMConfig()
        self._router_manager = router_manager
        self._packages: list[str] = []
        self._startup_hooks: list[LifecycleHook] = []
        self._shutdown_hooks: list[LifecycleHook] = []
        self._bound_apps: set[int] = set()
        self._boot_provided = boot_manager is not None
        self._orm_lifecycle: ORMLifecycle = self._orm_config.create_lifecycle()
        self._boot = boot_manager or BootManager(
            adapter_name=self._orm_lifecycle.adapter_name
        )
        self.register_packages(packages or ("apps", "pages"))

    def register_packages(self, packages: Iterable[str]) -> None:
        """Register discovery packages ensuring every entry is unique."""

        for package in packages:
            if not package:
                continue
            if package not in self._packages:
                self._packages.append(package)

    def register_startup_hook(self, hook: LifecycleHook) -> None:
        """Store a coroutine or callable to execute during application startup."""

        self._startup_hooks.append(hook)

    def register_shutdown_hook(self, hook: LifecycleHook) -> None:
        """Store a coroutine or callable to execute during application shutdown."""

        self._shutdown_hooks.append(hook)

    def build(
        self,
        *,
        settings: Any | None = None,
        orm_config: ORMConfig | None = None,
        router_manager: RouterManager | None = None,
        packages: Iterable[str] | None = None,
    ) -> FastAPI:
        """Return a FastAPI instance wired with FreeAdmin integration."""

        if settings is not None:
            self._settings = settings
        if orm_config is not None and orm_config is not self._orm_config:
            self._orm_config = orm_config
            self._orm_lifecycle = self._orm_config.create_lifecycle()
            self._bound_apps.clear()
            if not self._boot_provided:
                self._boot = BootManager(
                    adapter_name=self._orm_lifecycle.adapter_name
                )
        if router_manager is not None:
            self._router_manager = router_manager
        if packages is not None:
            self.register_packages(packages)

        title = getattr(self._settings, "project_title", None)
        if title:
            app = FastAPI(title=title)
        else:
            app = FastAPI()

        self._initialize_orm(app)
        self._boot.init(
            app,
            adapter=self._orm_lifecycle.adapter_name,
            packages=list(self._packages),
        )
        self._mount_routers(app)
        self._register_lifecycle_hooks(app)
        return app

    def _initialize_orm(self, app: FastAPI) -> None:
        """Attach the ORM lifecycle handlers to ``app`` once."""

        app_id = id(app)
        if app_id in self._bound_apps:
            return
        self._orm_lifecycle.bind(app)
        self._bound_apps.add(app_id)

    def _mount_routers(self, app: FastAPI) -> None:
        """Delegate route mounting to the configured router manager if present."""

        if self._router_manager is None:
            from freeadmin.core.runtime.hub import admin_site
            from freeadmin.core.network_router import AdminRouter

            self._router_manager = AdminRouter(admin_site)
        mount = getattr(self._router_manager, "mount", None)
        if mount is None:
            return
        try:
            params = list(signature(mount).parameters.values())
        except (TypeError, ValueError):  # pragma: no cover - fallback for C implementations
            mount(app)
            return
        if not params:
            mount()
            return
        if len(params) == 1 or (
            len(params) > 1 and params[1].default is not Parameter.empty
        ):
            mount(app)
            return
        from freeadmin.core.runtime.hub import admin_site

        mount(app, admin_site)

    def _register_lifecycle_hooks(self, app: FastAPI) -> None:
        """Attach registered startup and shutdown hooks to ``app``."""

        for hook in self._startup_hooks:
            app.add_event_handler("startup", hook)
        for hook in self._shutdown_hooks:
            app.add_event_handler("shutdown", hook)


__all__ = ["ApplicationFactory", "RouterManager"]


# The End
