# -*- coding: utf-8 -*-
"""
admins

Adapter-agnostic administrative configuration for built-in system models.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import Select2Widget

from .exports import SystemAdapterExports


@dataclass
class SystemAdminRegistration:
    """Describe a model admin registration payload."""

    app: str
    model: type
    admin_cls: type
    settings: bool = False
    icon: str | None = None

    def register(self, site) -> None:
        """Register this admin entry against ``site``."""

        site.register(
            app=self.app,
            model=self.model,
            admin_cls=self.admin_cls,
            settings=self.settings,
            icon=self.icon,
        )


class SystemAdminRegistrar:
    """Register adapter-aware system admins against an admin site."""

    def __init__(self, exports: SystemAdapterExports | None = None) -> None:
        """Store adapter exports used to resolve models for admin classes."""

        self._exports = exports or SystemAdapterExports()

    @property
    def exports(self) -> SystemAdapterExports:
        """Return adapter exports providing model and enumeration bindings."""

        return self._exports

    def iter_registrations(self) -> Iterable[SystemAdminRegistration]:
        """Yield registration descriptors for all system admins."""

        export = self.exports
        return (
            SystemAdminRegistration(
                app="admin",
                model=export.admin_group,
                admin_cls=AdminGroupAdmin,
                settings=True,
                icon="bi-people",
            ),
            SystemAdminRegistration(
                app="admin",
                model=export.admin_user_permission,
                admin_cls=AdminUserPermissionAdmin,
                settings=True,
                icon="bi-person-lock",
            ),
            SystemAdminRegistration(
                app="admin",
                model=export.admin_group_permission,
                admin_cls=AdminGroupPermissionAdmin,
                settings=True,
                icon="bi-shield-lock",
            ),
            SystemAdminRegistration(
                app="admin",
                model=export.admin_user,
                admin_cls=AdminUserAdmin,
                settings=True,
                icon="bi-person",
            ),
            SystemAdminRegistration(
                app="core",
                model=export.system_setting,
                admin_cls=SystemSettingAdmin,
                settings=True,
                icon="bi-gear",
            ),
        )

    def register(self, site) -> None:
        """Register all system admin classes on the provided ``site``."""

        for registration in self.iter_registrations():
            registration.register(site)


_exports = SystemAdapterExports()


class AdminGroupAdmin(ModelAdmin):
    """Admin configuration for the adapter-provided admin group model."""

    model = _exports.admin_group
    list_display = ("name", "description")


class AdminUserPermissionAdmin(ModelAdmin):
    """Admin configuration for the adapter-provided admin user permission."""

    model = _exports.admin_user_permission
    list_display = ("user", "content_type", "action")

    class Meta:
        """Widget overrides for AdminUserPermission admin form."""

        widgets = {
            "content_type": Select2Widget(),
        }


class AdminGroupPermissionAdmin(ModelAdmin):
    """Admin configuration for the adapter-provided admin group permission."""

    model = _exports.admin_group_permission
    list_display = ("group", "content_type", "action")


class AdminUserAdmin(ModelAdmin):
    """Admin configuration for the adapter-provided admin user model."""

    model = _exports.admin_user
    fields = ("username", "email", "is_staff", "is_superuser", "is_active")
    list_display = ("username", "email", "is_staff", "is_superuser", "is_active")
    list_filter = ("username", "email", "is_staff", "is_superuser", "is_active")


class SystemSettingAdmin(ModelAdmin):
    """Admin configuration for the adapter-provided system settings model."""

    model = _exports.system_setting
    label = "System Settings"
    label_singular = "System Setting"
    list_display = ("name", "key", "value")
    list_filter = ("name", "key", "value")
    fields = ("name", "key", "value", "value_type", "meta")

    class Meta:
        """Meta options for :class:`SystemSettingAdmin`."""

        pass


__all__ = [
    "AdminGroupAdmin",
    "AdminGroupPermissionAdmin",
    "AdminUserAdmin",
    "AdminUserPermissionAdmin",
    "SystemSettingAdmin",
    "SystemAdminRegistrar",
    "SystemAdminRegistration",
]


# The End
