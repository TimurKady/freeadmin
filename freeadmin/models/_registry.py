# -*- coding: utf-8 -*-
"""_registry

Adapter-backed model registry used by :mod:`freeadmin.models`.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Type

from freeadmin.core.boot import admin as boot_admin
from .autodiscoverer import ModelAutoDiscoverer


class ModelRegistry:
    """Encapsulate discovery and export of adapter-backed admin models."""

    def __init__(self) -> None:
        """Load adapter-specific metadata required for admin models."""

        try:
            adapter = boot_admin.adapter
        except ModuleNotFoundError:  # pragma: no cover - during adapter bootstrap
            self._adapter: Optional[object] = None
            self._model_base: Type[object] = object
            self._perm_action: Optional[object] = None
            self._setting_value_type: Optional[object] = None
            self._models: List[Type[object]] = []
        else:
            self._adapter = adapter
            self._model_base = adapter.Model
            self._perm_action = adapter.perm_action
            self._setting_value_type = adapter.setting_value_type
            discoverer = ModelAutoDiscoverer(self._model_base)
            self._models = discoverer.models

    @property
    def adapter(self) -> Optional[object]:
        """Return the active admin adapter or ``None`` when unavailable."""

        return self._adapter

    @property
    def model_base(self) -> Type[object]:
        """Return the base model class provided by the adapter."""

        return self._model_base

    @property
    def perm_action(self) -> Optional[object]:
        """Return the adapter-specific permission action enumeration."""

        return self._perm_action

    @property
    def setting_value_type(self) -> Optional[object]:
        """Return the enumeration describing supported setting value types."""

        return self._setting_value_type

    @property
    def models(self) -> Sequence[Type[object]]:
        """Return the lazily discovered set of admin models."""

        return tuple(self._models)

    def export_names(self) -> List[str]:
        """Return the module export list used by :mod:`freeadmin.models`."""

        base_exports = [
            "StrChoices",
            "IntChoices",
            "TextChoices",
            "IntegerChoices",
            "PermAction",
            "SettingValueType",
        ]
        dynamic_exports = [model.__name__ for model in self._models]
        return base_exports + dynamic_exports


registry = ModelRegistry()

adapter = registry.adapter
ModelBase = registry.model_base
PermAction = registry.perm_action
SettingValueType = registry.setting_value_type
__models__ = list(registry.models)
__all__ = registry.export_names()


# The End

