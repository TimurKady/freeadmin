# -*- coding: utf-8 -*-
"""
hub

Admin hub configuration and autodiscovery helpers.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
import importlib
import pkgutil
from typing import Iterable, List, Optional

from fastapi import FastAPI

from .core.site import AdminSite
from .router import mount_admin
from config.settings import settings

# Initialize the admin site with a configurable title
admin_site = AdminSite(title=settings.ADMIN_SITE_TITLE)


def autodiscover(packages: Iterable[str]) -> None:
    """Import all *.admin and *.admin.* modules within the given packages."""
    for pkg in packages:
        try:
            root = importlib.import_module(pkg)
        except Exception:
            continue
        if not hasattr(root, "__path__"):
            continue
        # walk subpackages
        prefix = root.__name__ + "."
        for finder, modname, ispkg in pkgutil.walk_packages(root.__path__, prefix):
            if modname.endswith(".admin") or ".admin." in modname:
                importlib.import_module(modname)


def init_app(app: FastAPI, *, packages: Optional[List[str]] = None) -> None:
    """Convenience shortcut: autodiscover followed by mount_admin."""
    if packages:
        autodiscover(packages)
    mount_admin(app, admin_site)

# The End
