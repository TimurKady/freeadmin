# -*- coding: utf-8 -*-
"""
textarea

Multi-line text input widget.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Any, Dict

from . import BaseWidget, register_widget


@register_widget("textarea")
class TextAreaWidget(BaseWidget):
    assets_js = (
        "https://cdn.jsdelivr.net/npm/ace-builds@latest/src-noconflict/ace.min.js",
    )

    def get_schema(self) -> Dict[str, Any]:
        fd = self.ctx.field
        meta = getattr(fd, "meta", {}) or {}

        schema: Dict[str, Any] = {
            "type": "string",
            "format": "textarea",
            "title": self.get_title(),
        }

        syntax = meta.get("syntax")
        if syntax:
            theme = meta.get("ace_theme", "chrome")
            schema["options"] = {"ace": {"mode": syntax, "theme": theme}}

        return self.merge_readonly(schema)


# The End

