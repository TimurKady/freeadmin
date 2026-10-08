# -*- coding: utf-8 -*-
"""Regression tests for Tortoise ORM 1.x compatibility."""

from __future__ import annotations

from tortoise import Tortoise

from freeadmin.contrib.adapters.tortoise import setting
from freeadmin.contrib.adapters.tortoise.adapter import Adapter
from freeadmin.contrib.adapters.tortoise.users import AdminUser
from freeadmin.core.boot.registry import ModelRegistrar
from freeadmin.core.orm import ORMConfig
from freeadmin.core.orm import config as orm_config_module


def test_config_has_no_empty_aerich_app_without_aerich(monkeypatch) -> None:
    """Tortoise 1.x rejects apps without models."""

    monkeypatch.setattr(orm_config_module.ORMConfig, "_has_aerich_support", lambda self: False)
    built = ORMConfig.build(
        adapter_name="tortoise",
        config={"connections": {"default": "sqlite://:memory:"}, "apps": {}},
    )
    legacy = ORMConfig(dsn="sqlite://:memory:", modules={"models": ["app.models"]})

    assert "aerich" not in built.config["apps"]
    assert "aerich" not in legacy.config["apps"]
    assert all(app["models"] for app in legacy.config["apps"].values())


def test_registrar_tolerates_uninitialised_apps(monkeypatch) -> None:
    """``Tortoise.apps`` is ``None`` before a 1.x context is initialised."""

    monkeypatch.setattr(type(Tortoise), "apps", property(lambda cls: None), raising=False)
    ModelRegistrar().add_adapter(Adapter.__new__(Adapter))


def test_adapter_resolves_models_through_apps_registry() -> None:
    adapter = Adapter()

    assert adapter.get_model("admin.AdminUser") is AdminUser
    assert adapter.get_model("admin.Missing") is None


def test_setting_json_field_is_importable_for_migrations() -> None:
    """Migration writers import field classes by module path."""

    field = setting.SystemSetting._meta.fields_map["value"]
    assert type(field) is setting.SettingJSONField
