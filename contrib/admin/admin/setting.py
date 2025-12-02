# -*- coding: utf-8 -*-
"""
setting

Admin configuration for core system settings.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from contrib.admin.core.model import ModelAdmin
from contrib.admin.hub import admin_site
from ..models.setting import SystemSetting


class SystemSettingAdmin(ModelAdmin):
    """Admin configuration for :class:`SystemSetting`."""

    model = SystemSetting
    # Friendly names for the admin UI
    label = "System Settings"
    label_singular = "System Setting"
    list_display = ("name", "key", "value")
    list_filter = ("name", "key", "value")
    fields = ("name", "key", "value", "value_type", "meta")

    class Meta:
        """Meta options for :class:`SystemSettingAdmin`."""
        pass


admin_site.register(
    app="core",
    model=SystemSetting,
    admin_cls=SystemSettingAdmin,
    settings=True,
    icon="bi-gear",
)

# The End
