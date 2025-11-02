# -*- coding: utf-8 -*-
"""models

Single point of connection of Admin Models.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from .choices import IntChoices, StrChoices  # noqa: F401
from .content_type import AdminContentType  # noqa: F401
from .groups import AdminGroup, AdminGroupPermission  # noqa: F401
from .setting import SystemSetting  # noqa: F401
from .users import AdminUser, AdminUserPermission  # noqa: F401
from ._registry import (  # noqa: F401
    ModelBase,
    PermAction,
    SettingValueType,
    adapter,
    __all__,
    __models__,
)


# The End
