# -*- coding: utf-8 -*-
"""
example.rendering

Example utilities demonstrating how to render FreeAdmin templates for public pages.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from freeadmin.config import FreeAdminSettings, current_settings

EXAMPLE_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
ADMIN_TEMPLATES_DIR = EXAMPLE_TEMPLATES_DIR.parents[1] / "freeadmin" / "templates"


class ExampleTemplateRenderer:
    """Provide cached template rendering for example public pages."""

    _templates: Jinja2Templates | None = None

    @classmethod
    def get_templates(cls) -> Jinja2Templates:
        """Return a configured ``Jinja2Templates`` instance for examples."""

        if cls._templates is None:
            settings: FreeAdminSettings | None = current_settings()
            templates = Jinja2Templates(directory=str(EXAMPLE_TEMPLATES_DIR))
            loader = templates.env.loader
            if hasattr(loader, "searchpath"):
                search_paths = list(getattr(loader, "searchpath", []))
                example_path = str(EXAMPLE_TEMPLATES_DIR)
                admin_path = str(ADMIN_TEMPLATES_DIR)
                if example_path not in search_paths:
                    search_paths.insert(0, example_path)
                if admin_path not in search_paths:
                    search_paths.append(admin_path)
                loader.searchpath = search_paths  # type: ignore[attr-defined]
            templates.env.globals["settings"] = settings
            cls._templates = templates
        return cls._templates

    @classmethod
    def render(
        cls,
        template_name: str,
        context: Mapping[str, Any],
        *,
        request: Request,
    ) -> HTMLResponse:
        """Render ``template_name`` with ``context`` using example templates."""

        final_context = dict(context)
        final_context.setdefault("request", request)
        return cls.get_templates().TemplateResponse(template_name, final_context)


# The End
