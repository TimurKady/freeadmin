# -*- coding: utf-8 -*-
"""admin migration notice

Validate rendering of the migration-required admin page."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from freeadmin.core.boot import admin as boot_admin
from freeadmin.core.interface.site import AdminSite
from freeadmin.core.network_router import RouterAggregator
from tests.conftest import admin_state


def test_migration_notice_route_renders() -> None:
    """Render the migration notice page with helpful instructions."""

    admin_state.reset()
    site = AdminSite(boot_admin.adapter, title="Migration Check")
    aggregator = RouterAggregator(site=site)
    app = FastAPI()
    aggregator.mount(app)

    with TestClient(app) as client:
        response = client.get("/admin/migration-required")
    assert response.status_code == 503
    assert "Run your migrations before starting FreeAdmin." in response.text

    admin_state.reset()


# The End
