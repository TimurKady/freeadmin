# -*- coding: utf-8 -*-
"""
__init__

Utilities for working with admin form widgets.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

# admin/widgets/__init__.py
from __future__ import annotations

from .base import BaseWidget
from .registry import register_widget, registry

__all__ = ["BaseWidget", "register_widget", "registry"]

# Import built-in widgets so they register themselves:
from .text import TextWidget      # noqa: F401
from .textarea import TextAreaWidget  # noqa: F401
from .relations import RelationsWidget  # noqa: F401
from .file import FileUploadWidget  # noqa: F401
from .number import NumberWidget  # noqa: F401
from .checkbox import CheckboxWidget  # noqa: F401
from .radio import RadioWidget          # noqa: F401
from .datetime import DateTimeWidget  # noqa: F401

# The End
