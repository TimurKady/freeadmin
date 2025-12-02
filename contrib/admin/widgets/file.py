# -*- coding: utf-8 -*-
"""
file

Placeholder implementation for a file upload widget.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from typing import Any, Dict
from . import BaseWidget, register_widget

@register_widget("file-upload")
class FileUploadWidget(BaseWidget):
    def get_schema(self) -> Dict[str, Any]:
        return self.merge_readonly({
            "type": "string",
            "format": "data-url",
            "title": self.get_title(),
        })

# The End
