# -*- coding: utf-8 -*-
"""
application

Deprecated compatibility layer for the application factory.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import sys
import types
import warnings

from freeadmin.application import ApplicationFactory, RouterManager


class _LegacyFactoryModule(types.ModuleType):
    """Shim module emitting a deprecation warning on attribute access."""

    _warned = False

    def __getattribute__(self, name: str):
        if name not in {"_warned", "__dict__"} and not object.__getattribute__(self, "_warned"):
            warnings.warn(
                "freeadmin.core.application.factory is deprecated; import from freeadmin.application instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            object.__setattr__(self, "_warned", True)
        return super().__getattribute__(name)


_factory_module = _LegacyFactoryModule(__name__ + ".factory")
_factory_module.ApplicationFactory = ApplicationFactory
_factory_module.RouterManager = RouterManager
sys.modules[__name__ + ".factory"] = _factory_module

warnings.warn(
    "freeadmin.core.application is deprecated; import from freeadmin.application instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ApplicationFactory", "RouterManager"]


# The End

