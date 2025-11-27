# -*- coding: utf-8 -*-
"""
admin inline operations tests

Verify inline metadata retrieval, forced foreign key headers, and badge count updates.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from tortoise import Tortoise, fields, models

from freeadmin.core.interface.models import ModelAdmin
from freeadmin.core.interface.inline import InlineModelAdmin
from freeadmin.core.interface.site import AdminSite
from freeadmin.core.network.router import AdminRouter
from freeadmin.core.boot import admin as boot_admin
from freeadmin.core.interface.auth import admin_auth_service
from freeadmin.core.interface.permissions import permission_checker
from freeadmin.core.interface.services.permissions import PermAction
from tests.system_models import system_models


class Parent(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)


class Child(models.Model):
    id = fields.IntField(pk=True)
    parent = fields.ForeignKeyField("models.Parent", related_name="children")
    name = fields.CharField(max_length=50)


class ChildInline(InlineModelAdmin):
    model = Child
    parent_fk_name = "parent"
    list_display = ("name",)


class ParentAdmin(ModelAdmin):
    model = Parent
    inlines = (ChildInline,)


class ChildAdmin(ModelAdmin):
    model = Child


class TestInlineAdmin:
    class PermissionStub:
        async def __call__(self, request: Request) -> None:  # pragma: no cover - simple stub
            return None

    class PermsStub:
        def __init__(self) -> None:
            self.deps: dict[PermAction, TestInlineAdmin.PermissionStub] = {}

        def require_model(self, perm, app_value=None, model_value=None, **kwargs):
            dep = TestInlineAdmin.PermissionStub()
            self.deps[perm] = dep
            return dep

    PermissionStub.__call__.__annotations__["request"] = Request

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
        cls.site.register("models", Parent, ParentAdmin)
        cls.site.register("models", Child, ChildAdmin)
        asyncio.run(cls.site.finalize())
        cls.perms_stub = cls.PermsStub()
        cls._orig_perm = permission_checker.require_model
        permission_checker.require_model = cls.perms_stub.require_model
        cls.user = SimpleNamespace(is_superuser=True)

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

    def test_get_inlines_returns_metadata(self) -> None:
        parent = asyncio.run(Parent.create(name="p1"))
        asyncio.run(Child.create(parent=parent, name="c1"))
        resp = self.client.get(f"/admin/orm/models/parent/{parent.id}/_inlines")
        assert resp.status_code == 200
        spec = resp.json()[0]
        assert spec["app"] == Parent.__module__.split(".")[0]
        assert spec["model"] == "child"
        assert spec["parent_fk"] == "parent"
        assert spec["columns"] == ["name"]
        assert spec["count"] == 1

    def test_force_fk_header_on_create(self) -> None:
        parent = asyncio.run(Parent.create(name="p2"))
        resp = self.client.post(
            "/admin/orm/models/child",
            json={"name": "forced", "parent": 0},
            headers={"X-Force-FK-parent": str(parent.id)},
        )
        assert resp.status_code == 200
        child_id = resp.json()["id"]

        async def _fetch(pk: int) -> Child:
            return await Child.get(id=pk)

        child = asyncio.run(_fetch(child_id))
        assert child.parent_id == parent.id

    def test_inline_badge_updates_after_add_delete(self) -> None:
        parent = asyncio.run(Parent.create(name="p3"))
        resp = self.client.get(f"/admin/orm/models/parent/{parent.id}/_inlines")
        assert resp.status_code == 200
        assert resp.json()[0]["count"] == 0
        resp_add = self.client.post(
            "/admin/orm/models/child",
            json={"name": "c1"},
            headers={"X-Force-FK-parent": str(parent.id)},
        )
        assert resp_add.status_code == 200
        child_id = resp_add.json()["id"]
        resp = self.client.get(f"/admin/orm/models/parent/{parent.id}/_inlines")
        assert resp.json()[0]["count"] == 1
        resp_del = self.client.delete(f"/admin/orm/models/child/{child_id}")
        assert resp_del.status_code == 200
        resp = self.client.get(f"/admin/orm/models/parent/{parent.id}/_inlines")
        assert resp.json()[0]["count"] == 0

    def test_edit_page_renders_inline_container(self) -> None:
        """Ensure the edit form loads with inline host markup and assets."""

        parent = asyncio.run(Parent.create(name="p4"))

        resp = self.client.get(f"/admin/orm/models/parent/{parent.id}/edit")
        assert resp.status_code == 200
        html = resp.text
        assert "id=\"inline-root\"" in html
        assert "admin-form.js" in html

        inline_resp = self.client.get(
            f"/admin/orm/models/parent/{parent.id}/_inlines"
        )
        assert inline_resp.status_code == 200
        assert inline_resp.json() != []


# The End

