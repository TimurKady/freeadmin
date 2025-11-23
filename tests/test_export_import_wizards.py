# -*- coding: utf-8 -*-
"""
Test export and import wizards.

Ensure export wizard respects scope filtering and generates files in
multiple formats, and import wizard previews rows and commits correctly.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
import types as _types
from enum import Enum
from types import SimpleNamespace

from fastapi import FastAPI, Request, status
from fastapi.testclient import TestClient
from lxml import html
from openpyxl import load_workbook
from tortoise import Tortoise, fields, models

orig_users_module = sys.modules.get("freeadmin.contrib.adapters.tortoise.users")
fake_users = _types.ModuleType("freeadmin.contrib.adapters.tortoise.users")


class _PermAction(str, Enum):
    view = "view"
    add = "add"
    change = "change"
    delete = "delete"
    export = "export"
    import_ = "import"


setattr(_PermAction, "import", _PermAction.import_)


class AdminUser(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=150, unique=True)

    class Meta:
        app = "admin"


class AdminUserPermission(models.Model):
    id = fields.IntField(pk=True)

    class Meta:
        app = "admin"


AdminUser.__module__ = "freeadmin.contrib.adapters.tortoise.users"
AdminUserPermission.__module__ = "freeadmin.contrib.adapters.tortoise.users"


fake_users.PermAction = _PermAction
fake_users.AdminUser = AdminUser
fake_users.AdminUserPermission = AdminUserPermission
sys.modules["freeadmin.contrib.adapters.tortoise.users"] = fake_users

from tests.system_models import system_models

from freeadmin.core.interface.models import ModelAdmin
from freeadmin.core.interface.site import AdminSite
from freeadmin.core.network_router import AdminRouter
from freeadmin.core.boot import admin as boot_admin
from freeadmin.core.interface.auth import admin_auth_service
from freeadmin.core.interface.permissions import permission_checker
from freeadmin.core.interface.services.permissions import PermAction
from freeadmin.core.interface.services.tokens import ScopeTokenService


class Item(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    description = fields.CharField(max_length=100, null=True)


class ItemAdmin(ModelAdmin):
    model = Item
    export_fields = ("id", "name", "description")
    import_fields = ("id", "name", "description")
    list_filter = ("name",)
    search_fields = ("name",)


class TestExportImportWizards:
    _orig_users_module = orig_users_module
    class PermissionStub:
        async def __call__(self, request: Request) -> None:  # pragma: no cover - stub
            return None

    class PermsStub:
        def require_model(self, perm, app_value=None, model_value=None, **kwargs):
            return TestExportImportWizards.PermissionStub()

    class WizardPage:
        def __init__(self, markup: str) -> None:
            self.doc = html.fromstring(markup)

        def has_back_button(self) -> bool:
            return bool(self.doc.xpath('//button[text()="Back"]'))

    class ExportWizardPage(WizardPage):
        def checkbox_values(self) -> list[str]:
            """Return the values of all export field checkboxes present."""

            return self.doc.xpath(
                '//input[@type="checkbox" and @name="fields"]/@value'
            )

        def checked_values(self) -> list[str]:
            """Return the values of export field checkboxes selected by default."""

            return self.doc.xpath(
                '//input[@type="checkbox" and @name="fields" and @checked]/@value'
            )

    class ImportWizardPage(WizardPage):
        pass

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
        cls.site.register("models", Item, ItemAdmin)
        asyncio.run(cls.site.finalize())
        cls.admin = cls.site.model_reg[("models", "item")]
        cls._orig_perm = permission_checker.require_model
        cls.perms_stub = cls.PermsStub()
        permission_checker.require_model = cls.perms_stub.require_model
        cls.user = SimpleNamespace(
            is_superuser=False,
            permissions={
                PermAction.view,
                PermAction.add,
                PermAction.export,
                getattr(PermAction, "import"),
            },
        )
        TestExportImportWizards.PermissionStub.__call__.__annotations__["request"] = Request

        async def _current_user(request: Request) -> SimpleNamespace:
            return cls.user

        _current_user.__annotations__["request"] = Request

        cls.app = FastAPI()
        AdminRouter(cls.site).mount(cls.app)
        cls.app.dependency_overrides[admin_auth_service.get_current_admin_user] = _current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def teardown_class(cls) -> None:
        permission_checker.require_model = cls._orig_perm
        asyncio.run(Tortoise.close_connections())
        if cls._orig_users_module is not None:
            sys.modules[
                "freeadmin.contrib.adapters.tortoise.users"
            ] = cls._orig_users_module
        else:
            sys.modules.pop("freeadmin.contrib.adapters.tortoise.users", None)

    def test_export_wizard_lists_fields(self) -> None:
        resp = self.client.get("/admin/orm/models/item/export/")
        assert resp.status_code == 200
        page = self.ExportWizardPage(resp.text)
        expected = list(self.admin.get_export_fields())
        values = page.checkbox_values()
        assert set(values) == set(expected)
        assert len(values) == len(expected)

    def test_export_wizard_fields_selected_by_default(self) -> None:
        resp = self.client.get("/admin/orm/models/item/export/")
        assert resp.status_code == 200
        page = self.ExportWizardPage(resp.text)
        expected = list(self.admin.get_export_fields())
        selected = page.checked_values()
        assert set(selected) == set(expected)
        assert len(selected) == len(expected)

    def test_export_wizard_has_back_button(self) -> None:
        resp = self.client.get("/admin/orm/models/item/export/")
        assert resp.status_code == 200
        page = self.ExportWizardPage(resp.text)
        assert page.has_back_button()

    def test_export_preview_scope_query(self) -> None:
        async def _clear() -> None:
            await Item.all().delete()

        asyncio.run(_clear())
        asyncio.run(Item.create(name="one", description="1"))
        asyncio.run(Item.create(name="two", description="2"))
        asyncio.run(Item.create(name="three", description="3"))

        payload_filters = {
            "fields": ["id", "name"],
            "scope": {
                "type": "query",
                "query": {"filters": {"filter.name": "two"}},
            },
        }
        resp = self.client.post(
            "/admin/orm/models/item/export/preview", json=payload_filters
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["rows"][0]["name"] == "two"

    def test_export_preview_scope_ids(self) -> None:
        async def _clear() -> None:
            await Item.all().delete()

        asyncio.run(_clear())
        first = asyncio.run(Item.create(name="one", description="1"))
        asyncio.run(Item.create(name="two", description="2"))
        third = asyncio.run(Item.create(name="three", description="3"))

        payload_ids = {
            "fields": ["id", "name"],
            "scope": {"type": "ids", "ids": [first.id, third.id]},
        }
        resp = self.client.post(
            "/admin/orm/models/item/export/preview", json=payload_ids
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        names = {r["name"] for r in body["rows"]}
        assert names == {"one", "three"}

    def test_export_preview_scope_all_records(self) -> None:
        async def _clear() -> None:
            await Item.all().delete()

        asyncio.run(_clear())
        asyncio.run(Item.create(name="one", description="1"))
        asyncio.run(Item.create(name="two", description="2"))

        payload_all = {
            "fields": ["id", "name"],
            "scope": {"type": "query", "query": {"filters": {}}},
        }
        resp = self.client.post(
            "/admin/orm/models/item/export/preview", json=payload_all
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2

    def test_export_run_generates_files(self) -> None:
        async def _clear() -> None:
            await Item.all().delete()

        asyncio.run(_clear())
        asyncio.run(Item.create(name="one", description="1"))
        asyncio.run(Item.create(name="two", description="2"))
        formats = {
            "json": "application/json",
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        for fmt, mime in formats.items():
            resp = self.client.post(
                "/admin/orm/models/item/export/run",
                json={
                    "fmt": fmt,
                    "scope": {"type": "query", "query": {"filters": {}}},
                },
            )
            assert resp.status_code == 200
            token = resp.json()["token"]
            resp_file = self.client.get(f"/admin/orm/models/item/export/done/{token}")
            assert resp_file.status_code == 200
            assert resp_file.headers["content-type"] == mime
            assert resp_file.headers["content-disposition"].startswith(
                "attachment; filename=item_"
            )
            if fmt == "json":
                rows = json.loads(resp_file.content.decode())
                assert any(r["name"] == "one" for r in rows)
            elif fmt == "csv":
                reader = csv.DictReader(io.StringIO(resp_file.content.decode()))
                rows = list(reader)
                assert any(r["name"] == "one" for r in rows)
            else:
                wb = load_workbook(io.BytesIO(resp_file.content))
                ws = wb.active
                data = list(ws.values)
                header = data[0]
                rows = [dict(zip(header, r)) for r in data[1:]]
                assert any(r["name"] == "one" for r in rows)

    def test_export_run_scope_query(self) -> None:
        async def _clear() -> None:
            await Item.all().delete()

        asyncio.run(_clear())
        asyncio.run(Item.create(name="one", description="1"))
        asyncio.run(Item.create(name="two", description="2"))
        asyncio.run(Item.create(name="three", description="3"))

        payload = {
            "fields": ["id", "name"],
            "fmt": "json",
            "scope": {
                "type": "query",
                "query": {"filters": {"filter.name": "two"}},
            },
        }
        resp = self.client.post(
            "/admin/orm/models/item/export/run", json=payload
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        resp_file = self.client.get(
            f"/admin/orm/models/item/export/done/{token}"
        )
        assert resp_file.status_code == 200
        rows = json.loads(resp_file.content.decode())
        assert len(rows) == 1
        assert rows[0]["name"] == "two"

    def test_export_run_scope_ids(self) -> None:
        async def _clear() -> None:
            await Item.all().delete()

        asyncio.run(_clear())
        first = asyncio.run(Item.create(name="one", description="1"))
        asyncio.run(Item.create(name="two", description="2"))
        third = asyncio.run(Item.create(name="three", description="3"))

        payload = {
            "fields": ["id", "name"],
            "fmt": "json",
            "scope": {"type": "ids", "ids": [first.id, third.id]},
        }
        resp = self.client.post(
            "/admin/orm/models/item/export/run", json=payload
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        resp_file = self.client.get(
            f"/admin/orm/models/item/export/done/{token}"
        )
        assert resp_file.status_code == 200
        rows = json.loads(resp_file.content.decode())
        names = {r["name"] for r in rows}
        assert names == {"one", "three"}

    def test_export_run_scope_token(self) -> None:
        async def _clear() -> None:
            await Item.all().delete()

        asyncio.run(_clear())
        first = asyncio.run(Item.create(name="one", description="1"))
        asyncio.run(Item.create(name="two", description="2"))
        third = asyncio.run(Item.create(name="three", description="3"))

        token = ScopeTokenService().sign(
            {"type": "ids", "ids": [first.id, third.id]}, 60
        )
        payload = {
            "fields": ["id", "name"],
            "fmt": "json",
            "scope_token": token,
        }
        resp = self.client.post(
            "/admin/orm/models/item/export/run", json=payload
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        resp_file = self.client.get(
            f"/admin/orm/models/item/export/done/{token}"
        )
        assert resp_file.status_code == 200
        rows = json.loads(resp_file.content.decode())
        names = {r["name"] for r in rows}
        assert names == {"one", "three"}

    def test_export_endpoints_without_permission(self) -> None:
        self.user.permissions.discard(PermAction.export)
        resp = self.client.post(
            "/admin/orm/models/item/export/preview", json={}
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json() == {"detail": "Export not permitted"}
        resp = self.client.post(
            "/admin/orm/models/item/export/run", json={}
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json() == {"detail": "Export not permitted"}
        resp = self.client.get(
            "/admin/orm/models/item/export/done/invalid-token"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json() == {"detail": "Export not permitted"}
        self.user.permissions.add(PermAction.export)

    def test_import_wizard_has_back_button(self) -> None:
        resp = self.client.get("/admin/orm/models/item/import/")
        assert resp.status_code == 200
        page = self.ImportWizardPage(resp.text)
        assert page.has_back_button()

    def test_import_endpoints_without_permission(self) -> None:
        self.user.permissions.discard(getattr(PermAction, "import"))
        csv_data = "id,name,description\n1,foo,bar\n"
        resp = self.client.post(
            "/admin/orm/models/item/import/preview",
            files={"file": ("items.csv", csv_data, "text/csv")},
            data={"fields": ["id", "name", "description"]},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json() == {"detail": "Import not permitted"}
        resp = self.client.post(
            "/admin/orm/models/item/import/run",
            json={"token": "dummy", "fields": ["id"]},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json() == {"detail": "Import not permitted"}
        self.user.permissions.add(getattr(PermAction, "import"))

    def test_superuser_export_without_permission(self) -> None:
        self.user.permissions.discard(PermAction.export)
        self.user.is_superuser = True

        async def _reset() -> None:
            await Item.all().delete()

        asyncio.run(_reset())
        asyncio.run(Item.create(name="one", description="1"))

        payload_preview = {
            "fields": ["id", "name"],
            "scope": {"type": "query", "query": {"filters": {}}},
        }
        resp = self.client.post(
            "/admin/orm/models/item/export/preview", json=payload_preview
        )
        assert resp.status_code == 200

        payload_run = {
            "fmt": "json",
            "scope": {"type": "query", "query": {"filters": {}}},
        }
        resp_run = self.client.post(
            "/admin/orm/models/item/export/run", json=payload_run
        )
        assert resp_run.status_code == 200
        token = resp_run.json()["token"]
        resp_done = self.client.get(
            f"/admin/orm/models/item/export/done/{token}"
        )
        assert resp_done.status_code == 200

        self.user.is_superuser = False
        self.user.permissions.add(PermAction.export)

    def test_import_preview_and_commit(self) -> None:
        async def _clear() -> None:
            await Item.all().delete()

        asyncio.run(_clear())
        rows = ["id,name,description\n"]
        for i in range(25):
            rows.append(f"{i + 1},item{i},desc{i}\n")
        csv_data = "".join(rows)
        resp = self.client.post(
            "/admin/orm/models/item/import/preview",
            files={"file": ("items.csv", csv_data, "text/csv")},
            data={"fields": ["id", "name", "description"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        token = body["token"]
        assert len(body["rows"]) == 20
        assert body["rows"][0]["name"] == "item0"
        assert body["rows"][0]["id"] == "1"

        resp = self.client.post(
            "/admin/orm/models/item/import/run",
            json={"token": token, "fields": ["id", "name", "description"]},
        )
        assert resp.status_code == 200
        report = resp.json()
        assert report["processed"] == 25
        assert report["created"] == 25
        assert report["updated"] == 0
        assert report["errors"] == []
        async def _count() -> int:
            return await Item.all().count()
        count = asyncio.run(_count())
        assert count == 25

    def test_import_updates_existing_rows(self) -> None:
        async def _setup() -> Item:
            await Item.all().delete()
            return await Item.create(name="one", description="first")

        existing = asyncio.run(_setup())
        csv_data = (
            "id,name,description\n"
            f"{existing.id},one,updated\n"
            f"{existing.id + 1},two,newdesc\n"
        )
        resp_preview = self.client.post(
            "/admin/orm/models/item/import/preview",
            files={"file": ("items.csv", csv_data, "text/csv")},
            data={"fields": ["id", "name", "description"]},
        )
        assert resp_preview.status_code == 200
        token = resp_preview.json()["token"]
        resp_run = self.client.post(
            "/admin/orm/models/item/import/run",
            json={"token": token, "fields": ["id", "name", "description"]},
        )
        assert resp_run.status_code == 200
        report = resp_run.json()
        assert report["processed"] == 2
        assert report["created"] == 1
        assert report["updated"] == 1

        async def _fetch(pk: int) -> Item:
            return await Item.get(id=pk)

        updated = asyncio.run(_fetch(existing.id))
        assert updated.description == "updated"

# The End

