# -*- coding: utf-8 -*-
"""
inline

Inline model admin definitions.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from typing import Any, Optional, Type, Literal

from .base import BaseModelAdmin


class InlineAdmin(BaseModelAdmin):
    """Base class for building an inline model."""

    model: Type[Any]
    parent_fk_name: Optional[str] = None  # FK-name on parent
    extra: int = 0
    can_delete: bool = True
    display: Literal["tabular", "stacked"] = "tabular"

# The End
