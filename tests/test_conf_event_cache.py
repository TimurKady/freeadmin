# -*- coding: utf-8 -*-
"""Tests ensuring event cache configuration honours memory preferences."""

from pathlib import Path

from freeadmin.config import FreeAdminSettings


def test_settings_default_to_in_memory_cache(tmp_path) -> None:
    """Verify default settings keep the event cache fully in memory."""

    settings = FreeAdminSettings()

    assert settings.event_cache_in_memory is True
    assert settings.event_cache_path == ":memory:"


def test_settings_respect_explicit_disk_path(tmp_path) -> None:
    """Ensure providing a path forces persistent cache storage."""

    db_path = tmp_path / "custom-cache.sqlite3"
    settings = FreeAdminSettings(event_cache_path=str(db_path), event_cache_in_memory=False)

    assert settings.event_cache_in_memory is False
    assert settings.event_cache_path == str(db_path)


def test_settings_infer_persistent_mode_from_path(tmp_path) -> None:
    """Check passing a path without flags disables the memory cache."""

    db_path = tmp_path / "implicit-persistent.sqlite3"
    settings = FreeAdminSettings(event_cache_path=str(db_path))

    assert settings.event_cache_in_memory is False
    assert settings.event_cache_path == str(db_path)


def test_settings_from_env_forces_memory_mode() -> None:
    """Check environment overrides can force in-memory behaviour."""

    env = {
        "FA_EVENT_CACHE_PATH": "/tmp/ignored.sqlite3",
        "FA_EVENT_CACHE_IN_MEMORY": "true",
    }

    settings = FreeAdminSettings.from_env(env)

    assert settings.event_cache_in_memory is True
    assert settings.event_cache_path == ":memory:"


def test_settings_from_env_persistent_with_default_file(tmp_path, monkeypatch) -> None:
    """Confirm disabling memory cache selects a default persistent path."""

    env = {
        "FA_EVENT_CACHE_IN_MEMORY": "false",
    }

    monkeypatch.chdir(tmp_path)

    settings = FreeAdminSettings.from_env(env)

    expected = Path.cwd() / "freeadmin-event-cache.sqlite3"
    assert settings.event_cache_in_memory is False
    assert settings.event_cache_path == str(expected)


# The End
