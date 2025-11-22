# -*- coding: utf-8 -*-
"""
sidebar views

Regression coverage for admin sidebar view registration.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from starlette.requests import Request

from freeadmin.core.boot import admin as boot_admin
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.interface.site import AdminSite
from freeadmin.contrib.apps.system.views import BuiltinPagesRegistrar
from tests.conftest import admin_state


class TestSidebarViewRegistration:
    """Verify sidebar view registration excludes section placeholders."""

    site: AdminSite
    views_prefix: str
    orm_prefix: str
    settings_prefix: str

    @classmethod
    def setup_class(cls) -> None:
        """Prepare a fresh admin site with built-in registrations."""

        admin_state.reset()
        cls.site = AdminSite(boot_admin.adapter, title="Regression Admin")

        cls.views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")
        cls.orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        cls.settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")

        registrar = BuiltinPagesRegistrar()
        registrar.register(cls.site)

        @cls.site.register_view(
            path=f"{cls.views_prefix}/demo/list",
            name="Demo List",
            icon="bi-list",
            label="demo",
        )
        async def demo_list_view(request, user):
            """Return context for the demo list view."""

            return {}

        @cls.site.register_view(
            path=f"{cls.settings_prefix}/demo/config",
            name="Demo Config",
            icon="bi-gear",
            label="demo-config",
        )
        async def demo_config_view(request, user):
            """Return context for the demo config view."""

            return {}

    @classmethod
    def teardown_class(cls) -> None:
        """Reset admin site state after tests."""

        admin_state.reset()

    def test_get_sidebar_views_ignores_section_roots(self) -> None:
        """Ensure section landing pages do not populate the sidebar."""

        sidebar_views = self.site.get_sidebar_views(settings=False)
        labels = [label for label, _ in sidebar_views]

        assert "views" not in labels
        assert "orm" not in labels
        assert "demo" in labels

        entries_by_label = {label: entries for label, entries in sidebar_views}
        demo_entries = entries_by_label["demo"]
        assert any(entry["path"] == f"{self.views_prefix}/demo/list" for entry in demo_entries)
        assert all(entry["settings"] is False for entry in demo_entries)

    def test_get_sidebar_views_retains_settings_groupings(self) -> None:
        """Confirm real settings views continue to surface in the sidebar."""

        sidebar_views = self.site.get_sidebar_views(settings=True)
        labels = [label for label, _ in sidebar_views]

        assert "settings" not in labels
        assert "demo-config" in labels

        entries_by_label = {label: entries for label, entries in sidebar_views}
        config_entries = entries_by_label["demo-config"]
        assert any(
            entry["path"] == f"{self.settings_prefix}/demo/config" for entry in config_entries
        )
        assert all(entry["settings"] is True for entry in config_entries)


# The End

