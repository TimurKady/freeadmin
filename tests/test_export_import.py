# -*- coding: utf-8 -*-
"""
Test export and import admin endpoints.

Ensure that export returns serialized rows and import respects dry-run logic.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from tortoise import Tortoise, fields, models

from freeadmin.core.interface.models import ModelAdmin
from freeadmin.core.interface.site import AdminSite
from freeadmin.core.network_router import AdminRouter
from freeadmin.core.boot import admin as boot_admin
from freeadmin.core.interface.auth import admin_auth_service
from freeadmin.core.interface.permissions import permission_checker
from freeadmin.core.interface.services.permissions import PermAction
from tests.system_models import system_models


class ExportItem(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    description = fields.CharField(max_length=100, null=True)


class ExportChild(models.Model):
    id = fields.IntField(pk=True)
    label = fields.CharField(max_length=50)
    parent: fields.ForeignKeyRelation[ExportItem] = fields.ForeignKeyField(
        "models.ExportItem", related_name="children"
    )


class ItemAdmin(ModelAdmin):
    model = ExportItem
    export_fields = ("id", "name", "description")
    import_fields = ("id", "name", "description")


class ChildAdmin(ModelAdmin):
    model = ExportChild
    export_fields = ("id", "label", "parent")
    import_fields = ("id", "label", "parent")


class TestExportImport:
    site: AdminSite
    perms_stub: "TestExportImport.PermsStub"
    _orig_perm: Any
    user: SimpleNamespace
    app: FastAPI
    client: TestClient

    class PermissionStub:
        async def __call__(self, request: Request) -> None:  # pragma: no cover - stub
            return None

    class PermsStub:
        def require_model(
            self, *args: Any, **kwargs: Any
        ) -> "TestExportImport.PermissionStub":
            return TestExportImport.PermissionStub()

    @classmethod
    def setup_class(cls) -> None:
        asyncio.run(
            Tortoise.init(
                db_url="sqlite://:memory:",
                modules={
                    "models": [__name__],
                    "admin": list(system_models.module_names()),
                },
            )
        )
        asyncio.run(Tortoise.generate_schemas())
        cls.site = AdminSite(boot_admin.adapter, title="Test")
        cls.site._model_to_slug = lambda n: n.replace("Export", "").lower()
        cls.site.register("models", ExportItem, ItemAdmin)
        cls.site.register("models", ExportChild, ChildAdmin)
        asyncio.run(cls.site.finalize())
        cls._orig_perm = permission_checker.require_model
        cls.perms_stub = cls.PermsStub()
        cast(Any, permission_checker).require_model = cls.perms_stub.require_model
        perm_any = cast(Any, PermAction)
        cls.user = SimpleNamespace(
            is_superuser=False,
            permissions={
                perm_any.view,
                perm_any.add,
                perm_any.export,
                getattr(perm_any, "import"),
            },
        )
        TestExportImport.PermissionStub.__call__.__annotations__["request"] = Request

        async def _current_user(request: Request) -> SimpleNamespace:
            return cls.user

        _current_user.__annotations__["request"] = Request

        cls.app = FastAPI()
        AdminRouter(cls.site).mount(cls.app)
        cls.app.dependency_overrides[admin_auth_service.get_current_admin_user] = (
            _current_user
        )
        cls.client = TestClient(cls.app)

    @classmethod
    def teardown_class(cls) -> None:
        cast(Any, permission_checker).require_model = cls._orig_perm
        asyncio.run(Tortoise.close_connections())
        asyncio.run(Tortoise._reset_apps())

    def test_export_returns_rows(self) -> None:
        async def _clear() -> None:
            await ExportItem.all().delete()

        asyncio.run(_clear())
        first = asyncio.run(ExportItem.create(name="one", description="1"))
        second = asyncio.run(ExportItem.create(name="two", description="2"))
        resp = self.client.post("/admin/orm/models/item/export")
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        assert {"id": first.id, "name": "one", "description": "1"} in rows
        assert {"id": second.id, "name": "two", "description": "2"} in rows

    def test_export_response_type(self) -> None:
        resp = self.client.post("/admin/orm/models/item/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        assert isinstance(resp.json()["rows"], list)

    def test_export_foreign_key_as_id(self) -> None:
        async def _clear() -> None:
            await ExportChild.all().delete()
            await ExportItem.all().delete()

        asyncio.run(_clear())
        parent = asyncio.run(ExportItem.create(name="parent", description="p"))
        child = asyncio.run(ExportChild.create(label="c", parent=parent))
        resp = self.client.post("/admin/orm/models/child/export")
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        assert {"id": child.id, "label": "c", "parent": parent.id} in rows

    def test_import_dry_run_and_commit(self) -> None:
        async def _clear() -> None:
            await ExportItem.all().delete()

        asyncio.run(_clear())
        payload = {
            "rows": [
                {"name": "a", "description": "old"},
                {"name": "b", "description": "bbb"},
            ],
            "dry": True,
        }
        resp = self.client.post("/admin/orm/models/item/import", json=payload)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

        async def _count() -> int:
            return await ExportItem.all().count()

        assert asyncio.run(_count()) == 0

        payload = {
            "rows": [
                {"name": "a", "description": "old"},
                {"name": "b", "description": "bbb"},
            ]
        }
        resp = self.client.post("/admin/orm/models/item/import", json=payload)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        assert asyncio.run(_count()) == 2

        async def _get_id() -> int:
            obj = await ExportItem.get(name="a")
            return obj.id

        first_id = asyncio.run(_get_id())
        payload = {
            "rows": [
                {"id": first_id, "name": "a", "description": "new"},
                {"name": "c", "description": "ccc"},
            ]
        }
        resp = self.client.post("/admin/orm/models/item/import", json=payload)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        assert asyncio.run(_count()) == 3

        async def _desc(i: int) -> str:
            obj = await ExportItem.get(id=i)
            return obj.description or ""

        assert asyncio.run(_desc(first_id)) == "new"

    def test_import_dry_run_preview(self) -> None:
        async def _clear() -> None:
            await ExportItem.all().delete()

        asyncio.run(_clear())
        payload = {"rows": [{"name": "z", "description": "zzz"}], "dry": True}
        resp = self.client.post("/admin/orm/models/item/import", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry"] is True
        assert body["count"] == 1

# The End

