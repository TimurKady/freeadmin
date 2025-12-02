# -*- coding: utf-8 -*-
"""
model

ModelAdmin implementation.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from .base import BaseModelAdmin
from .inline import InlineAdmin


class ModelAdmin(BaseModelAdmin):
    """ORM Model Admin Class."""

    # IMPORTANT: use a tuple + forward-link string;
    # It's the most trouble-free option at runtime
    inlines: tuple[type["InlineAdmin"], ...] = ()

# The End
