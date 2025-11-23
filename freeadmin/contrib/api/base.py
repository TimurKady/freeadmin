# -*- coding: utf-8 -*-
"""base

Compatibility wrapper around the admin system API view set.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from fastapi import APIRouter

from ..adapters import BaseAdapter
from freeadmin.config import FreeAdminSettings


class AdminAPI:
    """Provide backward-compatible access to the admin system API views."""

    class ParamsValidator:
        """Delegate validation to the system API configuration lazily."""

        def validate(self, schema: dict, params: dict) -> None:
            """Ensure ``params`` follow ``schema`` using the system API validator."""

            from ..apps.system.api.views import AdminAPIConfiguration

            AdminAPIConfiguration.ParamsValidator().validate(schema, params)

    def __init__(
        self,
        adapter: BaseAdapter | None = None,
        *,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        """Initialize the wrapper with optional adapter and settings overrides."""

        from ..apps.system.api.views import AdminAPIViewSet, AdminAPIConfiguration

        config = AdminAPIConfiguration(adapter=adapter, settings=settings)

        self.viewset = AdminAPIViewSet(config)
        self.router = APIRouter()
        self.viewset.register(self.router)
        self.API_PREFIX = config.api_prefix
        self.adapter = config.adapter
        self.DoesNotExist = config.does_not_exist
        self.permission_checker = config.permission_checker
        self.scope_query_service = config.scope_query_service
        self.scope_token_service = config.scope_token_service
        self.params_validator = config.params_validator
        self._config = config

    async def api_schema(self, *args, **kwargs):
        """Delegate schema retrieval to the view set."""

        return await self.viewset.schema.get(*args, **kwargs)

    async def api_list_filters(self, *args, **kwargs):
        """Delegate list filter retrieval to the view set."""

        return await self.viewset.list_filters.get(*args, **kwargs)

    async def api_lookup(self, *args, **kwargs):
        """Delegate lookup handling to the view set."""

        return await self.viewset.lookup.get(*args, **kwargs)

    async def actions_list(self, *args, **kwargs):
        """Delegate action enumeration to the view set."""

        return await self.viewset.actions_list.get(*args, **kwargs)

    async def actions_preview(self, *args, **kwargs):
        """Delegate action preview handling to the view set."""

        return await self.viewset.actions_preview.post(*args, **kwargs)

    async def action_run(self, *args, **kwargs):
        """Delegate action execution to the view set."""

        return await self.viewset.action_run.post(*args, **kwargs)

    async def scope_token(self, *args, **kwargs):
        """Delegate scope token issuance to the view set."""

        return await self.viewset.scope_token.post(*args, **kwargs)


__all__ = ["AdminAPI"]

# The End

