# -*- coding: utf-8 -*-
"""
core.templates.rendering

Helper utilities for rendering FreeAdmin templates outside the admin UI.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from fastapi import Request
from fastapi.responses import HTMLResponse

from . import service as template_service_module
from .service import TemplateService
from ..settings import SettingsKey, system_config
from freeadmin.core.configuration.conf import current_settings


class TemplateRenderer:
    """Provide cached access to FreeAdmin templates for public pages."""

    logger = logging.getLogger(__name__)
    _service: TemplateService | None = template_service_module.DEFAULT_TEMPLATE_SERVICE

    @classmethod
    def configure(cls, service: TemplateService) -> None:
        """Replace the template service used by the renderer."""

        cls._service = service

    @classmethod
    def get_service(cls) -> TemplateService:
        """Return the template service backing the renderer."""

        if cls._service is None:
            default_service = template_service_module.DEFAULT_TEMPLATE_SERVICE
            if default_service is not None:
                cls._service = default_service
            else:
                cls._service = TemplateService()
        return cls._service

    @classmethod
    def render(
        cls,
        template_name: str,
        context: Mapping[str, Any],
        *,
        request: Request | None = None,
    ) -> HTMLResponse:
        """Render ``template_name`` with ``context`` using FreeAdmin templates."""

        final_context = dict(context)
        if request is not None:
            final_context.setdefault("request", request)
        if "request" not in final_context:
            raise ValueError("Template context must include a 'request' key.")
        templates = cls.get_service().get_templates()
        if cls.logger.isEnabledFor(logging.INFO):
            cls.logger.info(
                "Rendering template response",
                extra={
                    "template": template_name,
                    "path": str(getattr(getattr(request, "url", None), "path", "")),
                },
            )
        return templates.TemplateResponse(template_name, final_context)


class PageTemplateResponder:
    """Render FreeAdmin page templates with standardised context defaults."""

    logger = logging.getLogger(__name__)

    @classmethod
    def render(
        cls,
        template_name: str,
        *,
        request: Request,
        context: Mapping[str, Any] | None = None,
        title: str | None = None,
    ) -> HTMLResponse:
        """Render ``template_name`` using ``context`` and injected defaults."""

        payload = dict(context or {})
        payload.setdefault("request", request)
        payload.setdefault("user", getattr(request.state, "user", None))
        if title is not None:
            payload.setdefault("title", title)
            payload.setdefault("page_title", title)

        defaults = cls._build_default_context(request)
        for key, value in defaults.items():
            payload.setdefault(key, value)

        if cls.logger.isEnabledFor(logging.DEBUG):
            cls.logger.debug(
                "Page template responder merged context",
                extra={
                    "template": template_name,
                    "title": title,
                    "path": str(request.url.path),
                    "context_keys": sorted(payload.keys()),
                },
            )
        return TemplateRenderer.render(template_name, payload, request=request)

    @classmethod
    def _build_default_context(cls, request: Request) -> dict[str, Any]:
        admin_site = getattr(getattr(request.app, "state", object()), "admin_site", None)
        settings_obj = getattr(admin_site, "_settings", None)
        if settings_obj is None:
            settings_obj = current_settings()

        admin_prefix = cls._normalize_prefix(
            system_config.get_cached(
                SettingsKey.ADMIN_PREFIX,
                getattr(settings_obj, "admin_path", "/admin"),
            )
        )
        public_prefix = cls._normalize_prefix(
            system_config.get_cached(SettingsKey.PUBLIC_PREFIX, "/"),
            allow_root=True,
        )
        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")

        request_path = request.url.path or "/"
        is_admin_request = cls._is_admin_request(request_path, admin_prefix)
        active_prefix = admin_prefix if is_admin_request else public_prefix
        if not active_prefix:
            active_prefix = "/"

        if admin_site is not None:
            site_title = admin_site.title
            brand_icon = admin_site.brand_icon
            menu_builder = getattr(admin_site, "public_menu_builder", None)
        else:
            site_title = system_config.get_cached(
                SettingsKey.DEFAULT_ADMIN_TITLE,
                getattr(settings_obj, "admin_site_title", "FreeAdmin"),
            )
            brand_icon = system_config.get_cached(
                SettingsKey.BRAND_ICON,
                getattr(settings_obj, "brand_icon", None),
            )
            menu_builder = None

        public_menu = []
        if menu_builder is not None:
            public_menu = menu_builder.build_menu(prefix=public_prefix)

        return {
            "prefix": active_prefix,
            "admin_prefix": admin_prefix or "/",
            "public_prefix": public_prefix or "/",
            "is_admin_request": is_admin_request,
            "ORM_PREFIX": orm_prefix,
            "SETTINGS_PREFIX": settings_prefix,
            "VIEWS_PREFIX": views_prefix,
            "site_title": site_title,
            "brand_icon": brand_icon,
            "assets": {"css": [], "js": []},
            "system_config": system_config,
            "public_menu": public_menu,
        }

    @staticmethod
    def _normalize_prefix(value: str | None, *, allow_root: bool = False) -> str:
        """Return a normalised prefix ensuring a leading slash."""

        if value is None:
            return "/" if allow_root else ""
        candidate = str(value).strip()
        if not candidate:
            return "/" if allow_root else ""
        if not candidate.startswith("/"):
            candidate = f"/{candidate}"
        if candidate != "/":
            candidate = candidate.rstrip("/")
        if candidate == "/" and not allow_root:
            return ""
        return candidate or "/"

    @staticmethod
    def _is_admin_request(path: str, admin_prefix: str) -> bool:
        """Return ``True`` when ``path`` belongs to the admin namespace."""

        if not admin_prefix or admin_prefix == "/":
            return True
        normalized = admin_prefix.rstrip("/")
        if normalized == "":
            return True
        if path == normalized:
            return True
        return path.startswith(f"{normalized}/")


def render_template(
    template_name: str,
    context: Mapping[str, Any],
    *,
    request: Request | None = None,
) -> HTMLResponse:
    """Render ``template_name`` with ``context`` for use in FastAPI views."""

    return TemplateRenderer.render(template_name, context, request=request)


# The End


