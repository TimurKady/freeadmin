# -*- coding: utf-8 -*-
"""
users

Admin user models and permissions.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from tortoise import fields
from tortoise.models import Model

from ....models.choices import StrChoices
from .content_type import AdminContentType


class PermAction(StrChoices):
    """Available actions that can be granted as permissions."""

    view = "view", "View"
    add = "add", "Add"
    change = "change", "Change"
    delete = "delete", "Delete"
    export = "export", "Export"
    import_ = "import", "Import"

setattr(PermAction, "import", PermAction.import_)


class AdminUser(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=150, unique=True)
    email = fields.CharField(max_length=254, null=True)
    password = fields.CharField(max_length=200, null=False, default="")

    is_staff = fields.BooleanField(default=False)
    is_superuser = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)

    # Real groups/permissions not connected yet
    # groups: M2M -> AdminGroup
    # permissions: M2M -> AdminPermission

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.username


class AdminUserPermission(Model):
    """User permission on a model (or global, if content_type is NULL)."""

    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation[AdminUser] = fields.ForeignKeyField(
        "admin.AdminUser", related_name="user_permissions", on_delete=fields.CASCADE
    )
    content_type: fields.ForeignKeyNullableRelation[AdminContentType] = fields.ForeignKeyField(
        "admin.AdminContentType", related_name="user_permissions", null=True, on_delete=fields.CASCADE
    )
    action = fields.CharEnumField(PermAction, index=True)

    class Meta:
        table = "admin_user_permissions"
        unique_together = (("user", "content_type", "action"),)
        indexes = (("user_id", "action", "content_type_id"),)
        verbose_name = "User permissions"
        verbose_name_plural = "User permissions"

    def __str__(self) -> str:
        ctd = self.content_type.dotted if self.content_type_id else "*"
        return f"{self.user_id}:{ctd}:{self.action}"

# The End

