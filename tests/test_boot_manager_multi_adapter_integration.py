# -*- coding: utf-8 -*-
"""Integration tests verifying boot sequence preserves adapter selections."""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib import import_module
from typing import Any, Dict, Iterable, List, Tuple
import sys
import types

import pytest
from fastapi import FastAPI

from freeadmin.contrib.adapters import registry as adapter_registry
from freeadmin.core.boot import BootManager
from freeadmin.core.interface.settings.config import system_config
from tests.multiadapterapp.models import (
    MemoryContentType,
    MemoryEnum,
    MemoryGroup,
    MemoryPermission,
    MemorySystemSetting,
    MemoryUser,
    MultiAdapterModel,
)

runtime_hub_module = import_module("freeadmin.core.runtime.hub")


class MemoryAdapter:
    """In-memory adapter satisfying the admin protocol for testing."""

    QuerySet = list
    DoesNotExist = LookupError
    MultipleObjectsReturned = RuntimeError
    IntegrityError = RuntimeError

    def __init__(self, name: str) -> None:
        """Initialize storage and bind adapter metadata."""

        self.name = name
        self.model_modules: list[str] = []
        self.user_model = MemoryUser
        self.group_model = MemoryGroup
        self.group_permission_model = MemoryPermission
        self.user_permission_model = MemoryPermission
        self.content_type_model = MemoryContentType
        self.system_setting_model = MemorySystemSetting
        self.perm_action = MemoryEnum
        self.setting_value_type = MemoryEnum
        self._storage: Dict[type, List[Any]] = {}
        self._next_ids: Dict[type, int] = {}

    def get_model_descriptor(self, model: type[Any]) -> dict[str, Any]:
        """Return a descriptor describing the provided model class."""

        return {"model": model}

    def get_model(self, dotted: str) -> type[Any]:
        """Resolve a dotted path into a model class from storage."""

        for model_cls in self._storage:
            if model_cls.__name__ == dotted.split(".")[-1]:
                return model_cls
        raise LookupError(f"Unknown model {dotted}")

    def get_pk_attr(self, model: type[Any]) -> str:
        """Return the attribute name used as a primary key."""

        _ = model
        return "id"

    def all(self, qs_or_model: Any) -> list[Any]:
        """Return all records associated with ``qs_or_model``."""

        model = qs_or_model if isinstance(qs_or_model, type) else type(qs_or_model)
        return list(self._storage.get(model, []))

    def filter(self, qs_or_model: Any, **filters: Any) -> list[Any]:
        """Return a filtered list of records matching ``filters``."""

        queryset = qs_or_model if isinstance(qs_or_model, list) else self.all(qs_or_model)
        results: list[Any] = []
        for obj in queryset:
            if all(getattr(obj, key, None) == value for key, value in filters.items()):
                results.append(obj)
        return results

    def apply_filter_spec(self, qs_or_model: Any, specs: list[Any]) -> list[Any]:
        """Apply filter specs sequentially to the provided queryset or model."""

        queryset = qs_or_model if isinstance(qs_or_model, list) else self.all(qs_or_model)
        filtered = list(queryset)
        for spec in specs:
            filtered = [obj for obj in filtered if spec(obj)]
        return filtered

    def order_by(self, qs: list[Any], *fields: str) -> list[Any]:
        """Sort ``qs`` by the supplied ``fields`` in insertion order."""

        ordered = list(qs)
        for field in reversed(fields):
            ordered.sort(key=lambda obj: getattr(obj, field, None))
        return ordered

    def limit(self, qs: list[Any], limit: int) -> list[Any]:
        """Return the first ``limit`` records from ``qs``."""

        return list(qs)[:limit]

    def offset(self, qs: list[Any], offset: int) -> list[Any]:
        """Return ``qs`` starting at the provided ``offset``."""

        return list(qs)[offset:]

    def select_related(self, qs: list[Any], *related: str) -> list[Any]:
        """Return ``qs`` unchanged; relation loading is unnecessary."""

        _ = related
        return list(qs)

    def prefetch_related(self, qs: list[Any], *related: str) -> list[Any]:
        """Return ``qs`` unchanged; relation loading is unnecessary."""

        _ = related
        return list(qs)

    def annotate(self, qs: list[Any], annotations: dict) -> list[Any]:
        """Return ``qs`` unchanged because annotations are unused in tests."""

        _ = annotations
        return list(qs)

    def distinct(self, qs: list[Any], *fields: str) -> list[Any]:
        """Return distinct values by ``fields`` preserving order."""

        _ = fields
        seen: set[int] = set()
        unique: list[Any] = []
        for obj in qs:
            identity = id(obj)
            if identity in seen:
                continue
            seen.add(identity)
            unique.append(obj)
        return unique

    def only(self, qs: list[Any], *fields: str) -> list[Any]:
        """Return ``qs`` unchanged; field projection is unnecessary."""

        _ = fields
        return list(qs)

    def values(self, qs: list[Any], *fields: str) -> list[dict]:
        """Return dictionaries containing selected ``fields`` from ``qs``."""

        payload: list[dict] = []
        for obj in qs:
            record = {field: getattr(obj, field, None) for field in fields}
            payload.append(record)
        return payload

    async def fetch_all(self, qs: Iterable[Any]) -> list[Any]:
        """Return all items from ``qs`` as a list."""

        return list(qs)

    async def fetch_values(self, qs: Iterable[Any], *fields: str, flat: bool = False) -> list[Any]:
        """Return selected values from ``qs`` respecting ``flat``."""

        records = []
        for obj in qs:
            values = [getattr(obj, field, None) for field in fields]
            records.append(values[0] if flat and values else tuple(values))
        return records

    async def count(self, qs: Iterable[Any]) -> int:
        """Return the number of records in ``qs``."""

        return len(list(qs))

    async def get(self, qs_or_model: Any, **filters: Any) -> Any:
        """Return a single record matching ``filters`` or raise."""

        matches = self.filter(qs_or_model, **filters)
        if not matches:
            raise self.DoesNotExist
        if len(matches) > 1:
            raise self.MultipleObjectsReturned
        return matches[0]

    async def get_or_none(self, qs_or_model: Any, **filters: Any) -> Any | None:
        """Return a single record matching ``filters`` or ``None``."""

        try:
            return await self.get(qs_or_model, **filters)
        except self.DoesNotExist:
            return None

    async def exists(self, qs: Iterable[Any]) -> bool:
        """Return ``True`` when ``qs`` contains at least one record."""

        return any(True for _ in qs)

    async def save(self, obj: Any) -> None:
        """Persist ``obj`` assigning an identifier when missing."""

        model = type(obj)
        bucket = self._storage.setdefault(model, [])
        if getattr(obj, "id", None) is None:
            next_id = self._next_ids.get(model, 1)
            obj.id = next_id
            self._next_ids[model] = next_id + 1
            bucket.append(obj)
            return
        for index, record in enumerate(bucket):
            if getattr(record, "id", None) == getattr(obj, "id", None):
                bucket[index] = obj
                break
        else:
            bucket.append(obj)

    async def delete(self, obj: Any) -> None:
        """Remove ``obj`` from storage if present."""

        model = type(obj)
        bucket = self._storage.get(model, [])
        self._storage[model] = [record for record in bucket if record is not obj]

    async def create(self, model: type[Any], **data: Any) -> Any:
        """Create, persist, and return an instance of ``model``."""

        instance = model(**data)
        await self.save(instance)
        return instance

    async def values_list(self, qs: Iterable[Any], *fields: str, flat: bool = False) -> list[Any]:
        """Return positional values from ``qs`` respecting ``flat``."""

        return await self.fetch_values(qs, *fields, flat=flat)

    def Q(self, *args: Any, **kwargs: Any) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        """Return a tuple capturing provided query arguments."""

        _ = args
        return args, kwargs

    @asynccontextmanager
    async def in_transaction(self):
        """Provide a no-op transaction context manager."""

        yield None

    async def m2m_clear(self, manager: Any) -> None:
        """Clear relations managed by ``manager`` when applicable."""

        _ = manager
        return None

    async def m2m_add(self, manager: Any, objs: Iterable[Any]) -> None:
        """Attach ``objs`` to ``manager`` when applicable."""

        _ = manager, objs
        return None


