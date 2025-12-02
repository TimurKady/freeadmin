# -*- coding: utf-8 -*-
"""
crud

Utility for mounting CRUD routes on FastAPI routers.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, TYPE_CHECKING

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from tortoise.exceptions import DoesNotExist, IntegrityError

from .adapters.tortoise import get_model_descriptor
from .core.auth import AdminUserDTO, get_current_admin_user
from .core.base import BaseModelAdmin
from .core.settings import SettingsKey, system_config
if TYPE_CHECKING:
    from .core.site import AdminSite
from .core.permissions import (
    PermAction,
    require_global_permission,
    require_model_permission,
)


class CrudRouterBuilder:
    """Helper to attach standard CRUD routes for admin classes."""

    @staticmethod
    def mount(
        router: APIRouter,
        *,
        admin_site: AdminSite,
        prefix: str,
        admin_cls: type[BaseModelAdmin],
        perms: Literal["model", "global"],
        app_label: str,
        model_name: str,
    ) -> APIRouter:
        """Mount standard CRUD routes for ``admin_cls`` on ``router``.

        ``prefix`` is the base path. ``perms`` controls whether permissions are
        checked against a specific model (``"model"``) or globally
        (``"global"``).
        """

        templates = getattr(router, "templates", None)
        if templates is None:
            base_dir = Path(__file__).resolve().parents[2]
            templates = Jinja2Templates(directory=str(base_dir / "templates"))

        admin = admin_cls(admin_cls.model)

        if perms == "global":
            perm_view = require_global_permission(PermAction.view)
            perm_add = require_global_permission(PermAction.add)
            perm_change = require_global_permission(PermAction.change)
            perm_delete = require_global_permission(PermAction.delete)
        else:
            perm_view = require_model_permission(
                PermAction.view, app_value=app_label, model_value=model_name
            )
            perm_add = require_model_permission(
                PermAction.add, app_value=app_label, model_value=model_name
            )
            perm_change = require_model_permission(
                PermAction.change, app_value=app_label, model_value=model_name
            )
            perm_delete = require_model_permission(
                PermAction.delete, app_value=app_label, model_value=model_name
            )

        md = get_model_descriptor(admin.model)

        @router.get(prefix + "/", response_class=HTMLResponse)
        async def list_page(
            request: Request,
            user: AdminUserDTO = Depends(get_current_admin_user),
            _: None = Depends(perm_view),
        ) -> HTMLResponse:
            can_add = admin.allow(user, "add")
            ctx = admin_site.build_template_ctx(
                request,
                user,
                app_label=app_label,
                model_name=model_name,
                is_settings=(perms == "global"),
                extra={
                    "can_add": can_add,
                    "has_list_filters": bool(admin.get_list_filter()),
                    "has_search": bool(admin.get_search_fields(md)),
                },
            )
            return templates.TemplateResponse("context/list.html", ctx)

        @router.get(prefix + "/add", response_class=HTMLResponse)
        async def add_page(
            request: Request,
            user: AdminUserDTO = Depends(get_current_admin_user),
            _: None = Depends(perm_add),
        ) -> HTMLResponse:
            title = f"Add {admin.get_verbose_name()}"
            ctx = admin_site.build_template_ctx(
                request,
                user,
                page_title=title,
                app_label=app_label,
                model_name=model_name,
                is_settings=(perms == "global"),
            )
            return templates.TemplateResponse("context/form.html", ctx)

        @router.get(prefix + "/{pk}/edit", response_class=HTMLResponse)
        async def edit_page(
            request: Request,
            pk: str,
            user: AdminUserDTO = Depends(get_current_admin_user),
            _: None = Depends(perm_change),
        ) -> HTMLResponse:
            qs = admin.get_objects(request, user)
            try:
                obj = await qs.get(**{md.pk_attr: pk})
            except DoesNotExist:
                raise HTTPException(404)
            title = f"Edit {admin.get_verbose_name()}"
            ctx = admin_site.build_template_ctx(
                request,
                user,
                page_title=title,
                app_label=app_label,
                model_name=model_name,
                is_settings=(perms == "global"),
                extra={"pk": pk},
            )
            return templates.TemplateResponse("context/form.html", ctx)

        # form schema served via global API; no local endpoint

        @router.get(prefix + "/_list")
        async def list_data(
            request: Request,
            search: str = "",
            page_num: int = 1,
            per_page: int | None = None,
            order: str = "",
            user: AdminUserDTO = Depends(get_current_admin_user),
            _: None = Depends(perm_view),
        ):
            columns = admin.get_list_columns(md)
            params: Dict[str, Any] = {"search": search, "order": order}
            qs = admin.get_list_queryset(request, user, md, params)
            order = params.get("order", order)

            if per_page is None:
                per_page = await system_config.get(SettingsKey.DEFAULT_PER_PAGE)
            max_per_page = await system_config.get(SettingsKey.MAX_PER_PAGE)
            per_page = max(1, min(int(per_page), max_per_page))
            page_num = max(1, int(page_num))
            total = await qs.count()
            pages = max(1, (total + per_page - 1) // per_page)
            offset = (page_num - 1) * per_page
            objs = await qs.limit(per_page).offset(offset)
            items = []
            for o in objs:
                row = await admin.serialize_list_row(o, md, columns)
                row["can_change"] = admin.allow(user, "change", o)
                row["can_delete"] = admin.allow(user, "delete", o)
                items.append(row)

            return {
                "columns": columns,
                "columns_meta": admin.columns_meta(md, columns),
                "id_field": md.pk_attr,
                "items": items,
                "page": page_num,
                "pages": pages,
                "per_page": per_page,
                "total": total,
                "order": order,
            }

        @router.post(prefix)
        async def create(
            request: Request,
            payload: dict = Body(...),
            user: AdminUserDTO = Depends(get_current_admin_user),
            _: None = Depends(perm_add),
        ):
            if not admin.allow(user, "add", None):
                raise HTTPException(
                    status_code=403, detail="Add not allowed by business rule",
                )
            try:
                obj = await admin.create(request, user, md, payload)
                return {"ok": True, "id": getattr(obj, md.pk_attr)}
            except IntegrityError as exc:
                raise admin.handle_integrity_error(exc)

        @router.put(prefix + "/{pk}")
        async def update(
            request: Request,
            pk: str,
            payload: dict = Body(...),
            user: AdminUserDTO = Depends(get_current_admin_user),
            _: None = Depends(perm_change),
        ):
            qs = admin.get_objects(request, user)
            try:
                obj = await qs.get(**{md.pk_attr: pk})
            except DoesNotExist:
                raise HTTPException(404)
            if not admin.allow(user, "change", obj):
                raise HTTPException(
                    status_code=403, detail="Change not allowed by business rule",
                )
            try:
                await admin.update(request, user, md, obj, payload)
                return {"ok": True}
            except IntegrityError as exc:
                raise admin.handle_integrity_error(exc)

        @router.delete(prefix + "/{pk}")
        async def delete(
            request: Request,
            pk: str,
            user: AdminUserDTO = Depends(get_current_admin_user),
            _: None = Depends(perm_delete),
        ):
            qs = admin.get_objects(request, user)
            try:
                obj = await qs.get(**{md.pk_attr: pk})
            except DoesNotExist:
                raise HTTPException(404)
            if not admin.allow(user, "delete", obj):
                raise HTTPException(
                    status_code=403, detail="Delete not allowed by business rule",
                )
            delete_method = getattr(admin, "delete", None)
            if delete_method:
                await delete_method(request, user, md, obj)
            else:
                await obj.delete()
            return {"ok": True}

        return router

# The End
