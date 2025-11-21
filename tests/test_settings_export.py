# -*- coding: utf-8 -*-
"""
Test export run endpoint for settings mode AdminUser.

Ensure that export routes are available for settings models.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Callable, cast

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from tortoise import Tortoise

from freeadmin.core.runtime.hub import admin_site
from freeadmin.core.network.router import AdminRouter
from freeadmin.core.interface.permissions import permission_checker
from freeadmin.core.interface.services.permissions import PermAction
from freeadmin.core.interface.auth import admin_auth_service
from tests.system_models import system_models
import freeadmin.contrib.apps.system.admin  # ensure registration


class TestSettingsExport:
    """Verify export endpoint for settings models."""

    _orig_perm: Any
    user: SimpleNamespace
    app: FastAPI
    client: TestClient

    @classmethod
    def setup_class(cls) -> None:
        asyncio.run(
            Tortoise.init(
                db_url="sqlite://:memory:",
                modules={
                    "admin": list(system_models.module_names()),
                },
            )
        )
        asyncio.run(Tortoise.generate_schemas())
        asyncio.run(admin_site.finalize())

        cls._orig_perm = permission_checker.require_view

        async def _allow(request: Request) -> None:  # pragma: no cover - stub
            return None

        def _perm_stub(*args: Any, **kwargs: Any) -> Callable[[Request], Any]:
            return _allow

        cast(Any, permission_checker).require_view = _perm_stub

        cls.user = SimpleNamespace(
            is_superuser=True, permissions={cast(Any, PermAction).export}
        )

        async def _current_user(request: Request) -> SimpleNamespace:
            return cls.user

        cls.app = FastAPI()
        AdminRouter(admin_site).mount(cls.app)
        cls.app.dependency_overrides[
            admin_auth_service.get_current_admin_user
        ] = _current_user
        cls.client = TestClient(cls.app)
        asyncio.run(
            system_models.models.user.create(username="u", email="u@example.com")
        )

    @classmethod
    def teardown_class(cls) -> None:
        cast(Any, permission_checker).require_view = cls._orig_perm
        asyncio.run(Tortoise.close_connections())

    def test_export_run_available(self) -> None:
        payload = {"scope": {"type": "ids", "ids": []}}
        resp = self.client.post(
            "/admin/settings/admin/adminuser/export/run", json=payload
        )
        assert resp.status_code == 200
        assert "token" in resp.json()


# The End