class BootHarness:
    """Coordinate boot, discovery, and finalization for a specific adapter."""

    def __init__(self, adapter_name: str) -> None:
        """Store adapter selection for later bootstrapping."""

        self.adapter_name = adapter_name

    async def run(self, packages: list[str]) -> tuple[Any, list[Any]]:
        """Execute boot and startup hooks, returning the admin site and menu."""

        previous_runtime_module = sys.modules.pop("freeadmin.core.runtime.hub", None)
        runtime_module = import_module("freeadmin.core.runtime.hub")
        sys.modules["freeadmin.core.runtime.hub"] = runtime_module
        runtime_package = sys.modules.get("freeadmin.core.runtime")
        if runtime_package is None:
            runtime_package = import_module("freeadmin.core.runtime")
        original_hub = getattr(runtime_module, "hub", None)
        original_admin_site = getattr(runtime_module, "admin_site", None)
        original_runtime_hub = (
            getattr(runtime_package, "hub", None) if runtime_package is not None else None
        )
        original_runtime_admin_site = (
            getattr(runtime_package, "admin_site", None)
            if runtime_package is not None
            else None
        )
        boot = BootManager(adapter_name=self.adapter_name)
        app = FastAPI()
        from freeadmin.core.runtime.hub import AdminHub

        runtime_module.hub = AdminHub(adapter=boot.adapter, boot_manager=boot)
        runtime_module.admin_site = runtime_module.hub.admin_site
        sys.modules["freeadmin.core.runtime.hub"] = runtime_module
        if runtime_package is not None:
            runtime_package.hub = runtime_module.hub
            runtime_package.admin_site = runtime_module.admin_site

        def _ensure_hub(self: BootManager) -> "AdminHub":
            existing_hub = runtime_module.hub
            if existing_hub is not None:
                existing_adapter = existing_hub.admin_site.adapter
                if self._adapter is None:
                    self._adapter = existing_adapter
                elif existing_adapter is not self._adapter:
                    raise RuntimeError(
                        "Admin hub already initialized with a different adapter"
                    )
                self._hub = existing_hub
            else:
                self._hub = AdminHub(adapter=self.adapter)
                runtime_module.hub = self._hub
                runtime_module.admin_site = self._hub.admin_site
                if runtime_package is not None:
                    runtime_package.hub = runtime_module.hub
                    runtime_package.admin_site = runtime_module.admin_site
            return self._hub

        boot._ensure_hub = _ensure_hub.__get__(boot, BootManager)
        try:
            boot.init(app, packages=packages)
            await app.router.startup()
            site = runtime_module.admin_site
            if runtime_package is not None:
                runtime_package.hub = runtime_module.hub
                runtime_package.admin_site = runtime_module.admin_site
            menu = site.menu_builder.build_main_menu(locale="en")
            await app.router.shutdown()
            boot.reset()
            return site, menu
        finally:
            runtime_module.hub = original_hub
            runtime_module.admin_site = original_admin_site
            if previous_runtime_module is not None:
                sys.modules["freeadmin.core.runtime.hub"] = previous_runtime_module
            else:
                sys.modules.pop("freeadmin.core.runtime.hub", None)
            if runtime_package is not None:
                runtime_package.hub = original_runtime_hub
                runtime_package.admin_site = original_runtime_admin_site


