# -*- coding: utf-8 -*-
"""groups

Adapter-backed admin group model exports.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from freeadmin.core.boot import admin as boot_admin

try:
    AdminGroup = boot_admin.adapter.group_model
    AdminGroupPermission = boot_admin.adapter.group_permission_model
except ModuleNotFoundError:  # pragma: no cover - during adapter bootstrap
    AdminGroup = object  # type: ignore[assignment]
    AdminGroupPermission = object  # type: ignore[assignment]


# The End

