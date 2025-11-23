# -*- coding: utf-8 -*-
"""
site

Compatibility wrapper exposing ``AdminSite`` from the interface package.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import warnings

from freeadmin.admin import AdminSite

warnings.warn(
    "freeadmin.core.site is deprecated; import AdminSite from freeadmin.admin instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["AdminSite"]


# The End

