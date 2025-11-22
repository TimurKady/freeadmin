# -*- coding: utf-8 -*-
"""
sidebar

Utilities for building sidebar data for the admin site.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from fastapi import Request

from freeadmin.core.configuration.conf import current_settings
from .settings import SettingsKey, system_config

if TYPE_CHECKING:  # pragma: no cover
    from .site import AdminSite


class SidebarBuilder:
    """Assemble sidebar entries for models and registered views."""

    KIND_APPS = "apps"
    KIND_VIEWS = "views"

    @classmethod
    def collect(cls, admin_site: "AdminSite", kind: str, settings: bool) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """Return grouped sidebar entries for the requested ``kind``."""

        if kind == cls.KIND_APPS:
            return cls._collect_apps(admin_site, settings)
        if kind == cls.KIND_VIEWS:
            return cls._collect_views(admin_site, settings)
        raise ValueError(f"Unsupported sidebar collection kind: {kind}")

    @classmethod
    def build(
        cls,
        admin_site: "AdminSite",
        request: Request,
        settings_mode: bool,
        app_label: str | None,
        model_name: str | None,
    ) -> List[Dict[str, Any]]:
        """Return final sidebar structure for template consumption."""

        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")
        settings_obj = getattr(admin_site, "_settings", current_settings())
        admin_prefix = system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, settings_obj.admin_path
        ).rstrip("/")

        resolution = admin_site.pages.resolve_request(request)
        normalized_path = resolution.normalized_path
        normalized_views = cls._normalize_prefix(views_prefix)
        normalized_orm = cls._normalize_prefix(orm_prefix)
        normalized_settings = cls._normalize_prefix(settings_prefix)
        views_segments = cls._split_prefix(normalized_views)
        orm_segments = cls._split_prefix(normalized_orm)
        settings_segments = cls._split_prefix(normalized_settings)

        raw_apps = cls.collect(admin_site, cls.KIND_APPS, settings_mode)
        view_groups = cls.collect(admin_site, cls.KIND_VIEWS, settings_mode)

        combined: Dict[str, List[Dict[str, Any]]] = {label: list(models) for label, models in raw_apps}
        for label, entries in view_groups:
            for entry in entries:
                cls._synchronize_view_model_name(
                    entry,
                    views_segments=views_segments,
                    orm_segments=orm_segments,
                    settings_segments=settings_segments,
                )
            combined.setdefault(label, []).extend(entries)

        combined_items: List[Tuple[str, List[Dict[str, Any]]]] = []
        for label, models in combined.items():
            models.sort(key=lambda item: item["display_name"].lower())
            combined_items.append((label, models))
        combined_items.sort(key=lambda item: item[0].lower())

        return [
            {
                "label": label,
                "display": admin_site._format_app_label(label),
                "models": models,
            }
            for label, models in combined_items
        ]

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        cleaned = prefix if prefix.startswith("/") else f"/{prefix}"
        return cleaned.rstrip("/") or "/"

    @classmethod
    def _collect_apps(
        cls, admin_site: "AdminSite", settings: bool
    ) -> List[Tuple[str, List[Dict[str, Any]]]]:
        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        apps: Dict[str, List[Dict[str, Any]]] = {}
        for entry in admin_site.registry.view_entries:
            if settings and not entry.settings:
                continue
            if not settings and entry.settings:
                continue
            arr = apps.setdefault(entry.app, [])
            admin = admin_site.model_reg.get((entry.app.lower(), entry.model.lower()))
            display = (
                admin.get_verbose_name_plural()
                if admin is not None
                else entry.name or entry.model.replace("_", " ").title()
            )
            arr.append(
                {
                    "model_name": entry.model,
                    "display_name": display,
                    "path": (settings_prefix if entry.settings else orm_prefix)
                    + f"/{entry.app}/{entry.model}",
                    "icon": entry.icon,
                    "settings": entry.settings,
                }
            )
        out: List[Tuple[str, List[Dict[str, Any]]]] = []
        for app_label, models in apps.items():
            models.sort(key=lambda model: model["display_name"].lower())
            out.append((app_label, models))
        out.sort(key=lambda item: item[0].lower())
        return out

    @classmethod
    def _collect_views(
        cls, admin_site: "AdminSite", settings: bool
    ) -> List[Tuple[str, List[Dict[str, Any]]]]:
        return admin_site.pages.iter_sidebar_views(settings=settings)

    @staticmethod
    def _split_prefix(prefix: str) -> List[str]:
        segments = [segment for segment in prefix.strip("/").split("/") if segment]
        return [segment.lower() for segment in segments]

    @classmethod
    def _synchronize_view_model_name(
        cls,
        entry: Dict[str, Any],
        *,
        views_segments: List[str],
        orm_segments: List[str],
        settings_segments: List[str],
    ) -> None:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            return
        normalized_path = cls._normalize_prefix(path)
        path_segments = [
            segment.lower() for segment in normalized_path.strip("/").split("/") if segment
        ]
        if not path_segments:
            return

        slug = (
            cls._match_prefix_slug(path_segments, views_segments)
            or cls._match_prefix_slug(path_segments, orm_segments)
            or cls._match_prefix_slug(path_segments, settings_segments)
        )
        if slug is None:
            slug = "_".join(path_segments)
        entry["model_name"] = slug

    @staticmethod
    def _match_prefix_slug(
        path_segments: List[str], prefix_segments: List[str]
    ) -> str | None:
        if not prefix_segments:
            return None
        if path_segments[: len(prefix_segments)] != prefix_segments:
            return None
        trimmed = path_segments[len(prefix_segments) :]
        if not trimmed:
            return None
        if len(trimmed) >= 2:
            return trimmed[1]
        return trimmed[0]

# The End

