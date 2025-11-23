# -*- coding: utf-8 -*-
"""
registry

Widget registry.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from typing import Dict, Type

from freeadmin.core.schema_descriptors import FieldDescriptor
from .base import BaseWidget


class WidgetRegistry:
    def __init__(self) -> None:
        """Initialize an empty registry of widget classes."""
        self._by_key: Dict[str, Type[BaseWidget]] = {}

    def register(self, key: str):
        """Decorator to register a widget by key."""
        def _decorator(cls: Type[BaseWidget]) -> Type[BaseWidget]:
            cls.key = key
            self._by_key[key] = cls
            return cls
        return _decorator

    def get(self, key: str) -> Type[BaseWidget] | None:
        """Retrieve a registered widget class by key."""
        return self._by_key.get(key)

    def resolve_for_field(
        self,
        fd: FieldDescriptor,
        field_name: str | None = None,
        admin=None,
    ) -> str:
        """Map a field to a widget key."""
        meta = getattr(fd, "meta", None) or {}
        if "widget" in meta:
            return str(meta["widget"])

        k = (fd.kind or "").lower()  # "string" | "int" | "bool" | "date" | "m2m" | "fk" | ...

        # 1) Boolean fields — always a checkbox (even if choices like Yes/No are provided)
        if k in ("bool", "boolean"):
            return "checkbox"

        if fd.relation is not None:
            name = field_name or getattr(fd, "name", "")
            rel_kind = getattr(fd.relation, "kind", "").lower()
            if (
                rel_kind == "fk"
                and admin is not None
                and name in admin.get_autocomplete_fields()
            ):
                return "select2"
            return "relation"

        if fd.choices is not None:
            return "radio"

        if k in ("number", "int", "integer", "float", "bigint", "decimal"):
            return "number"
        if k in ("date", "datetime", "time"):
            return "datetime"
        if k == "text":
            return "textarea"
        if k == "string":
            return "text"
        if k == "file":
            return "filepath"
        return "text"

registry = WidgetRegistry()

# The End

