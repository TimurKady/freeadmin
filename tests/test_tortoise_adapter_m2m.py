# -*- coding: utf-8 -*-
"""Unit tests for Tortoise adapter many-to-many helpers."""

from __future__ import annotations

import pytest

from freeadmin.contrib.adapters.tortoise.adapter import Adapter


@pytest.fixture
def anyio_backend():
    """Force AnyIO to run tests with the asyncio backend."""

    return "asyncio"


class SyncRelationManager:
    """Relation manager with a synchronous ``clear`` implementation."""

    def __init__(self) -> None:
        """Initialize the cleared flag for assertions."""

        self.cleared = False

    def clear(self):
        """Mark the relation as cleared using a synchronous method."""

        self.cleared = True
        return None


class AsyncRelationManager:
    """Relation manager exposing an asynchronous ``clear`` coroutine."""

    def __init__(self) -> None:
        """Initialize the cleared flag for assertions."""

        self.cleared = False

    async def clear(self):
        """Mark the relation as cleared using an awaited coroutine."""

        self.cleared = True


@pytest.mark.anyio
async def test_m2m_clear_supports_sync_managers():
    """Ensure ``m2m_clear`` handles managers with synchronous ``clear``."""

    adapter = Adapter.__new__(Adapter)
    manager = SyncRelationManager()

    await adapter.m2m_clear(manager)

    assert manager.cleared is True


@pytest.mark.anyio
async def test_m2m_clear_supports_async_managers():
    """Ensure ``m2m_clear`` awaits managers exposing async ``clear``."""

    adapter = Adapter.__new__(Adapter)
    manager = AsyncRelationManager()

    await adapter.m2m_clear(manager)

    assert manager.cleared is True


# The End

