# -*- coding: utf-8 -*-
"""
filepath

Widget for storing file path strings with upload support.


Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
import os
from pathlib import PurePath, PurePosixPath
from typing import Any, Dict
from urllib.parse import urlparse

from freeadmin.config import current_settings
from ...core.interface.settings import SettingsKey, system_config

from .base import BaseWidget
from .registry import registry


@registry.register("filepath")
class FilePathWidget(BaseWidget):
    """Widget that represents uploaded file paths."""

    assets_css = ("/static/widgets/filepath.css",)
    assets_js = ("/static/widgets/filepath.js",)
    upload_handler: str = "FilePathUploader"

    def get_schema(self) -> Dict[str, Any]:
        prefix = (self.ctx.prefix if self.ctx else "").rstrip("/")
        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm").strip("/")
        media_prefix = system_config.get_cached(
            SettingsKey.MEDIA_URL, current_settings().media_url
        ).strip("/")
        md = self.ctx.descriptor if self.ctx else None
        admin = self.ctx.admin if self.ctx else None

        app = (
            getattr(admin, "app_label", None)
            or getattr(md, "app", None)
            or getattr(md, "app_label", "")
        ).lower()
        name = (
            getattr(admin, "model_slug", None)
            or getattr(md, "name", None)
            or getattr(md, "model_name", "")
        ).lower()

        endpoint = str(PurePosixPath(prefix) / orm_prefix / app / name / "upload")

        schema: Dict[str, Any] = {
            "type": "string",
            "title": self.get_title(),
            "format": "url",
            "options": {
                "upload": {
                    "upload_handler": self.upload_handler,
                    "media_prefix": f"/{media_prefix}/",
                }
            },
            "upload_endpoint": endpoint,
        }
        start_val = self.get_startval()
        if isinstance(start_val, str) and start_val:
            schema["links"] = [
                {"href": f"/{media_prefix}/{{{{self}}}}", "title": "{{self}}"}
            ]
        return self.merge_readonly(schema)

    def to_python(self, value: Any, options: Dict[str, Any] | None = None) -> str:
        if value in (None, ""):
            return ""
        return str(value)

    def to_storage(self, value: Any, options: Dict[str, Any] | None = None) -> str | None:
        # 1) Cast to string when value is a supported type
        path_str: str | None = None
        if isinstance(value, str) and value:
            path_str = value
        elif isinstance(value, PurePath):
            path_str = value.as_posix()
        elif isinstance(value, os.PathLike):
            path_str = os.fspath(value)

        if not path_str:
            return None

        # 2) When an absolute URL is provided, keep only the path portion
        parts = urlparse(path_str)
        if parts.scheme and parts.netloc:
            path_str = parts.path

        # 3) Normalize into POSIX style
        path_str = str(PurePosixPath(path_str))

        media_prefix = system_config.get_cached(
            SettingsKey.MEDIA_URL, current_settings().media_url
        ).strip("/")
        if path_str.startswith(f"/{media_prefix}"):
            path_str = path_str[len(f"/{media_prefix}") :]

        # 4) Make the path relative (remove any leading slash)
        path_str = path_str.lstrip("/")

        return path_str or None

# The End

