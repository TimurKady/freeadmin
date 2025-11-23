# -*- coding: utf-8 -*-
"""
upload

File upload endpoint for the admin interface.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request

from ...core.interface.services.auth import AdminUserDTO
from ...core.interface.auth import admin_auth_service
from ...core.interface.permissions import permission_checker
from ...core.interface.services.permissions import PermAction
from ...core.interface.settings import SettingsKey, system_config
from ..crud import SafePathSegment
from freeadmin.config import FreeAdminSettings, current_settings


class UploadAPI:
    """API endpoints for uploading files."""

    def __init__(self, *, settings: FreeAdminSettings | None = None) -> None:
        self.router = APIRouter()
        self.router.post("/{app}/{model}/upload")(self.upload)
        self.permission_checker = permission_checker
        self._settings = settings or current_settings()

    async def _ensure_permission(self, request: Request, app: str, model: str) -> None:
        perm_add = self.permission_checker.require_model(
            PermAction.add, app_value=app, model_value=model
        )
        perm_change = self.permission_checker.require_model(
            PermAction.change, app_value=app, model_value=model
        )
        try:
            await perm_add(request)
        except HTTPException:
            await perm_change(request)

    async def upload(
        self,
        request: Request,
        app: str,
        model: str,
        file: UploadFile = File(...),
        user: AdminUserDTO = Depends(admin_auth_service.get_current_admin_user),
    ):
        if not file or not getattr(file, "filename", None):
            raise HTTPException(status_code=400, detail="No file provided")
        await self._ensure_permission(request, app, model)
        media_root = Path(
            system_config.get_cached(
                SettingsKey.MEDIA_ROOT, str(self._settings.media_root)
            )
        )
        safe_app = SafePathSegment(app)
        safe_model = SafePathSegment(model)
        rel_dir = Path(safe_app) / safe_model
        target = media_root / rel_dir
        target.mkdir(parents=True, exist_ok=True)
        filename = Path(file.filename or "upload").name
        dest = target / filename
        stem = dest.stem
        suffix = dest.suffix
        idx = 1
        while dest.exists():
            dest = target / f"{stem}-{idx}{suffix}"
            idx += 1
        data = await file.read()
        with open(dest, "wb") as fh:
            fh.write(data)
        await file.close()
        rel_path = rel_dir / dest.name
        return {"url": str(rel_path).replace("\\", "/")}


_api = UploadAPI()
router = _api.router

__all__ = ["router"]

# The End

