# -*- coding: utf-8 -*-
"""
example.pages.public_welcome

Example public page demonstrating FreeAdmin's extended router aggregator.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from freeadmin.core.interface.pages import BaseTemplatePage
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.runtime.hub import admin_site


class PublicWelcomePage(BaseTemplatePage):
    """Register the example public welcome page with the admin site."""

    path = "/"
    name = "Welcome"
    template = "pages/welcome.html"
    template_directory = Path(__file__).resolve().parent.parent / "templates"
    icon = "bi-stars"

    def __init__(self) -> None:
        """Register the public welcome view when instantiated."""

        super().__init__(site=admin_site)
        self.register_public_view()
        self.register_public_navigation()

    def register_public_navigation(self) -> None:
        """Register supplemental public navigation entries for the example."""

        login_path = system_config.get_cached(SettingsKey.LOGIN_PATH, "/login")
        admin_site.register_public_menu(
            title="Sign in",
            path=login_path,
            icon="bi-box-arrow-in-right",
        )

    async def get_context(
        self,
        *,
        request: Request,
        user: object | None = None,
    ) -> dict[str, object]:
        """Return template context for the welcome example page."""

        return {
            "subtitle": "Rendered outside the admin",
            "user": user,
        }


public_welcome_page = PublicWelcomePage()


# The End


