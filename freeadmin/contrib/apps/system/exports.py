# -*- coding: utf-8 -*-
"""exports

Adapter-facing exports for the system application.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from freeadmin.core.boot import BootManager, admin as boot_admin


class SystemAdapterExports:
    """Expose adapter-backed models and helpers for the system app."""

    def __init__(self, boot_manager: BootManager | None = None) -> None:
        """Store boot manager used to resolve adapter-bound classes."""

        self._boot = boot_manager or boot_admin

    @property
    def boot_manager(self) -> BootManager:
        """Return the boot manager powering these exports."""

        return self._boot

    @boot_manager.setter
    def boot_manager(self, boot_manager: BootManager) -> None:
        """Update the boot manager backing adapter-bound attributes."""

        self._boot = boot_manager

    @property
    def adapter(self):
        """Return the active adapter powering the system application."""

        return self._boot.adapter

    def _get_attribute(self, name: str):
        adapter = self.adapter
        try:
            return getattr(adapter, name)
        except AttributeError as exc:  # pragma: no cover - protective guard
            adapter_name = getattr(adapter, "name", "unknown")
            raise RuntimeError(
                f"Adapter '{adapter_name}' is missing required attribute '{name}'."
            ) from exc

    @property
    def admin_group(self):
        """Return the adapter-provided admin group model."""

        return self._get_attribute("group_model")

    @property
    def admin_group_permission(self):
        """Return the adapter-provided admin group permission model."""

        return self._get_attribute("group_permission_model")

    @property
    def admin_user(self):
        """Return the adapter-provided admin user model."""

        return self._get_attribute("user_model")

    @property
    def admin_user_permission(self):
        """Return the adapter-provided admin user permission model."""

        return self._get_attribute("user_permission_model")

    @property
    def system_setting(self):
        """Return the adapter-provided system setting model."""

        return self._get_attribute("system_setting_model")

    @property
    def admin_content_type(self):
        """Return the adapter-provided admin content type model."""

        return self._get_attribute("content_type_model")

    @property
    def perm_action(self):
        """Return the adapter-provided permission action enumeration."""

        return self._get_attribute("perm_action")

    @property
    def setting_value_type(self):
        """Return the adapter-provided setting value enumeration."""

        return self._get_attribute("setting_value_type")


_exports = SystemAdapterExports()

AdminGroup = _exports.admin_group
AdminGroupPermission = _exports.admin_group_permission
AdminUser = _exports.admin_user
AdminUserPermission = _exports.admin_user_permission
SystemSetting = _exports.system_setting
AdminContentType = _exports.admin_content_type
PermAction = _exports.perm_action
SettingValueType = _exports.setting_value_type

__all__ = [
    "SystemAdapterExports",
    "AdminGroup",
    "AdminGroupPermission",
    "AdminUser",
    "AdminUserPermission",
    "SystemSetting",
    "AdminContentType",
    "PermAction",
    "SettingValueType",
]


# The End

