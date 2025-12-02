# -*- coding: utf-8 -*-
"""
number

Widget for numeric fields (integers and floats).

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Any, Dict

from . import BaseWidget, register_widget


@register_widget("number")
class NumberWidget(BaseWidget):
    """Render numeric values using JSON Schema number/integer types."""

    def get_schema(self) -> Dict[str, Any]:
        kind = (getattr(self.ctx.field, "kind", "") or "").lower()
        schema_type = "integer" if kind in ("int", "integer") else "number"
        return self.merge_readonly({
            "type": schema_type,
            "title": self.get_title(),
        })

# The End
