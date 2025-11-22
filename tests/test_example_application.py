# -*- coding: utf-8 -*-
"""
test_example_application

Smoke tests that validate the example application setup.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from example.config.main import ExampleApplication
from example.config.orm import (
    ADMIN_APP_MODULES,
    MODELS_APP_MODULES,
    ExampleORMConfig,
)
from tests.sampleapp.app import default as sample_app_config
from tortoise import Tortoise

from freeadmin.contrib.adapters.tortoise.adapter import (
    Adapter as TortoiseAdapter,
)
from freeadmin.core.orm import ORMConfig


class TestExampleApplicationSmoke:
    """Verify that the example application mounts the admin router."""

    def test_admin_router_mounted(self) -> None:
        """Ensure configuring the example attaches the admin site to the app."""

        application = ExampleApplication()
        app = application.build()

        assert getattr(app.state, "admin_site", None) is not None

    def test_public_welcome_route_mounted(self) -> None:
        """Ensure building the example application exposes the welcome page."""

        application = ExampleApplication()
        app = application.build()

        has_public_welcome_route = any(
            route.path == "/" and "GET" in getattr(route, "methods", set())
            for route in app.router.routes
        )

        assert has_public_welcome_route is True

    def test_public_menu_entries_registered(self) -> None:
        """Ensure the example application registers public menu entries."""

        application = ExampleApplication()
        app = application.build()

        admin_site = app.state.admin_site
        menu_items = admin_site.public_menu_builder.build_menu()
        menu_paths = {item.path for item in menu_items}
        menu_titles = {item.title for item in menu_items}

        assert "/docs" in menu_paths
        assert "Documentation" in menu_titles
        assert "/login" in menu_paths


class TestExampleApplicationStartup:
    """Ensure application configs execute startup hooks during boot."""

    @pytest.mark.asyncio
    async def test_app_config_startup_called(self) -> None:
        """Verify AppConfig.startup executes when FastAPI starts up."""

        sample_app_config.ready_calls = 0
        application = ExampleApplication()
        application.register_packages(["tests.sampleapp"])
        app = application.build()

        boot_manager = application.boot_manager
        hub = boot_manager._ensure_hub()
        hub.admin_site.finalize = AsyncMock()
        hub.admin_site.cards.start_publishers = AsyncMock()
        hub.admin_site.cards.shutdown_publishers = AsyncMock()
        boot_manager._config = SimpleNamespace(
            ensure_seed=AsyncMock(),
            reload=AsyncMock(),
        )

        await app.router.startup()
        try:
            assert sample_app_config.ready_calls == 1
        finally:
            await app.router.shutdown()

    @pytest.mark.asyncio
    async def test_app_initialises_orm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify the example app initialises and tears down Tortoise ORM."""

        init_arguments: dict[str, object] = {}
        shutdown_calls: list[bool] = []

        async def fake_init(*, config: dict[str, object]) -> None:
            init_arguments["config"] = config

        async def fake_close() -> None:
            shutdown_calls.append(True)

        monkeypatch.setattr(Tortoise, "init", fake_init)
        monkeypatch.setattr(Tortoise, "close_connections", fake_close)

        custom_dsn = "sqlite:///example.db"
        custom_config = deepcopy(ExampleORMConfig.config)
        custom_config["connections"][ExampleORMConfig.default_connection_name] = custom_dsn
        orm_config = ORMConfig.build(
            adapter_name=ExampleORMConfig.adapter_name,
            config=custom_config,
        )
        application = ExampleApplication()
        app = application.build(orm_config=orm_config)

        boot_manager = application.boot_manager
        hub = boot_manager._ensure_hub()
        hub.admin_site.finalize = AsyncMock()
        hub.admin_site.cards.start_publishers = AsyncMock()
        hub.admin_site.cards.shutdown_publishers = AsyncMock()
        boot_manager._config = SimpleNamespace(
            ensure_seed=AsyncMock(),
            reload=AsyncMock(),
        )

        await app.router.startup()
        try:
            recorded_config = init_arguments["config"]
            assert recorded_config["connections"][
                ExampleORMConfig.default_connection_name
            ] == custom_dsn
            apps = recorded_config["apps"]
            project_modules = set(apps["models"]["models"])
            assert set(MODELS_APP_MODULES).issubset(project_modules)
            admin_modules = set(apps["admin"]["models"])
            assert set(ADMIN_APP_MODULES).issubset(admin_modules)
            assert "system" not in apps
        finally:
            await app.router.shutdown()

        assert shutdown_calls == [True]


class TestExampleApplicationDiscovery:
    """Validate discovery of demo application resources."""

    @pytest.mark.asyncio
    async def test_demo_config_startup_invoked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure DemoConfig.startup executes when scanning nested packages."""

        application = ExampleApplication()
        application.register_packages(["example.apps"])
        app = application.build()

        boot_manager = application.boot_manager
        hub = boot_manager._ensure_hub()
        hub.admin_site.finalize = AsyncMock()
        hub.admin_site.cards.start_publishers = AsyncMock()
        hub.admin_site.cards.shutdown_publishers = AsyncMock()
        boot_manager._config = SimpleNamespace(
            ensure_seed=AsyncMock(),
            reload=AsyncMock(),
        )

        from example.apps.demo import app as demo_app_module

        startup_mock = AsyncMock()
        monkeypatch.setattr(demo_app_module.default, "startup", startup_mock)
        previous_config = hub._app_configs.get("example.apps.demo")
        was_started = "example.apps.demo" in hub._started_configs
        hub._started_configs.discard("example.apps.demo")

        await app.router.startup()
        try:
            assert startup_mock.await_count == 1
        finally:
            await app.router.shutdown()
            if was_started:
                hub._started_configs.add("example.apps.demo")
            else:
                hub._started_configs.discard("example.apps.demo")
            if previous_config is None:
                hub._app_configs.pop("example.apps.demo", None)
            else:
                hub._app_configs["example.apps.demo"] = previous_config


class TestApplicationFactoryHooks:
    """Validate hook registration integrates with FastAPI events."""

    @pytest.mark.asyncio
    async def test_custom_startup_and_shutdown_hooks(self) -> None:
        """Ensure custom lifecycle hooks registered on the example execute."""

        application = ExampleApplication()
        startup_calls: list[str] = []
        shutdown_calls: list[str] = []

        def record_startup() -> None:
            startup_calls.append("startup")

        async def record_shutdown() -> None:
            shutdown_calls.append("shutdown")

        application.register_startup_hook(record_startup)
        application.register_shutdown_hook(record_shutdown)

        app = application.build()

        await app.router.startup()
        try:
            assert startup_calls == ["startup"]
        finally:
            await app.router.shutdown()

        assert shutdown_calls == ["shutdown"]


# The End

