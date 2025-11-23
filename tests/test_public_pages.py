# -*- coding: utf-8 -*-
"""public pages

Test coverage for registering and exposing public FreeAdmin pages."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.requests import Request

from freeadmin.core.boot import admin as boot_admin
from freeadmin.core.interface.site import AdminSite
from freeadmin.core.interface.templates.rendering import PageTemplateResponder
from freeadmin.core.network_router import ExtendedRouterAggregator
from tests.conftest import admin_state


def _build_request(path: str, site: AdminSite) -> Request:
    """Return a Starlette request bound to ``site`` for ``path``."""

    app = FastAPI()
    app.state.admin_site = site
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 80),
        "server": ("testserver", 80),
        "app": app,
    }
    return Request(scope)


class TestPublicPageRegistration:
    """Validate registration and mounting of public pages."""

    site: AdminSite

    @classmethod
    def setup_class(cls) -> None:
        """Prepare a fresh admin site and register a public page."""

        admin_state.reset()
        cls.site = AdminSite(boot_admin.adapter, title="Public Page Test")

        @cls.site.register_public_view(
            path="/welcome",
            name="Welcome",
            template="pages/welcome.html",
        )
        async def welcome(request, user=None) -> dict[str, object]:
            """Provide additional context for the welcome page."""

            return {"subtitle": "Rendered from tests", "user": user}

    @classmethod
    def teardown_class(cls) -> None:
        """Restore the global admin state after tests complete."""

        admin_state.reset()

    def test_public_router_registration(self) -> None:
        """Ensure the page manager exposes routers for public pages."""

        routers = list(self.site.pages.iter_public_routers())
        assert len(routers) == 1
        router = routers[0]
        paths = sorted(getattr(route, "path", "") for route in router.routes)
        assert "/welcome" in paths

    def test_extended_aggregator_includes_public_routes(self) -> None:
        """Verify aggregated routers include registered public pages."""

        aggregator = ExtendedRouterAggregator(site=self.site)
        aggregator.add_admin_router(aggregator.get_admin_router())
        collected_routes: list[str] = []
        for router, prefix in aggregator.get_routers():
            if prefix not in (None, ""):
                continue
            for route in router.routes:
                path = getattr(route, "path", None)
                if path:
                    collected_routes.append(path)
        assert "/welcome" in collected_routes

    def test_public_view_registers_menu_entry(self) -> None:
        """Ensure public views are exposed in the public menu builder."""

        menu = self.site.public_menu_builder.build_menu()
        assert any(item.path == "/welcome" for item in menu)

    def test_register_public_menu_adds_entry(self) -> None:
        """Ensure manual public menu registration updates the builder."""

        self.site.register_public_menu(title="Docs", path="/docs", icon="bi-book")
        menu = self.site.public_menu_builder.build_menu()
        assert any(item.path == "/docs" and item.icon == "bi-book" for item in menu)

    def test_default_context_uses_public_menu_for_public_requests(self) -> None:
        """Verify the template responder injects public menu context."""

        request = _build_request("/welcome", self.site)
        context = PageTemplateResponder._build_default_context(request)
        assert context["prefix"] == "/"
        assert context["public_prefix"] == "/"
        assert not context["is_admin_request"]
        assert any(item.path == "/welcome" for item in context["public_menu"])

    def test_default_context_detects_admin_requests(self) -> None:
        """Verify admin-prefixed URLs keep the administrative prefix."""

        request = _build_request("/admin/dashboard", self.site)
        context = PageTemplateResponder._build_default_context(request)
        assert context["is_admin_request"]
        assert context["prefix"].startswith("/admin")


# The End

