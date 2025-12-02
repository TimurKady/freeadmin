# -*- coding: utf-8 -*-
"""
router

Admin router utilities for mounting the admin site.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from config.settings import settings

from .core.site import AdminSite
from .provider import TemplateProvider

ASSETS_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def mount_admin(app: FastAPI, site: AdminSite, prefix: str = settings.ADMIN_PATH) -> None:
    """Mount the admin interface onto the application."""

    # "prefix" may be supplied with a trailing slash; remove it for
    # consistency so paths can be concatenated safely.
    prefix = prefix.rstrip("/")

    provider = TemplateProvider(
        templates_dir=str(TEMPLATES_DIR), static_dir=str(ASSETS_DIR)
    )
    if site.templates is None:
        site.templates = provider.get_templates()

    app.state.admin_site = site
    router = site.build_router(provider)
    app.include_router(router, prefix=prefix)
    provider.mount_static(app, prefix)

# The End
