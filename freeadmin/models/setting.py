# -*- coding: utf-8 -*-
"""setting

Adapter-backed admin system setting model exports.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from freeadmin.core.boot import admin as boot_admin

try:
    SystemSetting = boot_admin.adapter.system_setting_model
except ModuleNotFoundError:  # pragma: no cover - during adapter bootstrap
    SystemSetting = object  # type: ignore[assignment]


# The End

