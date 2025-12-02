# -*- coding: utf-8 -*-
"""
api

API endpoints for the admin interface.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from tortoise.exceptions import DoesNotExist

from .adapters.tortoise import get_model_descriptor
from .core.auth import AdminUserDTO
from .core.permissions import PermAction, require_model_permission
from .core.settings import SettingsKey, system_config

class AdminAPI:
    """API endpoints for the admin interface."""

    def __init__(self) -> None:
        self.API_PREFIX = system_config.get_cached(SettingsKey.API_PREFIX, "/api")
        self.SCHEMA_PATH = system_config.get_cached(
            SettingsKey.API_SCHEMA, f"{self.API_PREFIX}/schema"
        )
        self.LIST_FILTERS_PATH = system_config.get_cached(
            SettingsKey.API_LIST_FILTERS, f"{self.API_PREFIX}/list_filters"
        )

        self.router = APIRouter()

        self.router.get(
            self._relative(self.SCHEMA_PATH), name="admin.api.schema"
        )(self.api_schema)
        self.router.get(
            self._relative(self.LIST_FILTERS_PATH), name="admin.api.list_filters"
        )(self.api_list_filters)

    def _relative(self, path: str) -> str:
        """Return a path relative to ``API_PREFIX`` suitable for the router."""

        if path.startswith(self.API_PREFIX):
            path = path[len(self.API_PREFIX) :]
        if not path.startswith("/"):
            path = "/" + path
        return path

    async def api_schema(
        self,
        request: Request,
        app: str,
        model: str,
        mode: Literal["add", "edit"] = "add",
        pk: str | None = None,
        user: AdminUserDTO = Depends(require_model_permission(PermAction.view)),
    ):
        admin_site = request.app.state.admin_site
        admin = admin_site.find_admin_or_404(app, model)

        md = get_model_descriptor(admin.model)

        obj = None
        if mode == "edit" and pk is not None:
            qs = admin.get_objects(request, user)
            try:
                obj = await qs.get(**{md.pk_attr: pk})
            except DoesNotExist:
                raise HTTPException(status_code=404)

        schema_data = await admin.get_schema(request, user, md, mode, obj=obj)

        return {
            "schema": schema_data["schema"],
            "startval": schema_data["startval"],
        }

    async def api_list_filters(
        self,
        request: Request,
        app: str,
        model: str,
        user: AdminUserDTO = Depends(require_model_permission(PermAction.view)),
    ):
        admin_site = request.app.state.admin_site
        admin = admin_site.find_admin_or_404(app, model)
        md = get_model_descriptor(admin.model)

        return {"filters": admin.get_list_filters(md)}

_api = AdminAPI()
router = _api.router
API_PREFIX = _api.API_PREFIX

__all__ = ["router", "API_PREFIX"]

# The End
