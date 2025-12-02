# -*- coding: utf-8 -*-
"""
auth

Authentication utilities for the admin site.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, TYPE_CHECKING
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..models.rbac import (
    AdminGroupPermission,
    AdminUserPermission,
    PermAction,
)
from .auth_service import authenticate_user, create_superuser, superuser_exists
from config.settings import settings
from .settings import SettingsKey, system_config

if TYPE_CHECKING:  # pragma: no cover
    from .site import AdminSite

@dataclass
class AdminUserDTO:
    id: str
    username: str
    email: str = ""
    is_staff: bool = False
    is_superuser: bool = False
    is_active: bool = True

async def get_current_admin_user(request: Request) -> AdminUserDTO:
    user = getattr(request.state, "user", None)
    if not user or not getattr(user, "is_active", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return AdminUserDTO(
        id=str(user.id),
        username=user.username,
        email=getattr(user, "email", "") or "",
        is_staff=bool(getattr(user, "is_staff", False)),
        is_superuser=bool(getattr(user, "is_superuser", False)),
        is_active=True,
    )

def require_permissions(
    codenames: Iterable[str] = (), *, admin_site: "AdminSite" | None = None
):  # noqa: D401
    """Dependency generator enforcing permission codenames."""

    parsed: list[tuple[str, str, PermAction]] = []
    for codename in codenames:
        try:
            app, model, action = codename.split(".")
            parsed.append((app, model, PermAction(action)))
        except ValueError:
            raise ValueError(f"Invalid codename: {codename}") from None

    async def _dep(
        request: Request, user: AdminUserDTO = Depends(get_current_admin_user)
    ) -> AdminUserDTO:
        if not parsed:
            return user

        site = admin_site or getattr(request.app.state, "admin_site", None)
        if site is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        orm_user = request.state.user
        for app, model, action in parsed:
            ct_id = site.get_ct_id(app, model)
            if ct_id is None:
                raise HTTPException(status_code=404)
            allowed = False
            if orm_user.is_active and orm_user.is_staff:
                if orm_user.is_superuser:
                    allowed = True
                else:
                    allowed = await AdminUserPermission.filter(
                        user_id=orm_user.id,
                        content_type_id=ct_id,
                        action=action,
                    ).exists()
                    if not allowed:
                        group_ids = await orm_user.groups.all().values_list(
                            "id", flat=True
                        )
                        allowed = await AdminGroupPermission.filter(
                            group_id__in=group_ids,
                            content_type_id=ct_id,
                            action=action,
                        ).exists()
            if not allowed:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return user

    return _dep


def build_auth_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()
    login_path = system_config.get_cached(SettingsKey.LOGIN_PATH, "/login")
    logout_path = system_config.get_cached(SettingsKey.LOGOUT_PATH, "/logout")
    setup_path = system_config.get_cached(SettingsKey.SETUP_PATH, "/setup")

    @router.get(login_path)
    async def login_form(request: Request):
        orm_prefix = await system_config.get(SettingsKey.ORM_PREFIX)
        settings_prefix = await system_config.get(SettingsKey.SETTINGS_PREFIX)
        views_prefix = await system_config.get(SettingsKey.VIEWS_PREFIX)
        return templates.TemplateResponse(
            "pages/login.html",
            {
                "request": request,
                "error": None,
                "prefix": settings.ADMIN_PATH,
                "ORM_PREFIX": orm_prefix,
                "SETTINGS_PREFIX": settings_prefix,
                "VIEWS_PREFIX": views_prefix,
            },
        )

    @router.post(login_path)
    async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
        user = await authenticate_user(username, password)
        if not user:
            orm_prefix = await system_config.get(SettingsKey.ORM_PREFIX)
            settings_prefix = await system_config.get(SettingsKey.SETTINGS_PREFIX)
            views_prefix = await system_config.get(SettingsKey.VIEWS_PREFIX)
            return templates.TemplateResponse(
                "pages/login.html",
                {
                    "request": request,
                    "error": "Invalid credentials",
                    "prefix": settings.ADMIN_PATH,
                    "ORM_PREFIX": orm_prefix,
                    "SETTINGS_PREFIX": settings_prefix,
                    "VIEWS_PREFIX": views_prefix,
                },
                status_code=400,
            )
        session_key = await system_config.get(SettingsKey.SESSION_KEY)
        request.session[session_key] = str(user.id)
        return RedirectResponse(f"{settings.ADMIN_PATH}/", status_code=303)

    @router.get(logout_path)
    async def logout(request: Request):
        session_key = await system_config.get(SettingsKey.SESSION_KEY)
        request.session.pop(session_key, None)
        login_path = await system_config.get(SettingsKey.LOGIN_PATH)
        return RedirectResponse(f"{settings.ADMIN_PATH}{login_path}", status_code=303)

    @router.get(setup_path)
    async def setup_form(request: Request):
        if await superuser_exists():
            login_path = await system_config.get(SettingsKey.LOGIN_PATH)
            return RedirectResponse(f"{settings.ADMIN_PATH}{login_path}", status_code=303)
        orm_prefix = await system_config.get(SettingsKey.ORM_PREFIX)
        settings_prefix = await system_config.get(SettingsKey.SETTINGS_PREFIX)
        views_prefix = await system_config.get(SettingsKey.VIEWS_PREFIX)
        return templates.TemplateResponse(
            "pages/setup.html",
            {
                "request": request,
                "error": None,
                "prefix": settings.ADMIN_PATH,
                "ORM_PREFIX": orm_prefix,
                "SETTINGS_PREFIX": settings_prefix,
                "VIEWS_PREFIX": views_prefix,
            },
        )

    @router.post(setup_path)
    async def setup_post(
        request: Request,
        username: str = Form(...),
        email: str = Form(""),
        password: str = Form(...),
    ):
        if await superuser_exists():
            login_path = await system_config.get(SettingsKey.LOGIN_PATH)
            return RedirectResponse(f"{settings.ADMIN_PATH}{login_path}", status_code=303)
        user = await create_superuser(username=username, email=email, password=password)
        session_key = await system_config.get(SettingsKey.SESSION_KEY)
        request.session[session_key] = str(user.id)
        return RedirectResponse(f"{settings.ADMIN_PATH}/", status_code=303)

    return router

# The End
