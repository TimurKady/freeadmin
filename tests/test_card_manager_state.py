# -*- coding: utf-8 -*-
"""Tests covering persisted card state retrieval across manager instances."""

import pytest

from freeadmin.config import FreeAdminSettings
from freeadmin.core.interface.cards import CardManager
from freeadmin.core.interface.registry import PageRegistry


@pytest.mark.asyncio
async def test_card_manager_recovers_persisted_state(tmp_path) -> None:
    """Ensure a new manager reads the last state from the shared cache."""

    db_path = tmp_path / "cards.db"
    settings = FreeAdminSettings(event_cache_path=str(db_path))

    first_registry = PageRegistry()
    first_registry.register_card(
        key="alpha",
        app="demo",
        title="Demo",
        template="cards/demo.html",
        channel="channel-alpha",
    )
    first_manager = CardManager(first_registry, settings=settings)

    await first_manager.publish_event("alpha", {"value": 1})

    second_registry = PageRegistry()
    second_registry.register_card(
        key="alpha",
        app="demo",
        title="Demo",
        template="cards/demo.html",
        channel="channel-alpha",
    )
    second_manager = CardManager(second_registry, settings=settings)

    assert second_manager.get_last_state("alpha") == {"value": 1}


# The End
