# -*- coding: utf-8 -*-
"""
middleware

Admin app-level middleware.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from config.settings import settings
from contrib.admin.models.users import AdminUser as AdminUserORM

from .core.settings import SettingsKey, system_config


class AdminGuardMiddleware(BaseHTTPMiddleware):
    """Global guard for the admin interface.

    Performs 307 redirects to /<prefix>/setup if no superuser exists
    and to /<prefix>/login if there is no valid session.
    """

    def __init__(self, app):
        super().__init__(app)
        self.prefix = settings.ADMIN_PATH.rstrip("/")
        self._login_path: str | None = None
        self._logout_path: str | None = None
        self._setup_path: str | None = None
        self._static_path: str | None = None
        self._session_key: str | None = None
        self._has_superuser: bool | None = None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if not path.startswith(self.prefix):
            return await call_next(request)

        rel = path[len(self.prefix) :] or "/"

        if self._login_path is None:
            self._login_path = await system_config.get(SettingsKey.LOGIN_PATH)
            self._logout_path = await system_config.get(SettingsKey.LOGOUT_PATH)
            self._setup_path = await system_config.get(SettingsKey.SETUP_PATH)
            self._static_path = await system_config.get(SettingsKey.STATIC_PATH)
            self._session_key = await system_config.get(SettingsKey.SESSION_KEY)

        assert (
            self._login_path is not None
            and self._logout_path is not None
            and self._setup_path is not None
            and self._static_path is not None
            and self._session_key is not None
        )

        login_path = self._login_path
        logout_path = self._logout_path
        setup_path = self._setup_path
        static_path = self._static_path
        session_key = self._session_key

        if (
            rel.startswith(login_path)
            or rel.startswith(logout_path)
            or rel.startswith(setup_path)
            or rel.startswith(static_path)
        ):
            return await call_next(request)

        if self._has_superuser is not True:
            self._has_superuser = await AdminUserORM.filter(
                is_staff=True, is_superuser=True
            ).exists()
        if not self._has_superuser:
            return RedirectResponse(f"{self.prefix}{setup_path}", status_code=307)

        user_id = request.session.get(session_key)
        if not user_id:
            return RedirectResponse(f"{self.prefix}{login_path}", status_code=307)

        user = await AdminUserORM.get_or_none(id=user_id)
        if not user or not user.is_active or not user.is_staff:
            return RedirectResponse(f"{self.prefix}{login_path}", status_code=307)

        request.state.user = user
        return await call_next(request)

# The End
