# -*- coding: utf-8 -*-
"""
pages

Dataclasses describing different kinds of admin pages.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable

from .settings import SettingsKey, system_config


@dataclass(frozen=True)
class AdminPage:
    """Common fields shared by all pages in the admin interface."""

    title: str
    path: str
    icon: str | None = field(default=None, kw_only=True)
    page_type: str = field(
        default_factory=lambda: system_config.get_cached(
            SettingsKey.PAGE_TYPE_VIEW, "view"
        ),
        kw_only=True,
    )


@dataclass(frozen=True)
class FreeViewPage(AdminPage):
    """Arbitrary view rendered via a supplied handler."""

    # async/sync callable(request, user) -> dict
    handler: Callable[..., Any] | None = None


@dataclass(frozen=True)
class ModelPage(AdminPage):
    """Page representing an ORM model."""

    singular_title: str
    app_label: str
    model_name: str
    dotted: str
    # path for the model section will be of the form: /orm/{app}/{model}/


@dataclass(frozen=True)
class SettingsPage(FreeViewPage):
    """Administrative page for application settings."""

    page_type: str = field(
        default_factory=lambda: system_config.get_cached(
            SettingsKey.PAGE_TYPE_SETTINGS, "settings"
        )
    )

# The End
