# -*- coding: utf-8 -*-
"""
registry

Registry for admin pages and view entries.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Type

from .pages import AdminPage
from .settings import SettingsKey, system_config


@dataclass(frozen=True)
class ViewEntry:
    """Registry entry describing a model admin."""

    app: str
    model: str
    admin_cls: Type
    settings: bool
    icon: str | None
    name: str | None


@dataclass(frozen=True)
class MenuItem:
    """Navigation menu item."""

    title: str
    path: str
    icon: str | None = None
    page_type: str | None = None


class PageRegistry:
    """Store registered pages and model admin view entries."""

    def __init__(self) -> None:
        self.page_list: List[AdminPage] = []
        self.menu_list: List[MenuItem] = []
        self.view_entries: List[ViewEntry] = []

    # View entries -----------------------------------------------------
    def register_view_entry(
        self,
        *,
        app: str,
        model: str,
        admin_cls: Type,
        settings: bool = False,
        icon: str | None = None,
        name: str | None = None,
    ) -> None:
        """Register a :class:`ViewEntry` for the given admin class.

        The operation is idempotent for the tuple ``(app, model, settings)`` and
        raises ``ValueError`` when the resulting path is already occupied by
        another page or view entry.
        """

        key = (app.lower(), model.lower(), settings)
        for e in self.view_entries:
            if (e.app.lower(), e.model.lower(), e.settings) == key:
                return  # Idempotent

        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        prefix = (
            f"{settings_prefix}/{app}/{model}" if settings else f"{orm_prefix}/{app}/{model}"
        )

        for e in self.view_entries:
            other_prefix = (
                f"{settings_prefix}/{e.app}/{e.model}"
                if e.settings
                else f"{orm_prefix}/{e.app}/{e.model}"
            )
            if other_prefix == prefix:
                raise ValueError(f"Path conflict: {prefix}")

        for page in self.page_list:
            if page.path == prefix:
                raise ValueError(f"Path conflict: {prefix}")

        entry = ViewEntry(
            app=app,
            model=model,
            admin_cls=admin_cls,
            settings=settings,
            icon=icon,
            name=name,
        )
        self.view_entries.append(entry)

    def iter_orm(self) -> Iterator[ViewEntry]:
        """Iterate over non-settings admin registrations."""

        yield from (e for e in self.view_entries if not e.settings)

    def iter_settings(self) -> Iterator[ViewEntry]:
        """Iterate over settings admin registrations."""

        yield from (e for e in self.view_entries if e.settings)

    # Menu -------------------------------------------------------------
    def make_menu(self) -> List[MenuItem]:
        """Return full menu including ORM and settings admin entries."""

        default_page_type = system_config.get_cached(
            SettingsKey.PAGE_TYPE_VIEW, "view"
        )
        menu: List[MenuItem] = [
            MenuItem(
                title=m.title,
                path=m.path,
                icon=m.icon,
                page_type=m.page_type or default_page_type,
            )
            for m in self.menu_list
        ]
        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        for e in self.iter_orm():
            menu.append(
                MenuItem(
                    title=e.name or e.model,
                    path=f"{orm_prefix}/{e.app}/{e.model}",
                    icon=e.icon,
                    page_type=system_config.get_cached(SettingsKey.PAGE_TYPE_ORM, "orm"),
                )
            )
        for e in self.iter_settings():
            menu.append(
                MenuItem(
                    title=e.name or e.model,
                    path=f"{settings_prefix}/{e.app}/{e.model}",
                    icon=e.icon,
                    page_type=system_config.get_cached(SettingsKey.PAGE_TYPE_SETTINGS, "settings"),
                )
            )
        return menu

# The End
