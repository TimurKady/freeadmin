# -*- coding: utf-8 -*-
"""
core.templates.service

Shared template service coordinating providers, caching, and mounting.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, TYPE_CHECKING
from weakref import WeakSet

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from freeadmin.config import (
    FreeAdminSettings,
    current_settings,
    register_settings_observer,
)

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from ..site import AdminSite
    from ...runtime.provider import TemplateProvider


ASSETS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates"


class TemplateService:
    """Manage template providers, caching, and static mounts for FreeAdmin."""

    def __init__(
        self,
        *,
        templates_dir: str | Path | Iterable[str | Path] | None = None,
        static_dir: str | Path | None = None,
        settings: FreeAdminSettings | None = None,
        provider_cls: type["TemplateProvider"] | None = None,
    ) -> None:
        """Configure the service with template locations and settings."""

        self._template_dirs = self._coerce_template_dirs(
            templates_dir or TEMPLATES_DIR
        )
        self._static_dir = str(static_dir or ASSETS_DIR)
        self._settings = settings or current_settings()
        if provider_cls is None:
            from ...runtime.provider import TemplateProvider as _TemplateProvider

            provider_cls = _TemplateProvider
        self._provider_cls = provider_cls
        self._provider: TemplateProvider | None = None
        self._templates: Jinja2Templates | None = None
        self._mounted_apps: WeakSet[FastAPI] = WeakSet()
        if settings is None:
            register_settings_observer(self._apply_settings)

    def get_provider(self) -> TemplateProvider:
        """Return the cached template provider, creating it when needed."""

        if self._provider is None:
            self._provider = self._provider_cls(
                templates_dir=self._template_dirs,
                static_dir=self._static_dir,
                settings=self._settings,
            )
        return self._provider

    def get_templates(self) -> Jinja2Templates:
        """Return the cached ``Jinja2Templates`` environment."""

        if self._templates is None:
            self._templates = self.get_provider().get_templates()
        return self._templates

    def _apply_settings(self, settings: FreeAdminSettings) -> None:
        """Update cached configuration when global settings change."""

        self._settings = settings
        if self._provider is not None:
            self._provider._settings = settings
        if self._templates is not None:
            self._templates.env.globals["settings"] = settings

    def ensure_site_templates(self, site: "AdminSite") -> None:
        """Ensure the provided admin ``site`` exposes the shared templates."""

        if site.templates is None:
            site.templates = self.get_templates()

    def mount_static_resources(self, app: FastAPI, prefix: str) -> None:
        """Mount static, favicon, and media resources once per application."""

        if app in self._mounted_apps:
            return

        provider = self.get_provider()
        provider.mount_static(app, prefix)
        provider.mount_favicon(app)
        provider.mount_media(app)
        self._mounted_apps.add(app)

    def add_template_directory(self, directory: str | Path) -> None:
        """Ensure ``directory`` is part of the template search path."""

        normalized = str(directory)
        if normalized in self._template_dirs:
            return
        self._template_dirs.append(normalized)
        if self._provider is not None:
            self._provider.add_template_directory(normalized)
        if self._templates is not None:
            loader = self._templates.env.loader
            if hasattr(loader, "searchpath"):
                search_paths = list(getattr(loader, "searchpath", []))
                if normalized not in search_paths:
                    search_paths.append(normalized)
                    loader.searchpath = search_paths  # type: ignore[attr-defined]

    @staticmethod
    def _coerce_template_dirs(
        templates_dir: str | Path | Iterable[str | Path]
    ) -> list[str]:
        """Normalise ``templates_dir`` into a mutable list of search paths."""

        if isinstance(templates_dir, (str, Path)):
            return [str(templates_dir)]
        return [str(path) for path in templates_dir]


DEFAULT_TEMPLATE_SERVICE: TemplateService | None = None


# The End

