# -*- coding: utf-8 -*-
"""
user

Admin panel configuration for AdminUser model.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from contrib.admin.core.model import ModelAdmin
from contrib.admin.hub import admin_site

from ..models.users import AdminUser

class AdminUserAdmin(ModelAdmin):
    """Admin configuration for :class:`AdminUser`."""

    model = AdminUser
    fields = ("username", "email", "is_staff", "is_superuser", "is_active",)
    list_display = ("username", "email", "is_staff", "is_superuser", "is_active",)
    list_filter = ("username", "email", "is_staff", "is_superuser", "is_active",)


admin_site.register(app="admin", model=AdminUser, admin_cls=AdminUserAdmin, settings=True, icon="bi-person")

# The End
