# -*- coding: utf-8 -*-
"""
system sidebar

Registration coverage for system app admin sidebar population.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from fastapi import FastAPI

from freeadmin.core.boot import admin as boot_admin
from freeadmin.core.interface.sidebar import SidebarBuilder
from freeadmin.core.runtime.hub import admin_site
from tests.conftest import admin_state


class TestSystemSidebarPopulation:
    """Ensure system models populate the admin registry and sidebar."""

    site = admin_site

    @classmethod
    def setup_class(cls) -> None:
        """Boot the admin site to trigger system registrations."""

        admin_state.reset()
        cls.app = FastAPI()
        boot_admin.init(cls.app)
        cls.site = admin_site

    @classmethod
    def teardown_class(cls) -> None:
        """Reset admin configuration after sidebar assertions."""

        admin_state.reset()

    def test_system_models_registered(self) -> None:
        """Confirm system models exist in the admin registry."""

        registered_keys = set(self.site.model_reg.keys())
        expected = {
            ("admin", "admingroup"),
            ("admin", "adminuserpermission"),
            ("admin", "admingrouppermission"),
            ("admin", "adminuser"),
            ("core", "systemsetting"),
        }
        assert expected.issubset(registered_keys)

    def test_sidebar_contains_system_entries(self) -> None:
        """Verify sidebar builder outputs entries for system models."""

        sidebar_apps = SidebarBuilder.collect(
            self.site, SidebarBuilder.KIND_APPS, settings=True
        )
        entries_by_label = {label: entries for label, entries in sidebar_apps}

        assert entries_by_label
        admin_entries = entries_by_label.get("admin")
        assert admin_entries is not None

        admin_slugs = {entry["model_name"].lower() for entry in admin_entries}
        assert {"admingroup", "adminuser", "admingrouppermission", "adminuserpermission"}.issubset(
            admin_slugs
        )

        core_entries = entries_by_label.get("core")
        assert core_entries is not None
        assert any(
            entry["model_name"].lower() == "systemsetting" for entry in core_entries
        )

    def test_main_menu_contains_core_entries(self) -> None:
        """Ensure the main navigation includes dashboard and settings pages."""

        menu = self.site.menu_builder.build_main_menu(locale="en")
        titles = {item.title for item in menu}

        assert {"Dashboard", "Views", "Settings"}.issubset(titles)

    def test_user_menu_contains_logout(self) -> None:
        """Ensure the user menu is populated with default entries."""

        menu = self.site.get_user_menu()
        labels = {entry["label"] for entry in menu}

        assert "Logout" in labels


# The End
