# -*- coding: utf-8 -*-
"""
conf

Runtime configuration utilities for the FreeAdmin package.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Callable, Mapping


@dataclass
class FreeAdminSettings:
    """Container for admin configuration derived from environment variables."""

    secret_key: str = field(default_factory=lambda: "change-me")
    session_secret: str | None = None
    csrf_secret: str | None = None
    admin_path: str = "/admin"
    media_url: str = "/media/"
    media_root: Path = field(default_factory=lambda: Path.cwd() / "media")
    event_cache_path: str = ":memory:"
    event_cache_in_memory: bool = True
    jwt_secret_key: str | None = None
    action_batch_size: int = 50
    card_events_token_ttl: int = 3600
    admin_site_title: str = "FreeAdmin"
    brand_icon: str = "freeadmin/static/images/icon-36x36.png"
    favicon_path: str = "freeadmin/static/images/favicon.ico"
    database_url: str | None = None
    static_url_segment: str = "/staticfiles"
    static_route_name: str = "admin-static"
    export_cache_path: str | None = None
    export_cache_ttl: int = 300

    def __post_init__(self) -> None:
        """Finalize defaults by falling back to the secret key where required."""
        if not self.session_secret:
            self.session_secret = self.secret_key
        if not self.csrf_secret:
            self.csrf_secret = self.secret_key
        self.admin_path = self._normalize_prefix(self.admin_path)
        self.media_url = self._normalize_prefix(self.media_url)
        self.static_url_segment = self._normalize_static_segment(
            self.static_url_segment
        )
        if not isinstance(self.media_root, Path):
            self.media_root = Path(str(self.media_root))
        if isinstance(self.event_cache_path, Path):
            self.event_cache_path = str(self.event_cache_path)
        if isinstance(self.export_cache_path, Path):
            self.export_cache_path = str(self.export_cache_path)
        explicit_path = (
            self.event_cache_path not in (None, "", ":memory:")
            and self.event_cache_path.strip() != ""
        )
        if explicit_path and self.event_cache_in_memory:
            self.event_cache_in_memory = False
        if self.event_cache_in_memory:
            self.event_cache_path = ":memory:"
        elif (
            not self.event_cache_path
            or not self.event_cache_path.strip()
            or self.event_cache_path == ":memory:"
        ):
            default_file = Path.cwd() / "freeadmin-event-cache.sqlite3"
            self.event_cache_path = str(default_file)
        if not self.export_cache_path or not str(self.export_cache_path).strip():
            default_export_cache = Path.cwd() / "freeadmin-export-cache.sqlite3"
            self.export_cache_path = str(default_export_cache)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        prefix: str = "FA_",
    ) -> "FreeAdminSettings":
        """Build a settings instance from environment variables."""
        source = env or os.environ
        data = {key[len(prefix) :]: value for key, value in source.items() if key.startswith(prefix)}
        secret_key = data.get("SECRET_KEY") or source.get("SECRET_KEY") or "change-me"
        session_secret = data.get("SESSION_SECRET")
        csrf_secret = data.get("CSRF_SECRET")
        admin_path = data.get("ADMIN_PATH") or "/admin"
        media_url = data.get("MEDIA_URL") or "/media/"
        media_root = data.get("MEDIA_ROOT") or (Path.cwd() / "media")
        cache_path_raw = data.get("EVENT_CACHE_PATH")
        cache_memory_raw = data.get("EVENT_CACHE_IN_MEMORY")
        cache_in_memory = (
            cls._to_bool(cache_memory_raw)
            if cache_memory_raw is not None
            else cache_path_raw in (None, "", ":memory:")
        )
        cache_path = ":memory:" if cache_in_memory else (cache_path_raw or ":memory:")
        jwt_secret = data.get("JWT_SECRET_KEY")
        action_batch_size = cls._to_int(data.get("ACTION_BATCH_SIZE"), default=50)
        card_ttl = cls._to_int(data.get("CARD_EVENTS_TOKEN_TTL"), default=3600)
        admin_site_title = data.get("ADMIN_SITE_TITLE") or "FreeAdmin"
        brand_icon = data.get("BRAND_ICON") or "freeadmin/static/images/icon-36x36.png"
        favicon_path = data.get("FAVICON_PATH") or "freeadmin/static/images/favicon.ico"
        database_url = data.get("DATABASE_URL") or source.get("DATABASE_URL")
        static_segment = cls._normalize_static_segment(
            data.get("STATIC_URL_SEGMENT")
        )
        static_route = data.get("STATIC_ROUTE_NAME") or "admin-static"
        export_cache_path = data.get("EXPORT_CACHE_PATH")
        export_cache_ttl = cls._to_int(
            data.get("EXPORT_CACHE_TTL"), default=300
        )
        return cls(
            secret_key=secret_key,
            session_secret=session_secret,
            csrf_secret=csrf_secret,
            admin_path=admin_path,
            media_url=media_url,
            media_root=Path(media_root),
            event_cache_path=cache_path,
            event_cache_in_memory=cache_in_memory,
            jwt_secret_key=jwt_secret,
            action_batch_size=action_batch_size,
            card_events_token_ttl=card_ttl,
            admin_site_title=admin_site_title,
            brand_icon=brand_icon,
            favicon_path=favicon_path,
            database_url=database_url,
            static_url_segment=static_segment,
            static_route_name=static_route,
            export_cache_path=export_cache_path,
            export_cache_ttl=export_cache_ttl,
        )

    @staticmethod
    def _to_int(value: str | None, *, default: int) -> int:
        """Return an integer from ``value`` or ``default`` when conversion fails."""
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_bool(value: str | None, *, default: bool = False) -> bool:
        """Return a boolean parsed from ``value`` with a ``default`` fallback."""

        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    @staticmethod
    def _normalize_prefix(value: str) -> str:
        """Ensure paths always contain a single leading slash."""
        normalized = value.strip()
        stripped = normalized.strip("/")
        if not stripped:
            return "/"
        cleaned = "/" + stripped
        if normalized.endswith("/") and stripped:
            cleaned += "/"
        return cleaned

    @staticmethod
    def _normalize_static_segment(value: str | None) -> str:
        """Return an absolute URL segment used for serving static assets."""

        normalized = str(value or "").strip()
        if not normalized:
            normalized = "/staticfiles"
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if len(normalized) > 1 and normalized.endswith("/"):
            normalized = normalized.rstrip("/")
        if not normalized:
            return "/staticfiles"
        return normalized


class SettingsManager:
    """Central storage for the active ``FreeAdminSettings`` instance."""

    def __init__(self, initial: FreeAdminSettings | None = None) -> None:
        """Prepare storage with an optional preconfigured ``initial`` settings."""

        self._lock = RLock()
        self._settings = initial
        self._callbacks: list[Callable[[FreeAdminSettings], None]] = []

    def configure(self, settings: FreeAdminSettings) -> None:
        """Install a new settings instance and notify observers."""
        with self._lock:
            self._settings = settings
            for callback in list(self._callbacks):
                callback(settings)

    def current(self) -> FreeAdminSettings:
        """Return the active settings, lazily initializing from the environment."""
        with self._lock:
            if self._settings is None:
                self._settings = FreeAdminSettings.from_env()
            return self._settings

    def register(self, callback: Callable[[FreeAdminSettings], None]) -> None:
        """Register a callback invoked whenever settings change."""
        with self._lock:
            self._callbacks.append(callback)

    def unregister(self, callback: Callable[[FreeAdminSettings], None]) -> None:
        """Remove a previously registered settings change callback if present."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)


_settings_manager = SettingsManager()


def configure(settings: FreeAdminSettings) -> None:
    """Public entry point to install application specific settings."""
    _settings_manager.configure(settings)


def current_settings() -> FreeAdminSettings:
    """Return the active settings instance used by FreeAdmin components."""
    return _settings_manager.current()


def register_settings_observer(callback: Callable[[FreeAdminSettings], None]) -> None:
    """Subscribe to configuration changes for global singletons."""
    _settings_manager.register(callback)


def unregister_settings_observer(callback: Callable[[FreeAdminSettings], None]) -> None:
    """Unsubscribe from configuration changes previously registered."""
    _settings_manager.unregister(callback)


__all__ = [
    "FreeAdminSettings",
    "SettingsManager",
    "configure",
    "current_settings",
    "register_settings_observer",
    "unregister_settings_observer",
]


# The End

