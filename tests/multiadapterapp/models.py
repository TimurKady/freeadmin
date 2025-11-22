# -*- coding: utf-8 -*-
"""In-memory models used for adapter integration tests."""

from __future__ import annotations


class MultiAdapterModel:
    """Lightweight model representation for menu registration."""

    def __init__(self) -> None:
        """Create an empty model instance for compatibility hooks."""

        self.id: int | None = None


class MemoryContentType:
    """Represent the admin content type tracked during finalization."""

    def __init__(
        self,
        *,
        app_label: str,
        model: str,
        dotted: str,
        is_registered: bool = True,
        identifier: int | None = None,
    ) -> None:
        """Store identifying attributes and optional primary key."""

        self.id = identifier
        self.app_label = app_label
        self.model = model
        self.dotted = dotted
        self.is_registered = is_registered


class MemorySystemSetting:
    """Simplified system setting model used by in-memory adapters."""

    def __init__(self, *, key: str, name: str, value, value_type: str) -> None:
        """Persist key, name, value, and value type for assertions."""

        self.id: int | None = None
        self.key = key
        self.name = name
        self.value = value
        self.value_type = value_type


class MemoryUser:
    """Placeholder user model required for adapter validation."""

    def __init__(self, username: str = "user") -> None:
        """Store the username field for compatibility."""

        self.id: int | None = None
        self.username = username


class MemoryGroup:
    """Placeholder group model required for adapter validation."""

    def __init__(self, name: str = "group") -> None:
        """Store the group name for compatibility."""

        self.id: int | None = None
        self.name = name


class MemoryPermission:
    """Placeholder permission model required for adapter validation."""

    def __init__(self, owner=None) -> None:
        """Store the permission owner for compatibility."""

        self.id: int | None = None
        self.owner = owner


class MemoryEnum:
    """Minimal enumeration stand-in for adapter validation."""

    def __init__(self, label: str = "enum") -> None:
        """Retain a label describing the enumeration member."""

        self.label = label


__all__ = [
    "MemoryContentType",
    "MemoryEnum",
    "MemoryGroup",
    "MemoryPermission",
    "MemorySystemSetting",
    "MemoryUser",
    "MultiAdapterModel",
]


# The End
