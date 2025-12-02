# -*- coding: utf-8 -*-
"""
DataTime Widget.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from typing import Any, Dict
from datetime import date, datetime, time

from . import BaseWidget, register_widget

@register_widget("datetime")
class DateTimeWidget(BaseWidget):
    """
    Widget for ``date``/``datetime``/``time`` fields.
    JSON-Editor expects a string plus format: "date" | "datetime" | "time".
    """

    def get_schema(self) -> Dict[str, Any]:
        kind = (getattr(self.ctx.field, "kind", "") or "").lower()
        fmt = "datetime-local" if kind == "datetime" else ("date" if kind == "date" else "time")
        return self.merge_readonly({
            "type": "string",
            "title": self.get_title(),
            "format": fmt,
        })

    def get_startval(self) -> Any:
        v = super().get_startval()
        if v is None:
            return None
        # Convert to a string suitable for HTML5/JSON-Editor
        if isinstance(v, datetime):
            # 'YYYY-MM-DDTHH:MM:SS'
            return v.replace(microsecond=0).isoformat(timespec="seconds")
        if isinstance(v, date) and not isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, time):
            return v.replace(microsecond=0).isoformat(timespec="seconds")
        return str(v)

    def to_storage(self, value: Any, options: Dict[str, Any] | None = None) -> Any:
        # Keep as string—the model layer/validator will parse it
        return value

# The End
