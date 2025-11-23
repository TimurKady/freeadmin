# -*- coding: utf-8 -*-
"""
auth

Service utilities for admin authentication.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, TYPE_CHECKING

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import secrets
from itsdangerous import BadSignature, URLSafeTimedSerializer

from ....contrib.adapters import BaseAdapter
from ....utils.passwords import password_hasher
from ....utils.icon import IconPathMixin
from freeadmin.config import (
    FreeAdminSettings,
    current_settings,
    register_settings_observer,
)
from ..settings import SettingsKey, system_config

if TYPE_CHECKING:  # pragma: no cover
    from ..site import AdminSite


@dataclass
class AdminUserDTO:
    """Data transfer object representing an admin user."""

    id: str
    username: str
    email: str = ""
    is_staff: bool = False
    is_superuser: bool = False
    is_active: bool = True
    permissions: set[str] = field(default_factory=set)


class CSRFTokenManager:
    """Simple CSRF token generator and validator."""

    def __init__(self, secret: str) -> None:
        """Initialize the token manager with a secret."""
        self._serializer = URLSafeTimedSerializer(secret, salt="admin-csrf")

    def generate(self, request: Request) -> str:
        """Generate and store a CSRF token."""
        token = secrets.token_urlsafe()
        signed = self._serializer.dumps(token)
        request.session["_csrf_token"] = signed
        return signed

    def validate(self, request: Request, token: str) -> bool:
        """Validate a CSRF token retrieved from the session."""
        expected = request.session.get("_csrf_token")
        if not expected:
            return False
        try:
            token_val = self._serializer.loads(token, max_age=3600)
            expected_val = self._serializer.loads(expected, max_age=3600)
        except BadSignature:
            return False
        return secrets.compare_digest(token_val, expected_val)


class AuthService:
    """Authentication service using a provided adapter."""

    def __init__(self, adapter: BaseAdapter) -> None:
        self.adapter = adapter
        self.user_model = adapter.user_model

    async def authenticate_user(self, username: str, password: str) -> Any | None:
        """Return user if credentials are valid."""
        user = await self.adapter.get_or_none(self.user_model, username=username)
        if (
            not user
            or not getattr(user, "is_active", False)
            or not getattr(user, "is_staff", False)
            or not await password_hasher.check_password(password, user.password)
        ):
            return None
        return user

    async def superuser_exists(self) -> bool:
        """Check if a superuser already exists."""
        queryset = self.adapter.filter(
            self.user_model,
            is_staff=True,
            is_superuser=True,
        )
        return await self.adapter.exists(queryset)

    async def create_superuser(self, username: str, email: str, password: str) -> Any:
        """Create a new superuser."""
        return await self.adapter.create(
            self.user_model,
            username=username,
            email=email,
            password=await password_hasher.make_password(password),
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )


class AdminAuthService(IconPathMixin):
    """Authentication helpers for the admin site."""

    def __init__(
        self,
        auth_service: AuthService,
        adapter: BaseAdapter,
        *,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        """Initialize with authentication backend and data adapter."""
        self.auth_service = auth_service
        self.adapter = adapter
        self.AdminUserPermission = adapter.user_permission_model
        self.AdminGroupPermission = adapter.group_permission_model
        self.PermAction = adapter.perm_action
        self._settings = settings or current_settings()
        self._csrf = CSRFTokenManager(self._settings.csrf_secret)
        register_settings_observer(self._apply_settings)

    @property
    def site_title(self) -> str:
        """Return the admin site title."""
        return system_config.get_cached(
            SettingsKey.DEFAULT_ADMIN_TITLE, self._settings.admin_site_title
        )

    @property
    def brand_icon(self) -> str:
        """Return URL to the brand icon."""
        icon_path = system_config.get_cached(
            SettingsKey.BRAND_ICON, self._settings.brand_icon
        )
        prefix = system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, self._settings.admin_path
        )
        static_segment = system_config.get_cached(
            SettingsKey.STATIC_URL_SEGMENT, self._settings.static_url_segment
        )
        return self._resolve_icon_path(icon_path, prefix, static_segment)

    def _apply_settings(self, settings: FreeAdminSettings) -> None:
        """Update cached configuration and refresh CSRF secret."""
        self._settings = settings
        self._csrf = CSRFTokenManager(self._settings.csrf_secret)

    async def get_current_admin_user(self, request: Request) -> AdminUserDTO:
        """Retrieve the current admin user from the request state."""
        user = getattr(request.state, "user", None)
        if not user or not getattr(user, "is_active", False):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        perms: set[str] = set()
        if user.is_staff and not user.is_superuser:
            user_perm_qs = self.adapter.filter(
                self.AdminUserPermission, user_id=user.id
            )
            user_perm_qs = self.adapter.prefetch_related(
                user_perm_qs, "content_type"
            )
            user_perms = await self.adapter.fetch_values(
                user_perm_qs, "content_type__dotted", "action"
            )
            for dotted, action in user_perms:
                if dotted:
                    perms.add(f"{str(dotted).lower()}.{str(action)}")
                else:
                    perms.add(str(action))
            group_ids = await self.adapter.fetch_values(
                self.adapter.filter(user.groups), "id", flat=True
            )
            if group_ids:
                group_perm_qs = self.adapter.filter(
                    self.AdminGroupPermission, group_id__in=group_ids
                )
                group_perm_qs = self.adapter.prefetch_related(
                    group_perm_qs, "content_type"
                )
                group_perms = await self.adapter.fetch_values(
                    group_perm_qs, "content_type__dotted", "action"
                )
                for dotted, action in group_perms:
                    if dotted:
                        perms.add(f"{str(dotted).lower()}.{str(action)}")
                    else:
                        perms.add(str(action))
        return AdminUserDTO(
            id=str(user.id),
            username=user.username,
            email=getattr(user, "email", "") or "",
            is_staff=bool(getattr(user, "is_staff", False)),
            is_superuser=bool(getattr(user, "is_superuser", False)),
            is_active=True,
            permissions=perms,
        )

    def require_permissions(
        self, codenames: Iterable[str] = (), *, admin_site: "AdminSite" | None = None
    ):
        """Dependency generator enforcing permission codenames."""

        parsed: list[tuple[str, str, "PermAction"]] = []
        for codename in codenames:
            try:
                app, model, action = codename.split(".")
                parsed.append((app, model, self.PermAction(action)))
            except ValueError:
                raise ValueError(f"Invalid codename: {codename}") from None

        async def _dep(
            request: Request, user: AdminUserDTO = Depends(self.get_current_admin_user)
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
                        allowed = await self.adapter.exists(
                            self.adapter.filter(
                                self.AdminUserPermission,
                                user_id=orm_user.id,
                                content_type_id=ct_id,
                                action=action,
                            )
                        )
                        if not allowed:
                            group_ids = await self.adapter.fetch_values(
                                self.adapter.filter(orm_user.groups),
                                "id",
                                flat=True,
                            )
                            allowed = await self.adapter.exists(
                                self.adapter.filter(
                                    self.AdminGroupPermission,
                                    group_id__in=group_ids,
                                    content_type_id=ct_id,
                                    action=action,
                                )
                            )
                if not allowed:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
            return user

        return _dep

    async def logout(self, request: Request) -> RedirectResponse:
        """Log out the current user and clear session."""

        request.session.clear()
        admin_prefix = await system_config.get(SettingsKey.ADMIN_PREFIX)
        login_path = await system_config.get(SettingsKey.LOGIN_PATH)
        response = RedirectResponse(
            f"{admin_prefix}{login_path}", status_code=303
        )
        cookie_name = await system_config.get(SettingsKey.SESSION_COOKIE)
        response.delete_cookie(cookie_name)
        return response

    def build_auth_router(self, templates: Jinja2Templates) -> APIRouter:
        """Construct authentication routes for the admin site."""
        router = APIRouter()
        login_path = system_config.get_cached(SettingsKey.LOGIN_PATH, "/login")
        logout_path = system_config.get_cached(SettingsKey.LOGOUT_PATH, "/logout")
        setup_path = system_config.get_cached(SettingsKey.SETUP_PATH, "/setup")
        admin_prefix = system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, self._settings.admin_path
        )

        @router.get(login_path, response_class=HTMLResponse)
        async def login_form(request: Request):
            orm_prefix = await system_config.get(SettingsKey.ORM_PREFIX)
            settings_prefix = await system_config.get(SettingsKey.SETTINGS_PREFIX)
            views_prefix = await system_config.get(SettingsKey.VIEWS_PREFIX)
            token = self._csrf.generate(request)
            return templates.TemplateResponse(
                "pages/login.html",
                {
                    "request": request,
                    "error": None,
                    "prefix": admin_prefix,
                    "ORM_PREFIX": orm_prefix,
                    "SETTINGS_PREFIX": settings_prefix,
                    "VIEWS_PREFIX": views_prefix,
                    "site_title": self.site_title,
                    "brand_icon": self.brand_icon,
                    "csrf_token": token,
                },
            )

        @router.post(login_path, response_class=HTMLResponse)
        async def login_post(
            request: Request,
            username: str = Form(...),
            password: str = Form(...),
            csrf_token: str = Form(...),
        ):
            if not self._csrf.validate(request, csrf_token):
                orm_prefix = await system_config.get(SettingsKey.ORM_PREFIX)
                settings_prefix = await system_config.get(SettingsKey.SETTINGS_PREFIX)
                views_prefix = await system_config.get(SettingsKey.VIEWS_PREFIX)
                token = self._csrf.generate(request)
                return templates.TemplateResponse(
                    "pages/login.html",
                    {
                        "request": request,
                        "error": "Invalid CSRF token",
                        "prefix": admin_prefix,
                        "ORM_PREFIX": orm_prefix,
                        "SETTINGS_PREFIX": settings_prefix,
                        "VIEWS_PREFIX": views_prefix,
                        "site_title": self.site_title,
                        "brand_icon": self.brand_icon,
                        "csrf_token": token,
                    },
                    status_code=400,
                )
            user = await self.auth_service.authenticate_user(username, password)
            if not user:
                orm_prefix = await system_config.get(SettingsKey.ORM_PREFIX)
                settings_prefix = await system_config.get(SettingsKey.SETTINGS_PREFIX)
                views_prefix = await system_config.get(SettingsKey.VIEWS_PREFIX)
                token = self._csrf.generate(request)
                return templates.TemplateResponse(
                    "pages/login.html",
                    {
                        "request": request,
                        "error": "Invalid credentials",
                        "prefix": admin_prefix,
                        "ORM_PREFIX": orm_prefix,
                        "SETTINGS_PREFIX": settings_prefix,
                        "VIEWS_PREFIX": views_prefix,
                        "site_title": self.site_title,
                        "brand_icon": self.brand_icon,
                        "csrf_token": token,
                    },
                    status_code=400,
                )
            session_key = await system_config.get(SettingsKey.SESSION_KEY)
            request.session[session_key] = str(user.id)
            return RedirectResponse(f"{admin_prefix}/", status_code=303)

        router.get(logout_path)(self.logout)

        @router.get(setup_path)
        async def setup_form(request: Request):
            if await self.auth_service.superuser_exists():
                login_path = await system_config.get(SettingsKey.LOGIN_PATH)
                return RedirectResponse(
                    f"{admin_prefix}{login_path}", status_code=303
                )
            orm_prefix = await system_config.get(SettingsKey.ORM_PREFIX)
            settings_prefix = await system_config.get(SettingsKey.SETTINGS_PREFIX)
            views_prefix = await system_config.get(SettingsKey.VIEWS_PREFIX)
            token = self._csrf.generate(request)
            return templates.TemplateResponse(
                "pages/setup.html",
                {
                    "request": request,
                    "error": None,
                    "prefix": admin_prefix,
                    "ORM_PREFIX": orm_prefix,
                    "SETTINGS_PREFIX": settings_prefix,
                    "VIEWS_PREFIX": views_prefix,
                    "site_title": self.site_title,
                    "brand_icon": self.brand_icon,
                    "csrf_token": token,
                },
            )

        @router.post(setup_path)
        async def setup_post(
            request: Request,
            username: str = Form(...),
            email: str = Form(""),
            password: str = Form(...),
            csrf_token: str = Form(...),
        ):
            if not self._csrf.validate(request, csrf_token):
                orm_prefix = await system_config.get(SettingsKey.ORM_PREFIX)
                settings_prefix = await system_config.get(SettingsKey.SETTINGS_PREFIX)
                views_prefix = await system_config.get(SettingsKey.VIEWS_PREFIX)
                token = self._csrf.generate(request)
                return templates.TemplateResponse(
                    "pages/setup.html",
                    {
                        "request": request,
                        "error": "Invalid CSRF token",
                        "prefix": admin_prefix,
                        "ORM_PREFIX": orm_prefix,
                        "SETTINGS_PREFIX": settings_prefix,
                        "VIEWS_PREFIX": views_prefix,
                        "site_title": self.site_title,
                        "brand_icon": self.brand_icon,
                        "csrf_token": token,
                    },
                    status_code=400,
                )
            if await self.auth_service.superuser_exists():
                login_path = await system_config.get(SettingsKey.LOGIN_PATH)
                return RedirectResponse(
                    f"{admin_prefix}{login_path}", status_code=303
                )
            user = await self.auth_service.create_superuser(
                username=username, email=email, password=password
            )
            session_key = await system_config.get(SettingsKey.SESSION_KEY)
            request.session[session_key] = str(user.id)
            return RedirectResponse(f"{admin_prefix}/", status_code=303)

        return router

# The End

