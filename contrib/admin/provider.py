# -*- coding: utf-8 -*-
"""
provider

Utility class for providing templates and static files for the admin.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

from .core.settings import SettingsKey, system_config

class TemplateProvider:
    """Encapsulates template and static file handling."""

    def __init__(self, *, templates_dir: str | Path, static_dir: str | Path) -> None:
        self.templates_dir = str(templates_dir)
        self.static_dir = str(static_dir)

    def get_templates(self) -> Jinja2Templates:
        """Return a configured ``Jinja2Templates`` instance."""
        templates = Jinja2Templates(directory=self.templates_dir)
        return templates

    def mount_static(self, app: FastAPI, prefix: str) -> None:
        """Mount static files onto the provided application."""
        static_segment = system_config.get_cached(
            SettingsKey.STATIC_URL_SEGMENT, "/static"
        )
        route_name = system_config.get_cached(
            SettingsKey.STATIC_ROUTE_NAME, "admin-static"
        )
        app.mount(
            f"{prefix}{static_segment}",
            StaticFiles(
                directory=self.static_dir,
                packages=[("contrib.admin", "static")],
            ),
            name=route_name,
        )

# The End
