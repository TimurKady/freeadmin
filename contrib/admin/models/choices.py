# -*- coding: utf-8 -*-
"""
choices

Django-like Choices for Tortoise/Pydantic v2.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from enum import Enum, IntEnum
from typing import Any, List, Tuple, TypeVar

_E = TypeVar("_E", bound="ChoicesMixin")


class ChoicesMixin:
    """Common helpers for choices-like enums."""

    label: str  # set on each member

    @classmethod
    def choices(cls) -> List[Tuple[Any, str]]:
        return [(m.value, m.label) for m in cls]  # type: ignore[attr-defined]

    @classmethod
    def values(cls) -> List[Any]:
        return [m.value for m in cls]

    @classmethod
    def labels(cls) -> List[str]:
        return [m.label for m in cls]  # type: ignore[attr-defined]

    @classmethod
    def get_label(cls, value: Any) -> str | None:
        for m in cls:  # type: ignore[assignment]
            if m.value == value:
                return getattr(m, "label", str(m))
        return None

    @classmethod
    def from_value(cls: type[_E], value: Any) -> _E:
        for m in cls:  # type: ignore[assignment]
            if m.value == value:
                return m  # type: ignore[return-value]
        raise ValueError(f"{cls.__name__}: no member with value {value!r}")


class StrChoices(ChoicesMixin, str, Enum):
    """String-based choices: members defined as ('value', 'Label')."""

    def __new__(cls, value: str, label: str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label  # type: ignore[attr-defined]
        return obj

    def __str__(self) -> str:
        return str(self.value)


class IntChoices(ChoicesMixin, IntEnum):
    """Integer-based choices: members defined as (value, 'Label')."""

    def __new__(cls, value: int, label: str):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.label = label  # type: ignore[attr-defined]
        return obj

    def __str__(self) -> str:
        return str(self.value)

# The End
