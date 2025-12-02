# -*- coding: utf-8 -*-
"""
permissions

Permission checks based on flat user/group tables.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from fastapi.requests import Request

# IMPORTANT: path to your user model
from ..models.users import AdminUser  # ← adjust for your project
from ..models.rbac import AdminUserPermission, AdminGroupPermission, PermAction


logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from .auth import AdminUserDTO
    from .site import AdminSite


def require_model_permission(
    action: PermAction,
    app_param: str = "app",
    model_param: str = "model",
    app_value: str | None = None,
    model_value: str | None = None,
    admin_site: "AdminSite | None" = None,
):
    """Dependency ensuring user has ``action`` permission on a model.

    ``app`` and ``model`` may be provided as path or query parameters.
    Alternatively ``app_value`` and ``model_value`` can explicitly define the
    target model. Returns the current user as ``AdminUserDTO`` when permission
    check passes.
    """

    async def _dep(request: Request) -> "AdminUserDTO":
        from .auth import get_current_admin_user

        site = admin_site or getattr(request.app.state, "admin_site", None)
        if site is None:
            raise HTTPException(status_code=500, detail="Admin site not configured")

        user_dto = await get_current_admin_user(request)
        orm_user: AdminUser = request.state.user

        from urllib.parse import parse_qs

        qs = parse_qs(request.scope.get("query_string", b"").decode())
        app = app_value or request.path_params.get(app_param) or qs.get(app_param, [None])[0]
        model = model_value or request.path_params.get(model_param) or qs.get(model_param, [None])[0]
        if not app or not model:
            raise HTTPException(status_code=400, detail="Missing app/model params")

        ct_id = site.get_ct_id(app, model)
        if ct_id is None:
            raise HTTPException(status_code=404, detail=f"Unknown content type: {app}.{model}")

        allowed = False
        if orm_user.is_active and orm_user.is_staff:
            if orm_user.is_superuser:
                allowed = True
            else:
                allowed = await AdminUserPermission.filter(
                    user_id=orm_user.id, content_type_id=ct_id, action=action
                ).exists()
                if not allowed:
                    group_ids = await orm_user.groups.all().values_list("id", flat=True)
                    allowed = await AdminGroupPermission.filter(
                        group_id__in=group_ids, content_type_id=ct_id, action=action
                    ).exists()
        if not allowed:
            logger.debug(
                "Permission denied",
                extra={"user_id": orm_user.id, "ct_id": ct_id, "action": action},
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user_dto

    return _dep


def require_global_permission(action: PermAction):
    """
    Dependency for global pages (Settings, etc.).
    """
    async def _dep(request: Request):
        user: AdminUser | None = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")

        allowed = False
        if user.is_active and user.is_staff:
            if user.is_superuser:
                allowed = True
            else:
                allowed = await AdminUserPermission.filter(
                    user_id=user.id, content_type_id=None, action=action
                ).exists()
                if not allowed:
                    group_ids = await user.groups.all().values_list("id", flat=True)
                    allowed = await AdminGroupPermission.filter(
                        group_id__in=group_ids,
                        content_type_id=None,
                        action=action,
                    ).exists()
        if not allowed:
            logger.debug(
                "Permission denied",
                extra={"user_id": user.id, "ct_id": None, "action": action},
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return None

    return _dep

# The End
