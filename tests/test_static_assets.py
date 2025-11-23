"""static assets

Validate scheme-agnostic URL handling for static assets."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.requests import Request

from freeadmin.config import current_settings
from freeadmin.core.interface.base import BaseModelAdmin


class _AdapterStub:
    """Provide a minimal adapter stub for BaseModelAdmin instantiation."""


class DummyModel:
    """Represent a stand-in model for BaseModelAdmin tests."""


class TestStaticAssetPrefixing:
    """Ensure static asset URL generation stays scheme agnostic."""

    def test_prefix_static_uses_relative_path_for_https_requests(self) -> None:
        """Verify `_prefix_static` strips schemes even on HTTPS requests."""

        settings = current_settings()
        route_name = settings.static_route_name
        app = FastAPI()

        @app.get("/staticfiles/{path:path}", name=route_name)
        async def static_proxy(path: str) -> dict[str, str]:  # pragma: no cover - helper route
            """Provide a placeholder static response for URL generation."""

            return {"path": path}

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "path": "/admin/",  # arbitrary request path
            "raw_path": b"/admin/",
            "scheme": "https",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 443),
            "server": ("testserver", 443),
            "app": app,
            "root_path": "/tenant",
        }
        request = Request(scope)
        admin = BaseModelAdmin(DummyModel, _AdapterStub())

        asset_url = admin._prefix_static("/static/vendors/example.js", request=request)

        assert asset_url.startswith("/tenant/staticfiles/vendors/example.js")
        assert "http://" not in asset_url


# The End

