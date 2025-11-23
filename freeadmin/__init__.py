"""
__init__

Admin module entry point.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from .application import ApplicationFactory
from freeadmin.config import FreeAdminSettings, configure, current_settings
from .core.interface.base import BaseModelAdmin
from freeadmin.admin import AdminSite
from freeadmin.core.network_router import AdminRouter
from .meta import __version__

# The End

