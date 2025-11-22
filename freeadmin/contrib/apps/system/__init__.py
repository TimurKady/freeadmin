# -*- coding: utf-8 -*-
"""__init__

System application package exports.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from .apps import SystemAppConfig, default_app_config
from .admin import (
    AdminGroupAdmin,
    AdminGroupPermissionAdmin,
    AdminUserAdmin,
    AdminUserPermissionAdmin,
    SystemSettingAdmin,
)
from .exports import (
    AdminContentType,
    AdminGroup,
    AdminGroupPermission,
    AdminUser,
    AdminUserPermission,
    PermAction,
    SettingValueType,
    SystemSetting,
)
from .urls import SystemURLRegistrar
from .views import BuiltinPagesRegistrar, BuiltinUserMenuRegistrar

__all__ = [
    "SystemAppConfig",
    "default_app_config",
    "AdminGroupAdmin",
    "AdminGroupPermissionAdmin",
    "AdminUserAdmin",
    "AdminUserPermissionAdmin",
    "SystemSettingAdmin",
    "AdminContentType",
    "AdminGroup",
    "AdminGroupPermission",
    "AdminUser",
    "AdminUserPermission",
    "PermAction",
    "SettingValueType",
    "SystemSetting",
    "SystemURLRegistrar",
    "BuiltinPagesRegistrar",
    "BuiltinUserMenuRegistrar",
]


# The End
