# -*- coding: utf-8 -*-
"""
auth_service

Service utilities for admin authentication.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from ..models.users import AdminUser as AdminUserORM
from ..utils.passwords import check_password, make_password


async def authenticate_user(username: str, password: str) -> AdminUserORM | None:
    """Return user if credentials are valid."""
    user = await AdminUserORM.get_or_none(username=username)
    if (
        not user
        or not user.is_active
        or not user.is_staff
        or not await check_password(password, user.password)
    ):
        return None
    return user


async def superuser_exists() -> bool:
    """Check if a superuser already exists."""
    return await AdminUserORM.filter(is_staff=True, is_superuser=True).exists()


async def create_superuser(username: str, email: str, password: str) -> AdminUserORM:
    """Create a new superuser."""
    return await AdminUserORM.create(
        username=username,
        email=email,
        password=await make_password(password),
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )

# The End
