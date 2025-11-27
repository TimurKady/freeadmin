# -*- coding: utf-8 -*-
"""
textarea

Multi-line text input widget.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Any, Dict

from .base import BaseWidget
from .registry import registry


@registry.register("textarea")
class TextAreaWidget(BaseWidget):
    assets_js = ("/static/widgets/textarea.js",)
    _ace_src = "/static/vendors/ace-builds/src-noconflict/ace.js"

    def get_assets(self) -> Dict[str, list[str]]:
        """Return widget assets, enabling Ace only when configured."""

        assets = super().get_assets()
        if self._needs_ace():
            js_assets = assets.get("js", [])
            if self._ace_src not in js_assets:
                js_assets.insert(0, self._ace_src)
            assets["js"] = js_assets
        return assets

    def get_schema(self) -> Dict[str, Any]:
        fd = self.ctx.field
        meta = getattr(fd, "meta", {}) or {}

        fmt = self.config.get("format") or ("ace" if self._needs_ace() else "textarea")
        schema: Dict[str, Any] = {
            "type": "string",
            "format": fmt,
            "title": self.get_title(),
        }

        options = dict(self.config.get("options", {}))
        ace_options = dict(self.config.get("ace", {}))

        syntax = ace_options.pop("mode", None) or meta.get("syntax")
        theme = ace_options.pop("theme", None) or meta.get("ace_theme", "chrome")

        if syntax or ace_options:
            mode_path = syntax or ""
            if mode_path and not mode_path.startswith("ace/"):
                mode_path = f"ace/mode/{mode_path}"

            theme_path = theme or ""
            if theme_path and not theme_path.startswith("ace/"):
                theme_path = f"ace/theme/{theme_path}"

            if mode_path:
                ace_options["mode"] = mode_path
            if theme_path:
                ace_options.setdefault("theme", theme_path)

            ace_options.setdefault("use_ace_editor", True)

            options["ace"] = ace_options

        if options:
            schema["options"] = options

        schema.setdefault("options", {})
        schema["options"].setdefault("inputAttributes", {})
        schema["options"]["inputAttributes"]["data-textarea-autosize"] = "1"

        return self.merge_readonly(schema)

    def _needs_ace(self) -> bool:
        """Check whether Ace assets are required for the current field."""

        meta = getattr(self.ctx.field, "meta", {}) or {}
        return bool(meta.get("syntax") or self.config.get("ace"))

# The End

