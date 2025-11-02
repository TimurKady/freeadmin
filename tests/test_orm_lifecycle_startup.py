# -*- coding: utf-8 -*-
"""Tests ensuring ORM lifecycle tolerates missing migrations on startup."""

from __future__ import annotations

import logging
import warnings

import pytest
from tortoise.exceptions import OperationalError

from freeadmin.core.orm import ORMConfig, ORMLifecycle
from freeadmin.core.orm import config as orm_config_module


@pytest.mark.asyncio
async def test_startup_logs_hint_when_migrations_missing(monkeypatch, caplog) -> None:
    """The lifecycle should log a helpful error message instead of failing."""

    config = ORMConfig(dsn="sqlite://:memory:", modules={"models": []})
    lifecycle = ORMLifecycle(config=config)

    error = OperationalError("missing table admin_content_type")

    async def failing_init(*args, **kwargs):
        raise error

    monkeypatch.setattr(orm_config_module.Tortoise, "init", failing_init)

    caplog.set_level(
        logging.ERROR,
        logger=orm_config_module.ORMLifecycle._logger.name,
    )

    await lifecycle.startup()

    assert "Failed to initialise ORM" in caplog.text
    assert "Run your migrations before starting FreeAdmin." in caplog.text
    assert str(error) in caplog.text


@pytest.mark.asyncio
async def test_startup_logs_warning_for_modules_without_models(monkeypatch, caplog) -> None:
    """The lifecycle should surface warnings when configured modules lack models."""

    config = ORMConfig(dsn="sqlite://:memory:", modules={"models": []})
    lifecycle = ORMLifecycle(config=config)

    async def init_with_warning(*args, **kwargs):
        warnings.warn('Module "demo.app.models" has no models', RuntimeWarning)

    monkeypatch.setattr(orm_config_module.Tortoise, "init", init_with_warning)

    caplog.set_level(
        logging.WARNING,
        logger=orm_config_module.ORMLifecycle._logger.name,
    )

    await lifecycle.startup()

    assert "Module demo.app.models does not declare ORM models" in caplog.text


# The End

