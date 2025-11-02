# -*- coding: utf-8 -*-
"""users

Adapter-backed admin user model exports.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from freeadmin.core.boot import admin as boot_admin

try:
    AdminUser = boot_admin.adapter.user_model
    AdminUserPermission = boot_admin.adapter.user_permission_model
except ModuleNotFoundError:  # pragma: no cover - during adapter bootstrap
    AdminUser = object  # type: ignore[assignment]
    AdminUserPermission = object  # type: ignore[assignment]


# The End

