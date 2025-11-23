# -*- coding: utf-8 -*-
"""views

Admin system API views extracted from the legacy AdminAPI class.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from freeadmin.contrib.adapters import BaseAdapter
from freeadmin.core.boot import admin as boot_admin
from freeadmin.config import (
    FreeAdminSettings,
    current_settings,
    register_settings_observer,
)
from freeadmin.core.interface.exceptions import (
    ActionNotFound,
    AdminModelNotFound,
    HTTPError,
    PermissionDenied,
)
from freeadmin.core.interface.permissions import permission_checker
from freeadmin.core.interface.services import PermAction, ScopeQueryService
from freeadmin.core.interface.services.auth import AdminUserDTO
from freeadmin.core.interface.services.tokens import ScopeTokenService
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.runtime.runner import admin_action_runner


class AdminAPIConfiguration:
    """Shared configuration container for admin system API views."""

    class ParamsValidator:
        """Validate action parameters against a schema."""

        def validate(self, schema: dict, params: dict) -> None:
            """Ensure ``params`` follow ``schema`` or raise ``HTTPException``."""

            for name, typ in schema.items():
                if name not in params:
                    raise HTTPException(status_code=400, detail=f"Missing param '{name}'")
                if typ is bool:
                    if type(params[name]) is not bool:
                        raise HTTPException(
                            status_code=400, detail=f"Invalid type for param '{name}'"
                        )
                elif not isinstance(params[name], typ):
                    raise HTTPException(
                        status_code=400, detail=f"Invalid type for param '{name}'"
                    )
            for name in params:
                if name not in schema:
                    raise HTTPException(status_code=400, detail=f"Unexpected param '{name}'")

    def __init__(
        self,
        adapter: BaseAdapter | None = None,
        *,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        """Initialize configuration shared by the admin system API views."""

        self._logger = logging.getLogger(__name__)
        self._adapter = adapter or boot_admin.adapter
        self._does_not_exist = getattr(self._adapter, "DoesNotExist", Exception)
        self._settings = settings or current_settings()
        self._permission_checker = permission_checker
        self._scope_query_service = ScopeQueryService(self._adapter)
        self._scope_token_service = ScopeTokenService(settings=self._settings)
        self.params_validator = self.ParamsValidator()
        self._api_prefix = system_config.get_cached(SettingsKey.API_PREFIX, "/api")
        schema_rel = system_config.get_cached(SettingsKey.API_SCHEMA, "/schema")
        list_filters_rel = system_config.get_cached(
            SettingsKey.API_LIST_FILTERS, "/list_filters"
        )
        lookup_rel = system_config.get_cached(SettingsKey.API_LOOKUP, "/lookup")
        self._schema_path = self.absolute_path(schema_rel)
        self._list_filters_path = self.absolute_path(list_filters_rel)
        self._lookup_path = self.absolute_path(lookup_rel)
        self._actions_path = self.absolute_path("/action")
        register_settings_observer(self.apply_settings)

    @property
    def adapter(self) -> BaseAdapter:
        """Return the ORM adapter bound to the admin site."""

        return self._adapter

    @property
    def does_not_exist(self) -> type[Exception]:
        """Return the adapter-specific ``DoesNotExist`` exception type."""

        return self._does_not_exist

    @property
    def api_prefix(self) -> str:
        """Return the absolute API prefix."""

        return self._api_prefix

    @property
    def schema_path(self) -> str:
        """Return the absolute schema endpoint path."""

        return self._schema_path

    @property
    def list_filters_path(self) -> str:
        """Return the absolute list filters endpoint path."""

        return self._list_filters_path

    @property
    def lookup_path(self) -> str:
        """Return the absolute lookup endpoint base path."""

        return self._lookup_path

    @property
    def actions_path(self) -> str:
        """Return the absolute actions endpoint base path."""

        return self._actions_path

    @property
    def permission_checker(self):
        """Return the permission checker service used by the views."""

        return self._permission_checker

    @property
    def scope_query_service(self) -> ScopeQueryService:
        """Return the scope query service bound to the adapter."""

        return self._scope_query_service

    @property
    def scope_token_service(self) -> ScopeTokenService:
        """Return the scope token service used for signed scopes."""

        return self._scope_token_service

    def apply_settings(self, settings: FreeAdminSettings) -> None:
        """Apply runtime settings updates to dependent services."""

        self._settings = settings
        if hasattr(self._scope_token_service, "apply_settings"):
            self._scope_token_service.apply_settings(settings)

    def absolute_path(self, path: str) -> str:
        """Return ``path`` prefixed with the API prefix when necessary."""

        if path.startswith(self._api_prefix):
            return path
        return f"{self._api_prefix}{path}"

    def relative_path(self, path: str) -> str:
        """Return a router-friendly version of ``path`` relative to the prefix."""

        if path.startswith(self._api_prefix):
            path = path[len(self._api_prefix) :]
        if not path.startswith("/"):
            path = "/" + path
        return path

    def resolve_action_batch_size_default(self) -> int:
        """Return the fallback batch size from application settings when set."""

        fallback = int(getattr(self._settings, "action_batch_size", 0) or 0)
        try:
            from config.settings import settings as app_settings  # type: ignore
        except ModuleNotFoundError:
            return fallback if fallback > 0 else 0
        value = getattr(app_settings, "ACTION_BATCH_SIZE", fallback)
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback if fallback > 0 else 0

    def get_admin(self, admin_site, app: str, model: str):
        """Return the registered admin object for ``app`` and ``model``."""

        try:
            return admin_site.find_admin_or_404(app, model)
        except AdminModelNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


class BaseAdminAPIView:
    """Base helper providing configuration access for admin API views."""

    def __init__(self, config: AdminAPIConfiguration) -> None:
        """Store ``config`` for use by concrete view implementations."""

        self._config = config
        self.logger = logging.getLogger(__name__)

    @property
    def config(self) -> AdminAPIConfiguration:
        """Return the configuration shared with sibling views."""

        return self._config

    @property
    def adapter(self) -> BaseAdapter:
        """Return the ORM adapter bound to the admin site."""

        return self._config.adapter

    @property
    def does_not_exist(self) -> type[Exception]:
        """Return the adapter-specific ``DoesNotExist`` exception type."""

        return self._config.does_not_exist

    @property
    def permission_checker(self):
        """Return the permission checker service."""

        return self._config.permission_checker

    @property
    def scope_query_service(self) -> ScopeQueryService:
        """Return the scope query service for building querysets."""

        return self._config.scope_query_service

    @property
    def scope_token_service(self) -> ScopeTokenService:
        """Return the scope token service used by the views."""

        return self._config.scope_token_service

    @property
    def params_validator(self) -> AdminAPIConfiguration.ParamsValidator:
        """Return the parameter validator shared between views."""

        return self._config.params_validator

    def get_admin(self, admin_site, app: str, model: str):
        """Return the registered admin for ``app`` and ``model`` via config."""

        return self._config.get_admin(admin_site, app, model)


class AdminSchemaView(BaseAdminAPIView):
    """Provide the JSON schema describing admin forms."""

    async def get(
        self,
        request: Request,
        app: str,
        model: str,
        mode: Literal["add", "edit"] = "add",
        pk: str | None = None,
        user: AdminUserDTO = Depends(
            permission_checker.require_model(PermAction.view)
        ),
    ):
        """Return schema metadata for the requested model and mode."""

        admin_site = request.app.state.admin_site
        admin = self.get_admin(admin_site, app, model)
        md = self.adapter.get_model_descriptor(admin.model)
        obj = None
        if mode == "edit" and pk is not None:
            qs = admin.get_objects(request, user)
            try:
                obj = await self.adapter.get(qs, **{md.pk_attr: pk})
            except self.does_not_exist:
                raise HTTPException(status_code=404)
        try:
            schema_data = await admin.get_schema(request, user, md, mode, obj=obj)
        except Exception as exc:  # pragma: no cover - defensive
            field = str(exc) or "unknown"
            self.logger.exception("api_schema failed for %s.%s", app, model)
            raise HTTPException(
                status_code=400, detail=f"Unknown relation target for field {field}"
            ) from exc
        return {"schema": schema_data["schema"], "startval": schema_data["startval"]}


class AdminListFiltersView(BaseAdminAPIView):
    """Expose list filters configured for a registered admin."""

    async def get(
        self,
        request: Request,
        app: str,
        model: str,
        user: AdminUserDTO = Depends(
            permission_checker.require_model(PermAction.view)
        ),
    ):
        """Return list filter descriptors for the requested model."""

        admin_site = request.app.state.admin_site
        admin = self.get_admin(admin_site, app, model)
        md = self.adapter.get_model_descriptor(admin.model)
        return {"filters": admin.get_list_filters(md)}


class AdminLookupView(BaseAdminAPIView):
    """Provide lookup data for relational fields."""

    async def get(
        self,
        request: Request,
        app: str,
        model: str,
        field: str,
        q: str = "",
        page: int = 1,
        pk: str | None = None,
        user: AdminUserDTO = Depends(
            permission_checker.require_model(PermAction.view)
        ),
    ):
        """Return relation choices for ``field`` formatted for widgets."""

        admin_site = request.app.state.admin_site
        admin = self.get_admin(admin_site, app, model)
        md = self.adapter.get_model_descriptor(admin.model)
        fd = md.fields_map.get(field)
        rel = getattr(fd, "relation", None)
        if not fd or not rel or rel.kind not in {"fk", "m2m"}:
            raise HTTPException(status_code=404)
        rel_model = self.adapter.get_model(rel.target)
        if rel_model is None:
            raise HTTPException(status_code=404)
        pairs = await admin.get_choices(fd)
        meta = getattr(fd, "meta", {}) or {}
        raw_default = getattr(fd, "default", None)
        if callable(raw_default):
            raw_default = raw_default()
        is_many = bool(getattr(fd, "many", False) or rel.kind == "m2m")
        if raw_default is not None:
            if is_many:
                if isinstance(raw_default, (list, tuple, set)):
                    default_id = [str(v) for v in raw_default]
                else:
                    default_id = [str(raw_default)]
            else:
                default_id = str(raw_default)
        else:
            default_id = [] if is_many else None
        value: list[str] | str | None
        value = [] if is_many else None
        if pk is not None:
            qs = admin.get_objects(request, user)
            try:
                obj = await self.adapter.get(qs, **{md.pk_attr: pk})
            except self.does_not_exist:
                obj = None
            if obj is not None:
                if is_many:
                    try:
                        related = await getattr(obj, field).all()
                    except Exception:  # pragma: no cover - defensive
                        related = []
                    value = [str(getattr(o, "pk", o)) for o in related]
                else:
                    cur = getattr(obj, f"{field}_id", None)
                    if cur is not None:
                        value = str(cur)
        results = [{"id": pk, "title": label} for pk, label in pairs]
        return {
            "placeholder": meta.get("placeholder"),
            "default": default_id,
            "value": value,
            "results": results,
        }


class AdminActionsListView(BaseAdminAPIView):
    """List available actions for the requested admin model."""

    async def get(
        self,
        request: Request,
        app: str,
        model: str,
        user: AdminUserDTO = Depends(
            permission_checker.require_model(PermAction.view)
        ),
    ):
        """Return metadata describing the available admin actions."""

        admin_site = request.app.state.admin_site
        admin = self.get_admin(admin_site, app, model)
        return admin.get_action_specs(user)


class AdminActionsPreviewView(BaseAdminAPIView):
    """Preview the size of a scope for an action before execution."""

    async def post(
        self,
        request: Request,
        app: str,
        model: str,
        payload: dict = Body(...),
        user: AdminUserDTO = Depends(
            permission_checker.require_model(PermAction.view)
        ),
    ):
        """Return the number of objects affected by the provided scope."""

        admin_site = request.app.state.admin_site
        admin = self.get_admin(admin_site, app, model)
        md = self.adapter.get_model_descriptor(admin.model)
        scope = payload.get("scope")
        if scope is None:
            raise HTTPException(status_code=400, detail="Missing scope")
        try:
            qs = self.scope_query_service.build_queryset(admin, md, request, user, scope)
        except HTTPError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        return {"count": await self.adapter.count(qs)}


class AdminActionRunView(BaseAdminAPIView):
    """Execute an admin action synchronously or in the background."""

    async def post(
        self,
        request: Request,
        app: str,
        model: str,
        action: str,
        payload: dict = Body(...),
        user: AdminUserDTO = Depends(
            permission_checker.require_model(PermAction.view)
        ),
    ):
        """Run the requested action against the resolved queryset."""

        admin_site = request.app.state.admin_site
        admin = self.get_admin(admin_site, app, model)
        action_obj = admin.get_action(action)
        if action_obj is None:
            raise HTTPException(status_code=404)
        spec = action_obj.spec
        if spec.required_perm:
            await self.permission_checker.require_model(
                spec.required_perm,
                app_value=app,
                model_value=model,
                admin_site=admin_site,
            )(request)
        md = self.adapter.get_model_descriptor(admin.model)
        scope = payload.get("scope")
        if scope is None:
            token = payload.get("scope_token")
            if token is None:
                raise HTTPException(status_code=400, detail="Missing scope")
            try:
                scope = self.scope_token_service.verify(token)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid scope_token")
        scope_type = scope.get("type")
        if spec.scope and scope_type not in spec.scope:
            raise HTTPException(status_code=400, detail="Scope type not allowed")
        qs = self.scope_query_service.build_queryset(admin, md, request, user, scope)
        params = payload.get("params", {})
        self.params_validator.validate(spec.params_schema, params)
        affected = await self.adapter.count(qs)
        batch_default = self.config.resolve_action_batch_size_default()
        batch_size = int(system_config.get_cached(SettingsKey.ACTION_BATCH_SIZE, batch_default))
        if affected > batch_size:
            asyncio.create_task(
                admin_action_runner.run(
                    app, model, action, scope, params, user, admin_site=admin_site
                )
            )
            return {"ok": True, "background": True}
        try:
            return await admin_action_runner.run(
                app, model, action, scope, params, user, admin_site=admin_site
            )
        except ActionNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except HTTPError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


class AdminScopeTokenView(BaseAdminAPIView):
    """Issue signed scope tokens that allow delayed action execution."""

    async def post(
        self,
        request: Request,
        app: str,
        model: str,
        payload: dict = Body(...),
        user: AdminUserDTO = Depends(
            permission_checker.require_model(PermAction.view)
        ),
    ):
        """Return a signed token encoding the provided action scope."""

        admin_site = request.app.state.admin_site
        admin = self.get_admin(admin_site, app, model)
        md = self.adapter.get_model_descriptor(admin.model)
        scope = payload.get("scope")
        if scope is None:
            raise HTTPException(status_code=400, detail="Missing scope")
        try:
            _ = self.scope_query_service.build_queryset(admin, md, request, user, scope)
        except HTTPError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        ttl = int(payload.get("ttl", 60))
        token = self.scope_token_service.sign(scope, ttl)
        return {"scope_token": token}


class AdminAPIViewSet:
    """Bundle all admin system API views for easy router registration."""

    def __init__(self, config: AdminAPIConfiguration | None = None) -> None:
        """Create the view set and instantiate individual views."""

        self._config = config or AdminAPIConfiguration()
        self.schema = AdminSchemaView(self._config)
        self.list_filters = AdminListFiltersView(self._config)
        self.lookup = AdminLookupView(self._config)
        self.actions_list = AdminActionsListView(self._config)
        self.actions_preview = AdminActionsPreviewView(self._config)
        self.action_run = AdminActionRunView(self._config)
        self.scope_token = AdminScopeTokenView(self._config)

    @property
    def config(self) -> AdminAPIConfiguration:
        """Return the configuration shared by the view set."""

        return self._config

    def register(self, router: APIRouter) -> None:
        """Attach all view handlers to ``router`` using configured paths."""

        router.get(
            self._config.relative_path(self._config.schema_path),
            name="admin.api.schema",
        )(self.schema.get)
        router.get(
            self._config.relative_path(self._config.list_filters_path),
            name="admin.api.list_filters",
        )(self.list_filters.get)
        router.get(
            f"{self._config.relative_path(self._config.lookup_path)}/{{app}}/{{model}}/{{field}}",
            name="admin.api.lookup",
        )(self.lookup.get)
        router.get(
            f"{self._config.relative_path(self._config.actions_path)}/{{app}}.{{model}}/list",
            name="admin.api.actions_list",
        )(self.actions_list.get)
        router.post(
            f"{self._config.relative_path(self._config.actions_path)}/{{app}}.{{model}}/preview",
            name="admin.api.actions_preview",
        )(self.actions_preview.post)
        router.post(
            f"{self._config.relative_path(self._config.actions_path)}/{{app}}.{{model}}/{{action}}",
            name="admin.api.action_run",
        )(self.action_run.post)
        router.post(
            f"{self._config.relative_path(self._config.actions_path)}/{{app}}.{{model}}/token",
            name="admin.api.scope_token",
        )(self.scope_token.post)


__all__ = [
    "AdminAPIConfiguration",
    "AdminAPIViewSet",
    "AdminActionRunView",
    "AdminActionsListView",
    "AdminActionsPreviewView",
    "AdminListFiltersView",
    "AdminLookupView",
    "AdminSchemaView",
    "AdminScopeTokenView",
]

# The End

