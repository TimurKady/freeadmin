# -*- coding: utf-8 -*-
"""
ORM

Illustrative ORM configuration for the FreeAdmin example project.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from freeadmin.contrib.adapters.tortoise.adapter import (
    Adapter as TortoiseAdapter,
)
from freeadmin.core.orm import ORMConfig, ORMLifecycle


DB_ADAPTER = "tortoise"
"""Name of the FreeAdmin adapter powering the example ORM layer."""

SYSTEM_APP_MODULES: tuple[str, ...] = (
    "freeadmin.contrib.apps.system.models",
)
"""System-level model modules exposed to the example for admin helpers."""

ADMIN_APP_MODULES: tuple[str, ...] = tuple(TortoiseAdapter.model_modules)
"""Adapter-provided admin model modules bundled with FreeAdmin."""

MODELS_APP_MODULES: tuple[str, ...] = (
    "example.apps.demo.models",
)
"""Application model modules included in the example project."""

ORM_CONFIG: Dict[str, Dict[str, Any]] = {
    "connections": {
        "default": "sqlite://:memory:",
    },
    "apps": {
        "system": {
            "models": list(SYSTEM_APP_MODULES),
            "default_connection": "default",
        },
        "admin": {
            "models": list(ADMIN_APP_MODULES),
            "default_connection": "default",
        },
        "models": {
            "models": list(MODELS_APP_MODULES),
            "default_connection": "default",
        },
    },
}
"""Declarative configuration mapping for the example ORM setup."""

ExampleORMConfig: ORMConfig = ORMConfig.build(
    adapter_name=DB_ADAPTER,
    config=deepcopy(ORM_CONFIG),
)
"""Ready-to-use :class:`ORMConfig` instance for the example application."""


__all__ = [
    "DB_ADAPTER",
    "ADMIN_APP_MODULES",
    "ExampleORMConfig",
    "MODELS_APP_MODULES",
    "ORM_CONFIG",
    "ORMLifecycle",
    "SYSTEM_APP_MODULES",
]

# The End

