# -*- coding: utf-8 -*-
"""
relations

Simple select widget working with pre-calculated choices.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Any, Dict

from tortoise import Tortoise

from . import BaseWidget, register_widget


def _choices_from_fd(fd) -> tuple[list[str], list[str]]:
    """Extract ``enum`` and ``titles`` from a field descriptor.

    Some ``FieldDescriptor`` instances might not have the ``meta`` attribute
    populated (e.g. when ``prefetch`` was not executed or the field does not
    require additional metadata).  Accessing ``fd.meta`` directly in those
    cases raises ``AttributeError`` which breaks schema generation.  To make
    the widget more robust we gracefully handle missing ``meta`` and simply
    return empty choices.
    """

    meta = getattr(fd, "meta", None) or {}
    cm = meta.get("choices_map") or {}
    enum = list(cm.keys())
    titles = list(cm.values())
    return enum, titles


@register_widget("relation")
class RelationsWidget(BaseWidget):
    """Simple select based on enum/enum_titles."""

    async def prefetch(self) -> None:
        fd = self.ctx.field
        rel = getattr(fd, "relation", None)
        if not rel:
            return

        if hasattr(Tortoise, "get_model"):
            RelModel = Tortoise.get_model(rel.target)
        else:  # pragma: no cover - older versions
            app_label, model_name = rel.target.rsplit(".", 1)
            RelModel = Tortoise.apps.get(app_label, {}).get(model_name)
        if RelModel is None:
            return

        pk_attr = RelModel._meta.pk_attr
        objs = await RelModel.all().order_by(pk_attr)
        choices_map = {str(getattr(o, pk_attr)): str(o) for o in objs}

        meta = dict(getattr(fd, "meta", {}) or {})
        meta["choices_map"] = choices_map
        object.__setattr__(fd, "meta", meta)

        inst = self.ctx.instance
        if inst is not None:
            cur = getattr(inst, f"{self.ctx.name}_id", None)
            if cur is not None:
                key = str(cur)
                if key not in choices_map:
                    try:
                        obj = await RelModel.get(**{pk_attr: cur})
                        choices_map[key] = str(obj)
                    except Exception:
                        choices_map[key] = key
                meta["current_label"] = choices_map.get(key)
                object.__setattr__(fd, "meta", meta)

    def get_schema(self) -> Dict[str, Any]:
        fd = self.ctx.field
        title = self.get_title()
        rel = getattr(fd, "relation", None)
        is_many = bool(getattr(fd, "many", False) or (rel and getattr(rel, "kind", "") == "m2m"))
        required = bool(getattr(fd, "required", False))

        enum, titles = _choices_from_fd(fd)

        # Placeholder: only for single selects and only if the field is optional
        if not required and not is_many:
            if not enum or enum[0] != "":
                enum = [""] + enum
                titles = ["--- Select ---"] + titles

        if is_many:
            schema = {
                "type": "array",
                "title": title,
                "format": "select",
                "uniqueItems": True,
                "items": {
                    "type": "string",
                    "enum": enum,
                    "options": {"enum_titles": titles},
                },
            }
            return self.merge_readonly(schema)

        schema = {
            "type": "string",
            "title": title,
            "enum": enum,
            "options": {"enum_titles": titles},
        }
        return self.merge_readonly(schema)

    def get_startval(self) -> Any:
        fd = self.ctx.field
        rel = getattr(fd, "relation", None)
        is_many = bool(getattr(fd, "many", False) or (rel and getattr(rel, "kind", "") == "m2m"))
        required = bool(getattr(fd, "required", False))

        # add
        if self.ctx.instance is None:
            # For single selects, explicitly include an empty value
            if not required and not is_many:
                return ""
            return None

        # edit: FK → "<pk>", M2M → ["<pk>", ...]
        if rel:
            if is_many:
                ids = getattr(self.ctx.instance, f"{self.ctx.name}_ids", None)
                return [str(v) for v in ids] if ids is not None else []
            cur = getattr(self.ctx.instance, f"{self.ctx.name}_id", None)
            return "" if (cur is None and not required) else (str(cur) if cur is not None else None)

        # simple fields
        return getattr(self.ctx.instance, self.ctx.name, None)

    def to_storage(self, value: Any, options: Dict[str, Any] | None = None) -> Any:
        if value is None:
            return None
        fd = self.ctx.field
        rel = getattr(fd, "relation", None)
        is_many = bool(getattr(fd, "many", False) or (rel and getattr(rel, "kind", "") == "m2m"))
        if is_many:
            return [str(v) for v in value]
        return str(value)

# The End
