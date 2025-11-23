# -*- coding: utf-8 -*-
"""Tests covering caching of registered dashboard cards."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, List
from uuid import uuid4

import pytest

from freeadmin.config import FreeAdminSettings
from freeadmin.core.interface.cache.cards import SQLiteCardCache
from freeadmin.core.interface.site import AdminSite


class DummyAdapter:
    """Minimal adapter stub satisfying the admin site interface."""

    content_type_model = object()
    IntegrityError = RuntimeError


class DummyPermissionsService:
    """Simplified permission service emitting invalidation notifications."""

    class PermAction:
        view = "view"

    def __init__(self) -> None:
        self._hooks: List[Callable[[str], None]] = []
        self._snapshot = datetime.now(timezone.utc)

    def register_user_invalidation_hook(self, callback: Callable[[str], None]) -> None:
        """Store ``callback`` for later invalidation notifications."""

        self._hooks.append(callback)

    def get_permission_snapshot(self) -> datetime:
        """Return the timestamp representing the last invalidation."""

        return self._snapshot

    async def invalidate_user_permissions(self, user_id: int | str) -> None:
        """Trigger user permission invalidation hooks."""

        self._snapshot = datetime.now(timezone.utc)
        for hook in list(self._hooks):
            hook(str(user_id))


class DummyPermissionChecker:
    """Permission checker stub recording evaluated card keys."""

    PermAction = DummyPermissionsService.PermAction

    def __init__(self, service: DummyPermissionsService) -> None:
        self._service = service
        self.calls: list[str] = []

    async def check_card(
        self,
        user: Any,
        card_key: str,
        action: Any,
        *,
        admin_site: AdminSite | None = None,
    ) -> bool:
        """Record the evaluated ``card_key`` and return ``True``."""

        self.calls.append(card_key)
        return True

    def register_user_invalidation_hook(self, callback: Callable[[str], None]) -> None:
        """Delegate hook registration to the underlying service."""

        self._service.register_user_invalidation_hook(callback)

    def get_permission_snapshot(self) -> datetime:
        """Expose snapshot timestamp tracked by the service."""

        return self._service.get_permission_snapshot()

    def reset(self) -> None:
        """Clear recorded permission checks."""

        self.calls.clear()


@dataclass
class SiteFactory:
    """Helper responsible for constructing admin sites for tests."""

    base_path: Path
    monkeypatch: pytest.MonkeyPatch

    def create(
        self,
        *,
        ttl: timedelta = timedelta(seconds=60),
    ) -> tuple[AdminSite, DummyPermissionsService, DummyPermissionChecker]:
        """Return a configured admin site with deterministic dependencies."""

        self.monkeypatch.setattr(
            "freeadmin.core.interface.site.PermAction",
            DummyPermissionsService.PermAction,
            raising=False,
        )
        service = DummyPermissionsService()
        checker = DummyPermissionChecker(service)
        adapter = DummyAdapter()
        card_cache_path = self.base_path / f"card-cache-{uuid4().hex}.sqlite3"
        event_path = self.base_path / f"event-cache-{uuid4().hex}.sqlite3"
        cache = SQLiteCardCache(path=str(card_cache_path), ttl=ttl)
        settings = FreeAdminSettings(event_cache_path=str(event_path))
        site = AdminSite(
            adapter,
            settings=settings,
            permission_service=service,
            permission_checker_obj=checker,
            card_cache=cache,
        )
        return site, service, checker


@pytest.fixture
def site_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SiteFactory:
    """Provide a factory producing isolated admin site instances."""

    return SiteFactory(base_path=tmp_path, monkeypatch=monkeypatch)


def _register_card(site: AdminSite, key: str) -> None:
    """Register a sample card for ``site``."""

    site.register_card(
        key=key,
        title=f"Card {key}",
        template=f"cards/{key}.html",
        app="analytics",
    )


@pytest.mark.asyncio
async def test_card_cache_returns_cached_entries(site_factory: SiteFactory) -> None:
    """Ensure subsequent calls reuse cached card payloads."""

    site, _service, checker = site_factory.create()
    _register_card(site, "alpha")
    user = SimpleNamespace(id=1)

    first = await site.get_registered_cards(user)
    assert len(first) == 1
    second = await site.get_registered_cards(user)
    assert second == first
    assert checker.calls == ["alpha"]


@pytest.mark.asyncio
async def test_card_cache_invalidation_on_new_card(site_factory: SiteFactory) -> None:
    """Registering a new card should clear the cached payload."""

    site, _service, checker = site_factory.create()
    _register_card(site, "alpha")
    await site.get_registered_cards(SimpleNamespace(id=1))
    checker.reset()

    _register_card(site, "beta")
    cards = await site.get_registered_cards(SimpleNamespace(id=1))
    assert {entry["key"] for entry in cards} == {"alpha", "beta"}
    assert checker.calls == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_card_cache_invalidation_on_permission_change(
    site_factory: SiteFactory,
) -> None:
    """Permission invalidation should drop cached entries for the user."""

    site, service, checker = site_factory.create()
    _register_card(site, "alpha")
    user = SimpleNamespace(id=7)
    await site.get_registered_cards(user)
    checker.reset()

    await service.invalidate_user_permissions(user.id)
    refreshed = await site.get_registered_cards(user)
    assert len(refreshed) == 1
    assert checker.calls == ["alpha"]


@pytest.mark.asyncio
async def test_card_cache_ttl_expiry_triggers_revalidation(
    site_factory: SiteFactory,
) -> None:
    """Expired cache entries should be recomputed on access."""

    site, _service, checker = site_factory.create(ttl=timedelta(milliseconds=50))
    _register_card(site, "alpha")
    user = SimpleNamespace(id=3)
    await site.get_registered_cards(user)
    checker.reset()

    await asyncio.sleep(0.1)
    await site.get_registered_cards(user)
    assert checker.calls == ["alpha"]


# The End

