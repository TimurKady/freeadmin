# -*- coding: utf-8 -*-
"""
base

Base widget class.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

# admin/widgets/base.py
from __future__ import annotations
from typing import Any, Dict
from abc import ABC, abstractmethod
from .context import WidgetContext


class BaseWidget(ABC):
    """
    Base Widget Class

    Widgets provide JSON Schema fragments and optional start values.
    """
    key: str = "base"
    assets_css: tuple[str, ...] = ()
    assets_js: tuple[str, ...] = ()

    class Meta:
        css: tuple[str, ...] = ()
        js: tuple[str, ...] = ()

    def __init__(self, ctx: WidgetContext) -> None:
        self.ctx = ctx

    def get_assets(self) -> Dict[str, list[str]]:
        """
        Return widget assets:
        {
            "css": [...],
            "js": [...],
        }
        Priority: class attributes + Meta; preserve order, remove duplicates.

        Then any specific widget can put assets either like this:
        
        class RadioWidget(BaseWidget):
            assets_js = ("/static/admin/widgets/radio.js",)
            assets_css = ("/static/admin/widgets/radio.css",)
        
        or like this:
        
        class RadioWidget(BaseWidget):
            class Meta:
                js = ("/static/admin/widgets/radio.js",)
                css = ("/static/admin/widgets/radio.css",)
        
        Both methods will be combined.
        """

        css: list[str] = []
        js: list[str] = []

        # class-level
        css.extend(getattr(self, "assets_css", ()))
        js.extend(getattr(self, "assets_js", ()))

        # Meta-level
        meta = getattr(self, "Meta", None)
        if meta:
            css.extend(getattr(meta, "css", ()))
            js.extend(getattr(meta, "js", ()))

        # dedup while preserving order
        def _uniq(seq):
            seen = set()
            for x in seq:
                if x not in seen:
                    seen.add(x)
                    yield x

        return {"css": list(_uniq(css)), "js": list(_uniq(js))}
    
    def get_title(self) -> str:
        label = getattr(self.ctx.field, "label", None)
        if label:
            return label
        name = self.ctx.name.replace("_", "\u00A0")
        return name[:1].upper() + name[1:]

    # === Schema Generation ===
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """JSON Schema fragment for a specific field."""
        raise NotImplementedError

    def merge_readonly(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Insert the ``readonly`` flag into the schema if needed."""
        if self.ctx.readonly:
            schema["readonly"] = True
        return schema
    
    def get_startval(self) -> Any:
        """Start value for the form (edit) — defaults to ``instance``."""
        if self.ctx.instance is not None:
            return getattr(self.ctx.instance, self.ctx.name, None)
        return None

    async def prefetch(self) -> None:
        """Stub for asynchronous data preparation before schema generation."""
        return None

    # === Value Converters ===
    def to_python(self, value: Any, options: Dict[str, Any] | None = None) -> Any:
        return value

    def to_storage(self, value: Any, options: Dict[str, Any] | None = None) -> Any:
        return value

# The End
