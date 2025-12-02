# -*- coding: utf-8 -*-
"""
checkbox

Enhanced checkbox widget with Bootstrap switch support.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from typing import Any, Dict

from . import BaseWidget, register_widget


@register_widget("checkbox")
class CheckboxWidget(BaseWidget):
    """Render boolean values as a checkbox or Bootstrap switch."""

    def get_schema(self) -> Dict[str, Any]:
        title = self.get_title()
        
        # Base schema
        schema = {
            "type": "boolean",
            "format": "checkbox",
            "title": title,
            "options": {
                "containerAttributes": {
                    "class": "form-check form-switch"
                },
                "inputAttributes": {
                    "class": "form-check-input",
                    "type": "checkbox",
                    "role": "switch"
                }
            }
        }
        return self.merge_readonly(schema)

# The End
