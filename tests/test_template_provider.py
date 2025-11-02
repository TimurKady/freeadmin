# -*- coding: utf-8 -*-
"""
tests.test_template_provider

Unit tests for the TemplateProvider static asset handling.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from freeadmin.core.configuration.conf import FreeAdminSettings
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.runtime.provider import TemplateProvider


def test_mount_favicon_skips_missing_asset(monkeypatch, tmp_path) -> None:
    """Missing favicon files should not crash mounting and emit a warning."""

    warnings: list[str] = []

    def capture_warning(message: str, *args: object, **kwargs: object) -> None:
        warnings.append(message % args if args else message)

    monkeypatch.setattr(
        "freeadmin.core.runtime.provider.logger.warning",
        capture_warning,
    )

    missing_icon = tmp_path / "missing.ico"

    def fake_get_cached(key, default):
        if key == SettingsKey.FAVICON_PATH:
            return str(missing_icon)
        return default

    monkeypatch.setattr(system_config, "get_cached", fake_get_cached)

    provider = TemplateProvider(
        templates_dir=[tmp_path],
        static_dir=tmp_path,
        settings=FreeAdminSettings(),
    )
    app = FastAPI()

    provider.mount_favicon(app)

    assert all(route.path != "/favicon.ico" for route in app.router.routes)
    assert any("missing.ico" in message for message in warnings)


def test_mount_favicon_supports_absolute_path(monkeypatch, tmp_path) -> None:
    """Administrators should be able to provide absolute favicon paths."""

    favicon_dir = tmp_path / "media"
    favicon_dir.mkdir()
    favicon_file = favicon_dir / "custom.ico"
    favicon_file.write_bytes(b"custom icon bytes")

    def fake_get_cached(key, default):
        if key == SettingsKey.FAVICON_PATH:
            return str(favicon_file)
        return default

    monkeypatch.setattr(system_config, "get_cached", fake_get_cached)

    provider = TemplateProvider(
        templates_dir=[tmp_path],
        static_dir=tmp_path,
        settings=FreeAdminSettings(),
    )
    app = FastAPI()

    provider.mount_favicon(app)

    client = TestClient(app)
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.content == b"custom icon bytes"


def test_mount_favicon_resolves_packaged_static(monkeypatch, tmp_path) -> None:
    """Default packaged favicon should be resolved even with prefixed paths."""

    static_dir = Path(__file__).resolve().parents[1] / "freeadmin" / "static"

    def fake_get_cached(key, default):
        if key == SettingsKey.FAVICON_PATH:
            return "freeadmin/static/images/favicon.ico"
        return default

    monkeypatch.setattr(system_config, "get_cached", fake_get_cached)

    provider = TemplateProvider(
        templates_dir=[tmp_path],
        static_dir=static_dir,
        settings=FreeAdminSettings(),
    )
    app = FastAPI()

    provider.mount_favicon(app)

    client = TestClient(app)
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert len(response.content) > 0


# The End
