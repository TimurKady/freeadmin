# -*- coding: utf-8 -*-
"""admin template context

Validate that admin template context exposes layout-related flags."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.requests import Request

from freeadmin.core.interface.context import TemplateContextBuilder
from freeadmin.core.interface.site import AdminSite


class DummyAdapter:
    """Minimal adapter satisfying the admin site's contract for tests."""

    content_type_model = object()
    IntegrityError = Exception


class AdminContextFactory:
    """Provide helpers for constructing admin context test fixtures."""

    def __init__(self) -> None:
        """Initialise reusable factory state for admin context tests."""

    def create_site(self) -> AdminSite:
        """Return a new admin site configured with the dummy adapter."""

        return AdminSite(DummyAdapter(), title="Test Admin")

    def build_request(self, path: str = "/admin/") -> Request:
        """Construct a Starlette request pointing at ``path``."""

        app = FastAPI()
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


def test_admin_context_marks_admin_request() -> None:
    """Ensure admin context explicitly flags administrative requests."""

    factory = AdminContextFactory()
    site = factory.create_site()
    request = factory.build_request()

    context = TemplateContextBuilder(site).build(request, user=None)

    assert context["is_admin_request"] is True
    assert context["prefix"] == "/admin"


# The End

