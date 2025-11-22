# -*- coding: utf-8 -*-
"""
context

Template context builder for the admin site.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from fastapi import Request

from freeadmin.core.configuration.conf import current_settings
from .settings import SettingsKey, system_config
from .sidebar import SidebarBuilder

if TYPE_CHECKING:  # pragma: no cover
    from .site import AdminSite


class TemplateContextBuilder:
    """Assemble context dictionaries for admin template rendering."""

    logger = logging.getLogger(__name__)

    def __init__(self, admin_site: "AdminSite") -> None:
        """Store a reference to the admin site used for context building."""
        self._admin_site = admin_site

    def build(
        self,
        request: Request,
        user: Optional[Any],
        *,
        page_title: Optional[str] = None,
        app_label: Optional[str] = None,
        model_name: Optional[str] = None,
        is_settings: Optional[bool] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a populated context dictionary for admin templates."""
        admin_site = self._admin_site
        settings_obj = getattr(admin_site, "_settings", current_settings())
        resolution = admin_site.pages.resolve_request(request)
        if self.logger.isEnabledFor(logging.INFO):
            self.logger.info(
                "Building admin template context",
                extra={
                    "path": str(request.url.path),
                    "user": getattr(getattr(user, "__class__", None), "__name__", None),
                    "section_mode": resolution.section_mode,
                },
            )
        if is_settings is None:
            is_settings = resolution.is_settings
        if app_label is None:
            app_label = resolution.app_label
        if model_name is None:
            model_name = resolution.model_slug

        if not is_settings:
            registry_entries = getattr(admin_site.registry, "view_entries", ())
            has_orm_entries = any(not entry.settings for entry in registry_entries)
            has_settings_entries = any(entry.settings for entry in registry_entries)
            if has_settings_entries and not has_orm_entries:
                is_settings = True
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(
                        "Admin context defaulted to settings section due to missing ORM entries",
                        extra={"path": str(request.url.path)},
                    )

        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")
        admin_prefix = system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, settings_obj.admin_path
        ).rstrip("/")

        trimmed_path = request.url.path
        if admin_prefix and trimmed_path.startswith(admin_prefix):
            trimmed_path = trimmed_path[len(admin_prefix) :]
            if not trimmed_path.startswith("/"):
                trimmed_path = f"/{trimmed_path}"

        normalized_path = resolution.normalized_path
        normalized_views = views_prefix.rstrip("/") or "/"
        normalized_orm = orm_prefix.rstrip("/") or "/"
        normalized_settings = settings_prefix.rstrip("/") or "/"
        is_views_section = resolution.section_mode == "views"
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "Admin request path normalized",
                extra={
                    "trimmed_path": trimmed_path,
                    "normalized_path": normalized_path,
                    "admin_prefix": admin_prefix,
                    "views_prefix": normalized_views,
                    "orm_prefix": normalized_orm,
                    "settings_prefix": normalized_settings,
                    "is_settings": is_settings,
                    "is_views_section": is_views_section,
                },
            )

        apps = SidebarBuilder.build(
            admin_site=admin_site,
            request=request,
            settings_mode=bool(is_settings),
            app_label=app_label,
            model_name=model_name,
        )
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "Sidebar structure built",
                extra={
                    "groups": len(apps),
                    "entries": sum(len(group.get("models", [])) for group in apps),
                    "is_settings": is_settings,
                    "current_app": app_label,
                    "current_model": model_name,
                },
            )
        section_mode = resolution.section_mode if resolution.section_mode else (
            "settings" if is_settings else "orm"
        )
        ctx: Dict[str, Any] = {
            "request": request,
            "user": user,
            "system_config": system_config,
            "site_title": admin_site.title,
            "brand_icon": admin_site.brand_icon,
            "prefix": admin_prefix,
            "ORM_PREFIX": orm_prefix,
            "SETTINGS_PREFIX": settings_prefix,
            "VIEWS_PREFIX": views_prefix,
            "apps": apps,
            "current_app": app_label,
            "current_model": model_name,
            "section_mode": section_mode,
            "assets": {"css": [], "js": []},
        }
        if page_title is not None:
            ctx["page_title"] = page_title
        if extra:
            ctx.update(extra)

        static_segment = system_config.get_cached(
            SettingsKey.STATIC_URL_SEGMENT, settings_obj.static_url_segment
        )
        scripts, styles = admin_site._collect_card_assets(
            ctx,
            prefix=admin_prefix,
            static_segment=static_segment,
        )
        assets_map = ctx.get("assets")
        if isinstance(assets_map, dict):
            assets_map["js"] = list(scripts)
            assets_map["css"] = list(styles)
        else:
            ctx["assets"] = {"js": list(scripts), "css": list(styles)}
        if self.logger.isEnabledFor(logging.INFO):
            self.logger.info(
                "Admin template context built",
                extra={
                    "path": str(request.url.path),
                    "section_mode": section_mode,
                    "assets_js": len(ctx.get("assets", {}).get("js", [])),
                    "assets_css": len(ctx.get("assets", {}).get("css", [])),
                    "apps": len(apps),
                },
            )
        return ctx


# The End
