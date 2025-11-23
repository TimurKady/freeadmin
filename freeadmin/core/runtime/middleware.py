# -*- coding: utf-8 -*-
"""
middleware

Admin app-level middleware.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from ..configuration.conf import (
    FreeAdminSettings,
    current_settings,
    register_settings_observer,
)
from ..interface.settings import SettingsKey, system_config


class AdminGuardMiddleware(BaseHTTPMiddleware):
    """Global guard for the admin interface.

    Performs 307 redirects to /<prefix>/setup if no superuser exists
    and to /<prefix>/login if there is no valid session.
    """

    def __init__(
        self,
        app,
        *,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        super().__init__(app)
        self._settings = settings or current_settings()
        self._login_path: str | None = None
        self._logout_path: str | None = None
        self._setup_path: str | None = None
        self._static_path: str | None = None
        self._migrations_path: str | None = None
        self._session_key: str | None = None
        self._has_superuser: bool | None = None
        register_settings_observer(self._apply_settings)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        from freeadmin.core.boot import admin as boot_admin

        path = request.url.path
        if not path.startswith(self.prefix):
            return await call_next(request)

        rel = path[len(self.prefix) :] or "/"

        login_path = await system_config.get_or_default(SettingsKey.LOGIN_PATH)
        logout_path = await system_config.get_or_default(SettingsKey.LOGOUT_PATH)
        setup_path = await system_config.get_or_default(SettingsKey.SETUP_PATH)
        static_path = await system_config.get_or_default(SettingsKey.STATIC_PATH)
        migrations_path = await system_config.get_or_default(
            SettingsKey.MIGRATIONS_PATH
        )
        session_key = await system_config.get_or_default(SettingsKey.SESSION_KEY)

        # Persist the most recently observed values for debugging and tests.
        self._login_path = login_path
        self._logout_path = logout_path
        self._setup_path = setup_path
        self._static_path = static_path
        self._migrations_path = migrations_path
        self._session_key = session_key

        if system_config.migrations_required and not (
            rel.startswith(migrations_path) or rel.startswith(static_path)
        ):
            return RedirectResponse(
                f"{self.prefix}{migrations_path}", status_code=307
            )

        if (
            rel.startswith(login_path)
            or rel.startswith(logout_path)
            or rel.startswith(setup_path)
            or rel.startswith(static_path)
            or rel.startswith(migrations_path)
        ):
            return await call_next(request)

        if self._has_superuser is not True:
            qs = boot_admin.adapter.filter(
                boot_admin.adapter.user_model, is_staff=True, is_superuser=True
            )
            self._has_superuser = await boot_admin.adapter.exists(qs)
        if not self._has_superuser:
            return RedirectResponse(f"{self.prefix}{setup_path}", status_code=307)

        user_id = request.session.get(session_key)
        if not user_id:
            return RedirectResponse(f"{self.prefix}{login_path}", status_code=307)

        user = await boot_admin.adapter.get_or_none(
            boot_admin.adapter.user_model, id=user_id
        )
        if not user or not user.is_active or not user.is_staff:
            return RedirectResponse(f"{self.prefix}{login_path}", status_code=307)

        request.state.user = user
        return await call_next(request)

    def _apply_settings(self, settings: FreeAdminSettings) -> None:
        """Refresh cached prefix and settings after reconfiguration."""
        self._settings = settings

    @property
    def prefix(self) -> str:
        """Return the active admin prefix sourced from runtime settings."""

        return system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, self._settings.admin_path
        ).rstrip("/")

# The End

