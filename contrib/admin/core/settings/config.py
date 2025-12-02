# -*- coding: utf-8 -*-
"""
config

Database-backed system configuration utilities.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Any
import logging

from tortoise.transactions import in_transaction

from .defaults import DEFAULT_SETTINGS
from .keys import SettingsKey
from ...models.setting import SystemSetting

logger = logging.getLogger(__name__)


class SystemConfig:
    """Helper for accessing and mutating system settings.

    Values are cached in-memory. ``reload`` repopulates the cache from the
    database and ``ensure_seed`` inserts any missing defaults based on
    :data:`DEFAULT_SETTINGS`.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    async def ensure_seed(self) -> None:
        """Ensure all default settings exist in the database.

        Inserts any missing keys from :data:`DEFAULT_SETTINGS` and reloads the
        cache afterwards.
        """

        async with in_transaction():
            # migrate legacy page-type keys if present
            mapping = {
                "orm": SettingsKey.PAGE_TYPE_ORM,
                "view": SettingsKey.PAGE_TYPE_VIEW,
                "settings": SettingsKey.PAGE_TYPE_SETTINGS,
            }
            for bad_key, enum_key in mapping.items():
                record = await SystemSetting.get_or_none(key=bad_key)
                if record is None:
                    continue
                target_key = enum_key.value
                if await SystemSetting.filter(key=target_key).exists():
                    logger.warning(
                        "SystemSetting key '%s' exists; deleting stray '%s'", target_key, bad_key
                    )
                    await record.delete()
                    continue
                record.key = target_key
                record.name = enum_key.label or target_key
                await record.save()

            for key_enum, (value, value_type) in DEFAULT_SETTINGS.items():
                key = key_enum.value
                existing = await SystemSetting.get_or_none(key=key)
                if existing is None:
                    await SystemSetting.create(
                        key=key,
                        name=getattr(key_enum, "label", key),
                        value=value,
                        value_type=value_type,
                    )
        await self.reload()

    async def reload(self) -> None:
        """Reload settings from the database into the in-memory cache."""

        self._cache.clear()
        type_map = {k.value: t for k, (_, t) in DEFAULT_SETTINGS.items()}
        for record in await SystemSetting.all().values("key", "value"):
            key = record["key"]
            value_type = type_map.get(key, "string")
            self._cache[key] = self._cast(record["value"], value_type)

        # Ensure defaults for any keys still missing (in case DB lacked them)
        for key_enum, (value, value_type) in DEFAULT_SETTINGS.items():
            key = key_enum.value
            self._cache.setdefault(key, self._cast(value, value_type))

    def get_cached(self, key: SettingsKey | str, default: Any | None = None) -> Any:
        """Return ``key`` value directly from the in-memory cache.

        This helper avoids any disk IO and is safe to use after
        :meth:`reload` has populated the cache. If ``key`` is missing,
        ``default`` is returned instead of raising ``KeyError``.
        """

        key_str = key.value if isinstance(key, SettingsKey) else key
        return self._cache.get(key_str, default)

    async def get(self, key: SettingsKey | str, default: Any | None = None) -> Any:
        """Return a setting value by ``key``.

        ``key`` may be either a :class:`SettingsKey` instance or a raw string.
        If the key is missing and ``default`` is provided, ``default`` is
        returned. Otherwise a :class:`KeyError`` is raised.
        """

        key_str = key.value if isinstance(key, SettingsKey) else key
        if key_str in self._cache:
            return self._cache[key_str]
        if default is not None:
            return default
        raise KeyError(key_str)

    async def set(self, key: SettingsKey | str, value: Any) -> None:
        """Persist ``value`` for ``key`` and update the cache.

        Type casting is performed based on :data:`DEFAULT_SETTINGS` if the key
        is known; otherwise a simple string/integer/bool inference is applied.
        """

        key_str = key.value if isinstance(key, SettingsKey) else key
        value_type = self._resolve_type(key_str, value)
        casted = self._cast(value, value_type)

        existing = await SystemSetting.get_or_none(key=key_str)
        if existing is None:
            await SystemSetting.create(
                key=key_str,
                name=getattr(key, "label", key_str) if isinstance(key, SettingsKey) else key_str,
                value=casted,
                value_type=value_type,
            )
        else:
            existing.value = casted
            existing.value_type = value_type
            await existing.save()

        self._cache[key_str] = casted

    def exists(self, key: SettingsKey | str) -> bool:
        """Return ``True`` if ``key`` is present in the cache."""

        key_str = key.value if isinstance(key, SettingsKey) else key
        return key_str in self._cache

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _cast(value: Any, value_type: str) -> Any:
        if value_type == "int":
            return int(value)
        if value_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in {"1", "true", "yes", "on"}
            return bool(value)
        # default string
        if isinstance(value, str):
            return value
        return str(value)

    def _resolve_type(self, key: str, value: Any) -> str:
        for k, (_, t) in DEFAULT_SETTINGS.items():
            if k.value == key:
                return t
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        return "string"


# Module-level singleton ------------------------------------------------------

system_config = SystemConfig()

__all__ = ["SystemConfig", "system_config"]

# The End
