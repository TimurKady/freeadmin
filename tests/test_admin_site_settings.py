# -*- coding: utf-8 -*-
"""
tests.test_admin_site_settings

Validation for admin site settings resolution using runtime configuration.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from freeadmin.core.configuration.conf import FreeAdminSettings
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.runtime.hub import AdminHub


def test_admin_site_title_uses_runtime_settings(monkeypatch) -> None:
    """Admin site title should reflect database-backed runtime settings."""

    original_cache = dict(system_config._cache)  # type: ignore[attr-defined]
    try:
        system_config._cache.clear()  # type: ignore[attr-defined]
        system_config._cache[SettingsKey.DEFAULT_ADMIN_TITLE.value] = "Runtime Title"  # type: ignore[attr-defined]
        hub = AdminHub(settings=FreeAdminSettings())

        assert hub.admin_site.title == "Runtime Title"
    finally:
        system_config._cache.clear()  # type: ignore[attr-defined]
        system_config._cache.update(original_cache)  # type: ignore[attr-defined]


def test_admin_site_title_respects_override(monkeypatch) -> None:
    """Explicitly provided admin titles must override runtime settings."""

    original_cache = dict(system_config._cache)  # type: ignore[attr-defined]
    try:
        system_config._cache.clear()  # type: ignore[attr-defined]
        system_config._cache[SettingsKey.DEFAULT_ADMIN_TITLE.value] = "Runtime Title"  # type: ignore[attr-defined]
        hub = AdminHub(title="Static Title", settings=FreeAdminSettings())

        assert hub.admin_site.title == "Static Title"
    finally:
        system_config._cache.clear()  # type: ignore[attr-defined]
        system_config._cache.update(original_cache)  # type: ignore[attr-defined]


# The End


