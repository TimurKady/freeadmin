# -*- coding: utf-8 -*-
"""
context

Widget context helper.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from ..schema.descriptors import ModelDescriptor, FieldDescriptor

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from ..core.base import BaseModelAdmin  # type hints helper


@dataclass(frozen=True)
class WidgetContext:
    """Everything a widget needs to know about itself and its environment."""
    admin: BaseModelAdmin
    descriptor: ModelDescriptor           # model description (unified layer)
    field: FieldDescriptor                # field description (unified layer)
    name: str                             # field name in the form
    instance: Optional[Any]               # instance (None for add)
    mode: str                             # "add" | "edit" | "list"
    request: Any | None = None            # FastAPI Request (optional)
    readonly: bool = False                # field read-only?

# The End
