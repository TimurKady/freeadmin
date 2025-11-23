"""system settings runtime updates

Verify that runtime settings pulled from the database are applied immediately
across middleware, routing, and template contexts.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from starlette.requests import Request

from freeadmin.core.configuration.conf import FreeAdminSettings
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.network.router.aggregator import RouterAggregator
from freeadmin.core.runtime.middleware import AdminGuardMiddleware
from freeadmin.core.interface.templates.rendering import PageTemplateResponder


class DummySite:
    """Minimal site stub for router initialisation."""

    def __init__(self) -> None:
        """Prepare placeholder adapter reference."""

        self.adapter = object()


class DummyApp:
    """Simple ASGI application placeholder."""

    def __init__(self) -> None:
        """Initialize with a no-op admin site placeholder."""

        self.state = type("State", (), {"admin_site": None})()

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        """ASGI entrypoint stub required by Starlette middleware."""

        return None


class TestRuntimeSettingsPropagation:
    """Ensure runtime settings updates are visible without restarts."""

    @pytest.fixture(autouse=True)
    def clear_system_config_cache(self) -> None:
        """Reset system configuration cache before and after each test."""

        original = dict(system_config._cache)  # type: ignore[attr-defined]
        system_config._cache.clear()  # type: ignore[attr-defined]
        try:
            yield
        finally:
            system_config._cache.clear()  # type: ignore[attr-defined]
            system_config._cache.update(original)  # type: ignore[attr-defined]

    def test_router_aggregator_tracks_runtime_prefix(self) -> None:
        """RouterAggregator should reflect admin prefix updates from the cache."""

        system_config._cache[SettingsKey.ADMIN_PREFIX.value] = "/initial-admin"  # type: ignore[attr-defined]
        aggregator = RouterAggregator(site=DummySite(), settings=FreeAdminSettings())

        assert aggregator.prefix == "/initial-admin"

        system_config._cache[SettingsKey.ADMIN_PREFIX.value] = "/updated-admin"  # type: ignore[attr-defined]
        assert aggregator.prefix == "/updated-admin"

    def test_admin_guard_prefix_refreshes_after_setting_change(self) -> None:
        """AdminGuardMiddleware should read the current admin prefix dynamically."""

        system_config._cache[SettingsKey.ADMIN_PREFIX.value] = "/configured-admin"  # type: ignore[attr-defined]
        middleware = AdminGuardMiddleware(DummyApp(), settings=FreeAdminSettings())

        assert middleware.prefix == "/configured-admin"

        system_config._cache[SettingsKey.ADMIN_PREFIX.value] = "/new-admin"  # type: ignore[attr-defined]
        assert middleware.prefix == "/new-admin"

    @pytest.mark.asyncio
    async def test_template_defaults_pull_from_runtime_cache(self) -> None:
        """Template context defaults should honor updated runtime settings."""

        system_config._cache.update(  # type: ignore[attr-defined]
            {
                SettingsKey.DEFAULT_ADMIN_TITLE.value: "Runtime Title",
                SettingsKey.BRAND_ICON.value: "brand.png",
                SettingsKey.PUBLIC_PREFIX.value: "/public",
                SettingsKey.ADMIN_PREFIX.value: "/admin",
            }
        )

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/",
            "root_path": "",
            "scheme": "http",
            "server": ("testserver", 80),
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
        }
        scope["app"] = DummyApp()

        async def _receive() -> dict[str, Any]:
            """Provide an empty HTTP request body for template context generation."""

            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive=_receive)

        context = PageTemplateResponder._build_default_context(request)
        assert context["site_title"] == "Runtime Title"
        assert context["brand_icon"] == "brand.png"
        assert context["public_prefix"] == "/public"
        assert context["admin_prefix"] == "/admin"

        system_config._cache[SettingsKey.DEFAULT_ADMIN_TITLE.value] = "Updated Title"  # type: ignore[attr-defined]
        updated_context = PageTemplateResponder._build_default_context(request)
        assert updated_context["site_title"] == "Updated Title"


# The End
