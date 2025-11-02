# -*- coding: utf-8 -*-
"""
choices

Choice enumerations for Tortoise/Pydantic v2.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from enum import Enum, IntEnum
from typing import Any, Iterable, List, Tuple, cast


class ChoicesMixin:
    """Common helpers for choices-like enums."""

    label: str  # set on each member
    description: str | None  # optional description set on each member

    @classmethod
    def choices(cls) -> List[Tuple[Any, str]]:
        """Return a list of ``(value, label)`` pairs for each member."""
        members = cast(Iterable[Any], cls)
        return [(m.value, m.label) for m in members]  # type: ignore[attr-defined]

    @classmethod
    def values(cls) -> List[Any]:
        """Return all enumeration values."""
        members = cast(Iterable[Any], cls)
        return [m.value for m in members]

    @classmethod
    def labels(cls) -> List[str]:
        """Return labels for all members."""
        members = cast(Iterable[Any], cls)
        return [m.label for m in members]  # type: ignore[attr-defined]

    @classmethod
    def descriptions(cls) -> List[str | None]:
        """Return descriptions for all members."""
        members = cast(Iterable[Any], cls)
        return [getattr(m, "description", None) for m in members]

    @classmethod
    def get_label(cls, value: Any) -> str | None:
        """Return a label for the given value or ``None`` if not found."""
        for m in cast(Iterable[Any], cls):  # type: ignore[assignment]
            if m.value == value:
                return getattr(m, "label", str(m))
        return None

    @classmethod
    def from_value(cls, value: Any) -> ChoicesMixin:
        """Return the enum member matching ``value`` or raise ``ValueError``."""
        for m in cast(Iterable[Any], cls):  # type: ignore[assignment]
            if getattr(m, "value", None) == value:
                return cast(ChoicesMixin, m)
        raise ValueError(f"{cls.__name__}: no member with value {value!r}")


class StrChoices(ChoicesMixin, str, Enum):
    """String-based choices defined as ``('value', 'Label', 'Description')``."""

    def __new__(cls, value: str, label: str, description: str | None = None):
        """Create a new string choice."""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label  # type: ignore[attr-defined]
        obj.description = description  # type: ignore[attr-defined]
        return obj

    def __str__(self) -> str:
        """Return the ``value`` as string."""
        return str(self.value)


class IntChoices(ChoicesMixin, IntEnum):
    """Integer-based choices defined as ``(value, 'Label', 'Description')``."""

    def __new__(cls, value: int, label: str, description: str | None = None):
        """Create a new integer choice."""
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.label = label  # type: ignore[attr-defined]
        obj.description = description  # type: ignore[attr-defined]
        return obj

    def __str__(self) -> str:
        """Return the ``value`` as string."""
        return str(self.value)
# The End

