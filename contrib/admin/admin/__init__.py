# -*- coding: utf-8 -*-
"""
__init__

Admin registrations for admin models.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from .user import AdminUserAdmin
from .rbac import (
    AdminGroupAdmin,
    AdminUserPermissionAdmin,
    AdminGroupPermissionAdmin,
)
from .setting import SystemSettingAdmin

__all__ = [
    "AdminUserAdmin",
    "AdminGroupAdmin",
    "AdminUserPermissionAdmin",
    "AdminGroupPermissionAdmin",
    "SystemSettingAdmin",
]

# The End
