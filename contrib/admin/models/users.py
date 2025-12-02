# -*- coding: utf-8 -*-
"""
users

Admin user models.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from tortoise import fields
from tortoise.models import Model


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

# The End
