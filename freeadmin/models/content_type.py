# -*- coding: utf-8 -*-
"""content_type

Adapter-backed admin content type model exports.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from freeadmin.core.boot import admin as boot_admin

try:
    AdminContentType = boot_admin.adapter.content_type_model
except ModuleNotFoundError:  # pragma: no cover - during adapter bootstrap
    AdminContentType = object  # type: ignore[assignment]


# The End