@pytest.fixture(autouse=True)
def _patch_system_config(monkeypatch):
    """Stub configuration hooks to avoid touching external databases."""

    async def _noop() -> None:
        return None

    monkeypatch.setattr(system_config, "ensure_seed", _noop)
    monkeypatch.setattr(system_config, "reload", _noop)
    system_config._cache.clear()
    yield


@pytest.mark.asyncio
async def test_boot_sequence_uses_selected_adapter(monkeypatch) -> None:
    """Ensure discovery and finalization rely on the BootManager's adapter."""

    adapter_alpha = MemoryAdapter("alpha")
    adapter_beta = MemoryAdapter("beta")
    adapter_registry.register(adapter_alpha)
    adapter_registry.register(adapter_beta)

    harness_alpha = BootHarness(adapter_alpha.name)
    site_alpha, menu_alpha = await harness_alpha.run(["tests.multiadapterapp"])

    admin_entry_alpha = site_alpha.model_reg[("multiadapter", "multiadaptermodel")]
    assert admin_entry_alpha.adapter is adapter_alpha
    assert any(item.path.endswith("/multiadapter/multiadaptermodel") for item in menu_alpha)

    harness_beta = BootHarness(adapter_beta.name)
    site_beta, menu_beta = await harness_beta.run(["tests.multiadapterapp"])

    admin_entry_beta = site_beta.model_reg[("multiadapter", "multiadaptermodel")]
    assert admin_entry_beta.adapter is adapter_beta
    assert any(item.path.endswith("/multiadapter/multiadaptermodel") for item in menu_beta)
    assert site_alpha.adapter is adapter_alpha
    assert site_beta.adapter is adapter_beta


# The End
