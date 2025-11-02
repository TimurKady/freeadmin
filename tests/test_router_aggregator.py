# -*- coding: utf-8 -*-
"""
tests.test_router_aggregator

Unit tests for the router aggregator utility.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from starlette.staticfiles import StaticFiles

from freeadmin.core.network.router import (
    AdminRouter,
    ExtendedRouterAggregator,
    RouterAggregator,
)
from freeadmin.core.configuration.conf import FreeAdminSettings
from freeadmin.core.interface.templates import TemplateService


def _extract_static_mount(app: FastAPI, route_name: str) -> tuple[str, StaticFiles]:
    """Return the mounted static route tuple of path and app."""

    for route in app.router.routes:
        if getattr(route, "name", None) == route_name:
            return route.path, route.app  # type: ignore[attr-defined]
    raise AssertionError(f"Static route '{route_name}' not registered")


def _build_site(router: APIRouter) -> MagicMock:
    site = MagicMock()
    site.templates = None
    site.build_router.return_value = router
    site.pages.iter_public_routers.return_value = []
    return site


def test_mount_is_idempotent() -> None:
    """Calling ``mount`` repeatedly must not duplicate admin resources."""

    app = FastAPI()
    admin_router = APIRouter()

    @admin_router.get("/dashboard")
    def dashboard() -> dict[str, str]:
        return {"status": "ok"}

    site = _build_site(admin_router)
    aggregator = RouterAggregator(site=site, prefix="/admin")
    service = aggregator.template_service
    original_get_templates = service.get_templates
    service.get_templates = MagicMock(wraps=original_get_templates)  # type: ignore[assignment]
    provider = service.get_provider()
    provider.mount_static = MagicMock()  # type: ignore[attr-defined]
    provider.mount_favicon = MagicMock()  # type: ignore[attr-defined]
    provider.mount_media = MagicMock()  # type: ignore[attr-defined]

    aggregator.mount(app)
    initial_route_count = len(app.router.routes)
    aggregator.mount(app)
    subsequent_route_count = len(app.router.routes)

    assert site.build_router.call_count == 1
    assert aggregator.get_admin_router() is admin_router
    assert initial_route_count == subsequent_route_count
    assert service.get_templates.call_count == 1  # type: ignore[attr-defined]
    provider.mount_static.assert_called_once_with(app, "/admin")  # type: ignore[attr-defined]
    provider.mount_favicon.assert_called_once_with(app)  # type: ignore[attr-defined]
    provider.mount_media.assert_called_once_with(app)  # type: ignore[attr-defined]
    assert app.state.admin_site is site
    service.get_templates = original_get_templates  # type: ignore[assignment]


def test_admin_router_reuses_aggregator_cache() -> None:
    """Wrapper should expose aggregator caching to callers."""

    app = FastAPI()
    admin_router = APIRouter()

    @admin_router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    site = _build_site(admin_router)
    wrapper = AdminRouter(site=site, prefix="/admin")
    aggregator = wrapper.aggregator
    provider = aggregator.template_service.get_provider()
    provider.mount_static = MagicMock()  # type: ignore[attr-defined]
    provider.mount_favicon = MagicMock()  # type: ignore[attr-defined]
    provider.mount_media = MagicMock()  # type: ignore[attr-defined]

    wrapper.mount(app)
    wrapper.mount(app)

    assert site.build_router.call_count == 1
    assert aggregator.get_admin_router() is admin_router
    provider.mount_static.assert_called_once_with(app, "/admin")  # type: ignore[attr-defined]
    provider.mount_favicon.assert_called_once_with(app)  # type: ignore[attr-defined]
    provider.mount_media.assert_called_once_with(app)  # type: ignore[attr-defined]
    assert app.state.admin_site is site


def test_subclass_can_register_extra_routers() -> None:
    """Subclasses should be able to expose bespoke routers."""

    app = FastAPI()
    admin_router = APIRouter()

    @admin_router.get("/home")
    def home() -> dict[str, str]:
        return {"status": "home"}

    extra_router = APIRouter()

    @extra_router.get("/extras/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    site = _build_site(admin_router)

    class CustomRouterAggregator(RouterAggregator):
        """Router aggregator providing an extra router."""

        def __init__(self, *, site: MagicMock) -> None:
            """Attach the admin site and register the extra router."""

            super().__init__(site=site, prefix="/admin")
            self.add_additional_router(extra_router, "")

    aggregator = CustomRouterAggregator(site=site)
    provider = aggregator.template_service.get_provider()
    provider.mount_static = MagicMock()  # type: ignore[attr-defined]
    provider.mount_favicon = MagicMock()  # type: ignore[attr-defined]
    provider.mount_media = MagicMock()  # type: ignore[attr-defined]
    aggregator.mount(app)

    client = TestClient(app)
    response = client.get("/extras/ping")
    assert response.status_code == 200
    assert response.json() == {"pong": "ok"}

    aggregator.mount(app)
    assert site.build_router.call_count == 1


def test_constructor_additional_router_registration() -> None:
    """Routers passed into the constructor should be mounted."""

    app = FastAPI()
    admin_router = APIRouter()

    @admin_router.get("/root")
    def root() -> dict[str, str]:
        return {"root": "ok"}

    reports_router = APIRouter()

    @reports_router.get("/reports")
    def reports() -> dict[str, str]:
        return {"reports": "ok"}

    site = _build_site(admin_router)
    aggregator = RouterAggregator(
        site=site,
        prefix="/admin",
        additional_routers=((reports_router, "/extras"),),
    )
    provider = aggregator.template_service.get_provider()
    provider.mount_static = MagicMock()  # type: ignore[attr-defined]
    provider.mount_favicon = MagicMock()  # type: ignore[attr-defined]
    provider.mount_media = MagicMock()  # type: ignore[attr-defined]
    aggregator.mount(app)

    client = TestClient(app)
    response = client.get("/extras/reports")
    assert response.status_code == 200
    assert response.json() == {"reports": "ok"}


def test_extended_aggregator_combines_public_and_admin() -> None:
    """Extended aggregator should expose public routes alongside admin ones."""

    app = FastAPI()
    admin_router = APIRouter()

    @admin_router.get("/dashboard")
    def dashboard() -> dict[str, str]:
        return {"status": "admin"}

    public_router = APIRouter()

    @public_router.get("/welcome")
    def welcome() -> dict[str, str]:
        return {"message": "hello"}

    site = _build_site(admin_router)
    aggregator = ExtendedRouterAggregator(site=site, prefix="/admin", public_first=True)
    aggregator.add_additional_router(public_router)
    provider = aggregator.template_service.get_provider()
    provider.mount_static = MagicMock()  # type: ignore[attr-defined]
    provider.mount_favicon = MagicMock()  # type: ignore[attr-defined]
    provider.mount_media = MagicMock()  # type: ignore[attr-defined]

    ordering = aggregator.get_routers()
    assert ordering[0][0] is public_router


def test_static_assets_mounted_without_admin_prefix() -> None:
    """Static assets must mount at the global segment, not under admin."""

    app = FastAPI()
    admin_router = APIRouter()

    @admin_router.get("/status")
    def status() -> dict[str, str]:
        return {"status": "ready"}

    site = _build_site(admin_router)
    settings = FreeAdminSettings()
    template_service = TemplateService(settings=settings)
    aggregator = RouterAggregator(
        site=site,
        prefix="/console",
        settings=settings,
        template_service=template_service,
    )
    aggregator.mount(app)

    provider = aggregator.provider
    route_name = provider._settings.static_route_name  # type: ignore[attr-defined]
    static_path, static_app = _extract_static_mount(app, route_name)

    assert static_path == "/staticfiles"
    assert not static_path.startswith(f"{aggregator.prefix}/")
    assert isinstance(static_app, StaticFiles)


def test_static_assets_honor_custom_segment() -> None:
    """Custom static URL segments should be normalised and mounted."""

    app = FastAPI()
    admin_router = APIRouter()

    @admin_router.get("/status")
    def status() -> dict[str, str]:
        return {"status": "ready"}

    site = _build_site(admin_router)
    settings = FreeAdminSettings(static_url_segment="assets/")
    template_service = TemplateService(settings=settings)
    aggregator = RouterAggregator(
        site=site,
        prefix="/console",
        settings=settings,
        template_service=template_service,
    )
    aggregator.mount(app)

    provider = aggregator.provider
    route_name = provider._settings.static_route_name  # type: ignore[attr-defined]
    static_path, static_app = _extract_static_mount(app, route_name)

    assert static_path == "/assets"
    assert not static_path.startswith(f"{aggregator.prefix}/")
    assert isinstance(static_app, StaticFiles)


def test_extended_aggregator_respects_order_flag() -> None:
    """Setting ``public_first`` to False keeps admin routers first."""

    admin_router = APIRouter()

    @admin_router.get("/home")
    def home() -> dict[str, str]:
        return {"home": "ok"}

    public_router = APIRouter()

    @public_router.get("/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    site = _build_site(admin_router)
    aggregator = ExtendedRouterAggregator(site=site, prefix="/admin", public_first=False)
    aggregator.add_additional_router(public_router)

    routers = aggregator.get_routers()
    assert routers[0][1] == "/admin"
    assert routers[-1][0] is public_router


def test_invalidate_admin_router_rebuilds_cached_router() -> None:
    """Dropping the cache should force site router reconstruction."""

    initial_router = APIRouter()
    site = _build_site(initial_router)
    aggregator = RouterAggregator(site=site, prefix="/admin")

    assert aggregator.get_admin_router() is initial_router

    replacement = APIRouter()
    site.build_router.return_value = replacement

    aggregator.invalidate_admin_router()

    assert aggregator.get_admin_router() is replacement
    assert site.build_router.call_count == 2


def test_extended_aggregator_invalidation_resets_aggregate_router() -> None:
    """Extended aggregator cache should be rebuilt after invalidation."""

    initial_admin = APIRouter()
    site = _build_site(initial_admin)
    aggregator = ExtendedRouterAggregator(site=site, prefix="/admin")

    first_combined = aggregator.router

    replacement_admin = APIRouter()
    site.build_router.return_value = replacement_admin

    aggregator.invalidate_admin_router()

    assert aggregator.router is not first_combined
    assert site.build_router.call_count == 2


# The End

