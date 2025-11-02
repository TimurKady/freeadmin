# -*- coding: utf-8 -*-
"""
radio

Radio button widget.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from enum import Enum, EnumMeta
from typing import Any, Dict, Tuple, Iterable, cast

from ...models.choices import ChoicesMixin
from .base import BaseWidget
from .registry import registry

@registry.register("radio")
class RadioWidget(BaseWidget):
    """Radio buttons for fields with choices (IntEnum/CharEnum etc.)."""

    def _humanize(self, name: str) -> str:
        return name.replace("_", " ").title()

    def _normalize_choices(self, choices: Any) -> Tuple[list[Any], list[str]]:
        """
        Supported forms:
          - dict {value: label}
          - iterable of pairs (value, label)
          - iterable of values (value)
          - Enum class (EnumMeta) or iterable of Enum members

        For enum members where ``member.value`` itself is a two-item
        sequence ``(value, label)``, the second element is treated as the
        human‑readable label. Returns ``(enum_values, enum_titles)``.
        """
        if not choices:
            return [], []

        if isinstance(choices, type) and issubclass(choices, ChoicesMixin):
            vals = list(choices.values())
            titles = [
                str(desc if desc is not None else lbl)
                for desc, lbl in zip(choices.descriptions(), choices.labels())
            ]
            return vals, titles

        if isinstance(choices, EnumMeta):
            vals: list[Any] = []
            titles: list[str] = []
            for m in cast(Iterable[Enum], choices):
                val = m.value
                lbl = (
                    getattr(m, "description", None)
                    or getattr(m, "label", None)
                    or getattr(m, "title", None)
                )
                if isinstance(val, (tuple, list)) and len(val) == 2:
                    val, lbl = val
                lbl = lbl or self._humanize(m.name)
                vals.append(val)
                titles.append(str(lbl))
            return vals, titles

        if isinstance(choices, dict):
            vals, titles = [], []
            for k, v in choices.items():
                vals.append(k.value if isinstance(k, Enum) else k)
                if isinstance(v, Enum):
                    lbl = (
                        getattr(v, "description", None)
                        or getattr(v, "label", None)
                        or getattr(v, "title", None)
                        or self._humanize(v.name)
                    )
                else:
                    lbl = v
                titles.append(str(lbl))
            return vals, titles

        if isinstance(choices, Iterable) and not isinstance(choices, (str, bytes)):
            choices_list = list(choices)
            if choices_list and all(hasattr(c, "const") and hasattr(c, "title") for c in choices_list):
                vals = [getattr(item, "const") for item in choices_list]
                titles = [str(getattr(item, "title")) for item in choices_list]
                return vals, titles
            choices = choices_list

        vals, titles = [], []
        for item in choices:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                v, lbl = item
                vals.append(v.value if isinstance(v, Enum) else v)
                if isinstance(lbl, Enum):
                    lbl = (
                        getattr(lbl, "description", None)
                        or getattr(lbl, "label", None)
                        or getattr(lbl, "title", None)
                        or self._humanize(lbl.name)
                    )
                titles.append(str(lbl))
            elif isinstance(item, dict) and ("value" in item or "const" in item):
                v = item.get("value", item.get("const"))
                lbl = item.get("label", item.get("title", v))
                vals.append(v.value if isinstance(v, Enum) else v)
                if isinstance(lbl, Enum):
                    lbl = (
                        getattr(lbl, "description", None)
                        or getattr(lbl, "label", None)
                        or getattr(lbl, "title", None)
                        or self._humanize(lbl.name)
                    )
                titles.append(str(lbl))
            else:
                if isinstance(item, Enum):
                    val = item.value
                    lbl = (
                        getattr(item, "description", None)
                        or getattr(item, "label", None)
                        or getattr(item, "title", None)
                    )
                    if isinstance(val, (tuple, list)) and len(val) == 2:
                        val, lbl = val
                    lbl = lbl or self._humanize(item.name)
                    vals.append(val)
                    titles.append(str(lbl))
                else:
                    vals.append(item)
                    titles.append(str(item))
        return vals, titles

    def get_schema(self) -> Dict[str, Any]:
        """Build a JSON Schema fragment for a radio widget."""
        fd = self.ctx.field

        enum_vals, titles = self._normalize_choices(getattr(fd, "choices", None))

        # Type based on actual values (all ints → integer, otherwise string)
        typ = "integer" if enum_vals and all(isinstance(v, int) for v in enum_vals) else "string"

        opts = {"enum_titles": titles}
        return self.merge_readonly({
            "type": typ,
            "title": self.get_title(),
            "format": "radio",
            "enum": enum_vals,
            "options": opts,
        })

    def get_startval(self) -> Any:
        """Return the initial value for the radio widget."""
        val = super().get_startval()  # takes instance.<field> (see BaseWidget)
        if val is None:
            return None
        raw = getattr(val, "value", val)  # Enum → its .value
        enum_vals, _ = self._normalize_choices(getattr(self.ctx.field, "choices", None))
        if (
            enum_vals
            and all(isinstance(v, int) for v in enum_vals)
            and isinstance(raw, int)
            and not isinstance(raw, bool)
        ):
            return int(raw)
        return str(raw) if not isinstance(raw, int) else raw

    def to_storage(self, value: Any, options: Dict[str, Any] | None = None) -> Any:
        """Prepare the radio value for persistence."""
        return value

# The End

