# -*- coding: utf-8 -*-
"""
crud

Utility for mounting CRUD routes on FastAPI routers.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, TYPE_CHECKING

import mimetypes
import re
import sys
import types
import warnings
from fastapi import APIRouter, Body, Depends, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.routing import NoMatchFound

from importlib import import_module

from freeadmin.config import current_settings
from freeadmin.core.interface.services.auth import AdminUserDTO
from freeadmin.core.interface.auth import admin_auth_service
from freeadmin.core.interface.base import BaseModelAdmin
from freeadmin.core.interface.permissions import permission_checker
from freeadmin.core.interface.services import PermAction, ScopeTokenService
from freeadmin.core.interface.services.admin import AdminService
from freeadmin.core.interface.services.export import ExportService
from freeadmin.core.interface.exceptions import HTTPError
from freeadmin.core.interface.settings import SettingsKey, system_config

ImportService = import_module(
    "freeadmin.core.interface.services.import"
).ImportService


if TYPE_CHECKING:
    from freeadmin.admin import AdminSite


MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


class SafePathSegment(str):
    """String subclass enforcing safe path segments."""

    _pattern = re.compile(r"^[A-Za-z0-9_-]+$")

    def __new__(cls, value: str) -> "SafePathSegment":
        if ".." in value or not cls._pattern.fullmatch(value):
            raise HTTPException(status_code=400, detail="Invalid path segment")
        return str.__new__(cls, value)


class AsyncFileSaver:
    """Store uploaded files asynchronously with size checks."""

    chunk_size = 1 << 20  # 1MB

    def __init__(self, upload: UploadFile, dest: Path, limit: int = MAX_UPLOAD_SIZE):
        self.upload = upload
        self.dest = dest
        self.limit = limit

    async def save(self) -> None:
        size = 0
        fh = await run_in_threadpool(open, self.dest, "wb")
        try:
            while True:
                chunk = await self.upload.read(self.chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.limit:
                    await self.upload.close()
                    await run_in_threadpool(fh.close)
                    self.dest.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File too large")
                await run_in_threadpool(fh.write, chunk)
        finally:
            await run_in_threadpool(fh.close)
        await self.upload.close()


class CrudRouterBuilder:
    """Helper to attach standard CRUD routes for admin classes."""

    @staticmethod
    def mount(
        router: APIRouter,
        *,
        admin_site: AdminSite,
        prefix: str,
        admin_cls: type[BaseModelAdmin],
        perms: Literal["model", "global"],
        app_label: str,
    ) -> APIRouter:
        """Mount standard CRUD routes for ``admin_cls`` on ``router``.

        ``prefix`` is the base path. ``perms`` controls whether permissions are
        checked against a specific model (``"model"``) or globally
        (``"global"``).
        """

        templates = getattr(router, "templates", None)
        if templates is None:
            base_dir = Path(__file__).resolve().parents[2]
            templates = Jinja2Templates(directory=str(base_dir / "templates"))

        adapter = getattr(admin_site, "adapter", None)
        if adapter is None:
            from freeadmin.core.boot import admin as boot_admin  # pragma: no cover
            adapter = boot_admin.adapter
        admin = admin_cls(admin_cls.model, adapter)
        setattr(admin, "app_label", app_label)
        model_slug_func = getattr(admin_site, "_model_to_slug", lambda n: n.lower())
        model_slug = model_slug_func(admin_cls.model.__name__)
        export_endpoint_name = f"{app_label}_{model_slug}_export_wizard"
        import_endpoint_name = f"{app_label}_{model_slug}_import_wizard"
        import_preview_name = f"{app_label}_{model_slug}_import_preview"
        import_run_name = f"{app_label}_{model_slug}_import_run"
        admin.export_endpoint_name = export_endpoint_name
        admin.import_endpoint_name = import_endpoint_name
        admin.import_preview_endpoint_name = import_preview_name
        admin.import_run_endpoint_name = import_run_name
        service = AdminService(admin)
        md = service.md
        export_service = ExportService(adapter)
        import_service = ImportService()
        scope_token_service = ScopeTokenService()

        perm_view: Callable[[Request], Awaitable[Any]]
        perm_add: Callable[[Request], Awaitable[Any]]
        perm_change: Callable[[Request], Awaitable[Any]]
        perm_delete: Callable[[Request], Awaitable[Any]]
        perm_export: Callable[[Request], Awaitable[Any]]
        perm_import: Callable[[Request], Awaitable[Any]]
        checker = permission_checker
        if perms == "global":
            perm_view = checker.require_view(PermAction.view, admin_site=admin_site)
            perm_add = checker.require_view(PermAction.add, admin_site=admin_site)
            perm_change = checker.require_view(PermAction.change, admin_site=admin_site)
            perm_delete = checker.require_view(PermAction.delete, admin_site=admin_site)
            if admin.perm_export:
                perm_export = checker.require_view(admin.perm_export, admin_site=admin_site)
            else:
                async def perm_export(request: Request) -> None:
                    return None
            if admin.perm_import:
                perm_import = checker.require_view(admin.perm_import, admin_site=admin_site)
            else:
                async def perm_import(request: Request) -> None:
                    return None
        else:
            perm_view = checker.require_model(
                PermAction.view,
                app_value=app_label,
                model_value=model_slug,
                admin_site=admin_site,
            )
            perm_add = checker.require_model(
                PermAction.add,
                app_value=app_label,
                model_value=model_slug,
                admin_site=admin_site,
            )
            perm_change = checker.require_model(
                PermAction.change,
                app_value=app_label,
                model_value=model_slug,
                admin_site=admin_site,
            )
            perm_delete = checker.require_model(
                PermAction.delete,
                app_value=app_label,
                model_value=model_slug,
                admin_site=admin_site,
            )
            if admin.perm_export:
                perm_export = checker.require_model(
                    admin.perm_export,
                    app_value=app_label,
                    model_value=model_slug,
                    admin_site=admin_site,
                )
            else:
                async def perm_export(request: Request) -> None:
                    return None
            if admin.perm_import:
                perm_import = checker.require_model(
                    admin.perm_import,
                    app_value=app_label,
                    model_value=model_slug,
                    admin_site=admin_site,
                )
            else:
                async def perm_import(request: Request) -> None:
                    return None

        # model descriptor already provided by the service

        @router.api_route(
            prefix + "/export/",
            methods=["GET", "POST"],
            response_class=HTMLResponse,
            name=export_endpoint_name,
        )
        async def export_wizard(
            request: Request,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_export),
        ) -> HTMLResponse:
            request.state.user_dto = user
            if not admin.has_export_perm(request):
                raise HTTPException(status_code=404)
            ctx = admin_site.build_template_ctx(
                request,
                user,
                page_title="Export",
                app_label=app_label,
                model_name=model_slug,
            )
            ctx["fields"] = list(admin.get_export_fields())
            return templates.TemplateResponse("context/export.html", ctx)

        @router.api_route(
            prefix + "/import/",
            methods=["GET", "POST"],
            response_class=HTMLResponse,
            name=import_endpoint_name,
        )
        async def import_wizard(
            request: Request,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_import),
        ) -> HTMLResponse:
            request.state.user_dto = user
            if not admin.has_import_perm(request):
                raise HTTPException(status_code=404)
            ctx = admin_site.build_template_ctx(
                request,
                user,
                page_title="Import",
                app_label=app_label,
                model_name=model_slug,
            )
            ctx.update(
                fields=list(admin.get_import_fields()),
                required=set(admin.get_required_import_fields()),
            )
            return templates.TemplateResponse("context/import.html", ctx)

        @router.get(prefix + "/", response_class=HTMLResponse)
        async def list_page(
            request: Request,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_view),
        ) -> HTMLResponse:
            request.state.user_dto = user
            can_add = admin.allow(user, "add")
            export_url = None
            if admin.has_export_perm(request):
                try:
                    export_url = request.url_for(admin.export_endpoint_name)
                except NoMatchFound:
                    export_url = None
            import_url = None
            if admin.has_import_perm(request):
                try:
                    import_url = request.url_for(admin.import_endpoint_name)
                except NoMatchFound:
                    import_url = None
            ctx = admin_site.build_template_ctx(
                request,
                user,
                app_label=app_label,
                model_name=model_slug,
                is_settings=(perms == "global"),
                extra={
                    "admin": admin,
                    "can_add": can_add,
                    "can_export": bool(export_url),
                    "can_import": bool(import_url),
                    "export_url": export_url,
                    "import_url": import_url,
                    "has_list_filters": bool(admin.get_list_filter()),
                    "has_search": bool(admin.get_search_fields(md)),
                },
            )
            return templates.TemplateResponse("context/list.html", ctx)

        @router.get(prefix + "/add", response_class=HTMLResponse)
        async def add_page(
            request: Request,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_add),
        ) -> HTMLResponse:
            title = f"Add {admin.get_verbose_name()}"
            ctx = admin_site.build_template_ctx(
                request,
                user,
                page_title=title,
                app_label=app_label,
                model_name=model_slug,
                is_settings=(perms == "global"),
            )
            md = admin.adapter.get_model_descriptor(admin.model)
            assets = admin.collect_assets(md, mode="add", obj=None, request=request)
            ctx["assets"] = assets
            return templates.TemplateResponse("context/form.html", ctx)

        @router.get(prefix + "/{pk}/edit", response_class=HTMLResponse)
        async def edit_page(
            request: Request,
            pk: str,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_change),
        ) -> HTMLResponse:
            try:
                obj = await service.get_object(request, user, pk)
            except HTTPError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
            title = f"Edit {admin.get_verbose_name()}"
            ctx = admin_site.build_template_ctx(
                request,
                user,
                page_title=title,
                app_label=app_label,
                model_name=model_slug,
                is_settings=(perms == "global"),
                extra={"pk": pk},
            )
            md = admin.adapter.get_model_descriptor(admin.model)
            assets = admin.collect_assets(md, mode="edit", obj=obj, request=request)
            ctx["assets"] = assets
            return templates.TemplateResponse("context/form.html", ctx)

        @router.get(prefix + "/{pk}/_inlines")
        async def inline_specs(
            request: Request,
            pk: str,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_change),
        ):
            try:
                obj = await service.get_object(request, user, pk)
            except HTTPError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
            return await admin.get_inlines_spec(request, user, obj)

        # form schema served via global API; no local endpoint

        @router.get(prefix + "/_list")
        async def list_data(
            request: Request,
            search: str = "",
            page_num: int = 1,
            per_page: int | None = None,
            order: str = "",
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_view),
        ):
            try:
                return await service.list_data(
                    request, user, search, page_num, per_page, order
                )
            except HTTPError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        @router.get(prefix + "/_actions")
        async def action_specs(
            request: Request,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_view),
        ):
            return admin.get_action_specs(user)

        @router.post(prefix + "/_actions/token")
        async def action_scope_token(
            request: Request,
            payload: dict = Body(...),
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_view),
        ):
            scope = payload.get("scope")
            if scope is None:
                raise HTTPException(status_code=400, detail="Missing scope")
            token = scope_token_service.sign(scope, 300)
            return {"scope_token": token}

        @router.post(prefix + "/_actions/{name}")
        async def run_action(
            request: Request,
            name: str,
            payload: dict = Body(...),
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_view),
        ):
            try:
                return await service.run_action(
                    request, user, name, payload, app_label, model_slug
                )
            except HTTPError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        @router.post(prefix + "/export")
        async def export_data(
            request: Request,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_export),
        ):
            request.state.user_dto = user
            if not admin.has_export_perm(request):
                raise HTTPException(status_code=404)
            qs = admin.get_objects(request, user)
            fields = list(admin.get_export_fields())
            data = await export_service.export(qs, fields)
            return {"rows": data}

        @router.post(prefix + "/import")
        async def import_data(
            request: Request,
            payload: dict = Body(...),
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_import),
        ):
            request.state.user_dto = user
            if not admin.has_import_perm(request):
                raise HTTPException(status_code=404)
            rows = payload.get("rows", [])
            dry = bool(payload.get("dry", False))
            allowed = set(admin.get_import_fields())
            cleaned: list[dict[str, Any]] = []
            for row in rows:
                extra = set(row) - allowed
                if extra and getattr(admin, "import_strict", True):
                    names = ", ".join(sorted(extra))
                    raise HTTPException(status_code=400, detail=f"Unexpected field(s): {names}")
                cleaned.append({k: row.get(k) for k in allowed if k in row})
            count = len(cleaned)
            if not dry:
                count = await import_service.import_rows(admin, cleaned)
            return {"count": count, "dry": dry}

        async def _perm_upload(request: Request) -> None:
            try:
                await perm_add(request)
            except HTTPException:
                await perm_change(request)

        @router.post(prefix + "/upload")
        async def upload(
            request: Request,
            file: UploadFile = File(...),
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(_perm_upload),
        ):
            media_root = Path(
                system_config.get_cached(
                    SettingsKey.MEDIA_ROOT, str(current_settings().media_root)
                )
            )
            safe_app = SafePathSegment(app_label)
            safe_model = SafePathSegment(model_slug)
            rel_dir = Path(safe_app) / safe_model
            target = media_root / rel_dir
            target.mkdir(parents=True, exist_ok=True)
            filename = Path(file.filename or "upload").name
            dest = target / filename
            stem = dest.stem
            suffix = dest.suffix
            if file.content_type:
                expected = mimetypes.guess_extension(file.content_type)
                if expected and suffix.lower() != expected:
                    raise HTTPException(status_code=400, detail="Invalid file type")
            idx = 1
            while dest.exists():
                dest = target / f"{stem}-{idx}{suffix}"
                idx += 1
            saver = AsyncFileSaver(file, dest, MAX_UPLOAD_SIZE)
            await saver.save()
            rel_path = rel_dir / dest.name
            return {"url": str(rel_path).replace("\\", "/")}

        @router.post(prefix)
        async def create(
            request: Request,
            payload: dict = Body(...),
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_add),
        ):
            try:
                return await service.create(request, user, payload)
            except HTTPError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        @router.put(prefix + "/{pk}")
        async def update(
            request: Request,
            pk: str,
            payload: dict = Body(...),
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_change),
        ):
            try:
                return await service.update(request, user, pk, payload)
            except HTTPError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        @router.delete(prefix + "/{pk}")
        async def delete(
            request: Request,
            pk: str,
            user: AdminUserDTO = Depends(
                admin_auth_service.get_current_admin_user
            ),
            _ = Depends(perm_delete),
        ):
            try:
                return await service.delete(request, user, pk)
            except HTTPError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        return router


class _LegacyOperationsModule(types.ModuleType):
    """Shim module emitting a deprecation warning on attribute access."""

    _warned = False

    def __getattribute__(self, name: str):
        if name not in {"_warned", "__dict__"} and not object.__getattribute__(self, "_warned"):
            warnings.warn(
                "freeadmin.contrib.crud.operations is deprecated; import from freeadmin.contrib.crud instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            object.__setattr__(self, "_warned", True)
        return super().__getattribute__(name)


_legacy_operations = _LegacyOperationsModule(__name__ + ".operations")
_legacy_operations.CrudRouterBuilder = CrudRouterBuilder
sys.modules[__name__ + ".operations"] = _legacy_operations

# The End

