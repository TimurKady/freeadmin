# -*- coding: utf-8 -*-
"""
conf

Compatibility facade exposing configuration helpers from the configuration package.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import warnings

from freeadmin.config import (
    FreeAdminSettings,
    configure,
    current_settings,
    register_settings_observer,
    unregister_settings_observer,
)

warnings.warn(
    "freeadmin.core.configuration.conf is deprecated; import from freeadmin.config instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "FreeAdminSettings",
    "configure",
    "current_settings",
    "register_settings_observer",
    "unregister_settings_observer",
]


# The End

