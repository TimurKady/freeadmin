# -*- coding: utf-8 -*-
"""
boot

Utility helpers for bootstrapping the admin app.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from fastapi import FastAPI

from .core.settings.config import system_config


def register_startup(app: FastAPI) -> None:
    """Register system configuration startup hooks."""

    @app.on_event("startup")
    async def _load_system_config() -> None:
        await system_config.ensure_seed()
        await system_config.reload()

# The End
