# -*- coding: utf-8 -*-
"""
views

System application page and menu registrars.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from freeadmin.core.interface.settings import SettingsKey, system_config

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from freeadmin.core.interface.site import AdminSite


class BuiltinPagesRegistrar:
    """Register built-in admin pages for the system application."""

    def __init__(self) -> None:
        """Initialize cached settings-driven page metadata."""

        self.dashboard_title = system_config.get_cached(
            SettingsKey.DASHBOARD_PAGE_TITLE, "Dashboard"
        )
        self.dashboard_icon = "bi-speedometer2"
        self.views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")
        self.views_title = system_config.get_cached(SettingsKey.VIEWS_PAGE_TITLE, "Views")
        self.views_icon = system_config.get_cached(SettingsKey.VIEWS_PAGE_ICON, "bi-eye")
        self.orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        self.orm_title = system_config.get_cached(SettingsKey.ORM_PAGE_TITLE, "ORM")
        self.orm_icon = system_config.get_cached(SettingsKey.ORM_PAGE_ICON, "bi-diagram-3")
        self.settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        self.settings_title = system_config.get_cached(SettingsKey.SETTINGS_PAGE_TITLE, "Settings")
        self.settings_icon = system_config.get_cached(SettingsKey.SETTINGS_PAGE_ICON, "bi-gear")
        self.default_page_type = system_config.get_cached(
            SettingsKey.PAGE_TYPE_VIEW, "view"
        )

    def register(self, site: "AdminSite") -> None:
        """Attach the built-in admin pages to ``site``."""

        site.menu_builder.register_item(
            title=self.dashboard_title,
            path="/",
            icon=self.dashboard_icon,
            page_type=self.default_page_type,
        )
        @site.register_view(
            path=self.views_prefix,
            name=self.views_title,
            icon=self.views_icon,
            include_in_sidebar=False,
        )
        async def views_placeholder(request, user):
            """Render a placeholder response for registered views."""

            page_title = await system_config.get(SettingsKey.VIEWS_PAGE_TITLE)
            return site.build_template_ctx(request, user, page_title=page_title)

        @site.register_view(
            path=self.orm_prefix,
            name=self.orm_title,
            icon=self.orm_icon,
            include_in_sidebar=False,
        )
        async def orm_home(request, user):
            """Render the ORM landing page."""

            page_title = await system_config.get(SettingsKey.ORM_PAGE_TITLE)
            return site.build_template_ctx(
                request,
                user,
                page_title=page_title,
                is_settings=False,
            )

        @site.register_settings(
            path=self.settings_prefix,
            name=self.settings_title,
            icon=self.settings_icon,
        )
        async def settings_home(request, user):
            """Render the Settings landing page."""

            page_title = await system_config.get(SettingsKey.SETTINGS_PAGE_TITLE)
            return site.build_template_ctx(
                request,
                user,
                page_title=page_title,
                is_settings=True,
            )


class BuiltinUserMenuRegistrar:
    """Register the default user menu entries."""

    def __init__(self) -> None:
        """Initialize cached metadata for user menu items."""

        self.logout_path = system_config.get_cached(SettingsKey.LOGOUT_PATH, "/logout")

    def register(self, site: "AdminSite") -> None:
        """Attach user menu entries to ``site``."""

        site.register_user_menu(
            title="Logout",
            path=self.logout_path,
            icon="bi-box-arrow-right",
        )


# The End
