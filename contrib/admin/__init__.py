# -*- coding: utf-8 -*-
"""
__init__

Admin module entry point.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from contrib.admin.core.site import AdminSite
from contrib.admin.core.base import BaseModelAdmin
from contrib.admin.router import mount_admin

__all__ = [
    "AdminSite",
    "BaseModelAdmin",
    "mount_admin",
]

__version__ = "0.1.0-dev"

# The End
