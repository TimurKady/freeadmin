# -*- coding: utf-8 -*-
"""
views

Free Page Builder.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from ..core.site import AdminSite
from ..core.settings import SettingsKey, system_config

def register_builtin_pages(site: AdminSite) -> None:
    views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")
    views_title = system_config.get_cached(SettingsKey.VIEWS_PAGE_TITLE, "Views")
    views_icon = system_config.get_cached(SettingsKey.VIEWS_PAGE_ICON, "bi-eye")
    orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
    orm_title = system_config.get_cached(SettingsKey.ORM_PAGE_TITLE, "ORM")
    orm_icon = system_config.get_cached(SettingsKey.ORM_PAGE_ICON, "bi-diagram-3")
    settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
    settings_title = system_config.get_cached(SettingsKey.SETTINGS_PAGE_TITLE, "Settings")
    settings_icon = system_config.get_cached(SettingsKey.SETTINGS_PAGE_ICON, "bi-gear")

    @site.register_view(path=views_prefix, name=views_title, icon=views_icon)
    async def views_placeholder(request, user):
        page_title = await system_config.get(SettingsKey.VIEWS_PAGE_TITLE)
        return site.build_template_ctx(request, user, page_title=page_title)

    @site.register_view(path=orm_prefix, name=orm_title, icon=orm_icon)
    async def orm_home(request, user):
        page_title = await system_config.get(SettingsKey.ORM_PAGE_TITLE)
        return site.build_template_ctx(request, user, page_title=page_title, is_settings=False)

    @site.register_settings(path=settings_prefix, name=settings_title, icon=settings_icon)
    async def settings_home(request, user):
        page_title = await system_config.get(SettingsKey.SETTINGS_PAGE_TITLE)
        return site.build_template_ctx(request, user, page_title=page_title, is_settings=True)

# The End
