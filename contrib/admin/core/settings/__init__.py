# -*- coding: utf-8 -*-
"""
__init__

Settings constants and enums.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from .keys import SettingsKey

from .defaults import DEFAULT_SETTINGS
from .config import system_config

__all__ = ["SettingsKey", "DEFAULT_SETTINGS", "system_config"]

# The End
