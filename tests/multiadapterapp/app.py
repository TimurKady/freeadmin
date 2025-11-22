# -*- coding: utf-8 -*-
"""Application configuration registering admins during startup."""

from __future__ import annotations

from importlib import import_module

from freeadmin.core.interface.app import AppConfig
from tests.multiadapterapp.models import MultiAdapterModel


class MultiAdapterAdmin:
    """Registerable admin class storing adapter references for assertions."""

    def __init__(self, site, app_label: str, model_slug: str, adapter) -> None:
        """Store the adapter used for registration and basic metadata."""

        self.site = site
        self.app_label = app_label
        self.model_slug = model_slug
        self.adapter = adapter

    def get_verbose_name_plural(self) -> str:
        """Return the human-readable name for menu rendering."""

        return "Adapters"


class MultiAdapterAppConfig(AppConfig):
    """Track lifecycle hooks and register admin definitions for testing."""

    app_label = "multiadapter"
    name = "tests.multiadapterapp"

    def __init__(self) -> None:
        """Initialize counters verifying startup execution."""

        super().__init__()
        self.ready_calls = 0

    async def startup(self) -> None:
        """Register admin entries to drive menu and registry assertions."""

        self.ready_calls += 1
        runtime_hub = import_module("freeadmin.core.runtime.hub")
        runtime_hub.admin_site.register(
            app=self.app_label,
            model=MultiAdapterModel,
            admin_cls=MultiAdapterAdmin,
            icon="bi-stars",
        )


default = MultiAdapterAppConfig()

__all__ = ["MultiAdapterAppConfig", "default", "MultiAdapterAdmin"]


# The End
