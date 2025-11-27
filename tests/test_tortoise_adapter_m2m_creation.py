# -*- coding: utf-8 -*-
"""
Tortoise adapter many-to-many creation tests

Validate that passing many-to-many payloads to the Tortoise adapter does not
clobber relation managers and attaches related objects after creation.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest
from tortoise import Tortoise, fields, models

from freeadmin.contrib.adapters.tortoise.adapter import Adapter
from tests.system_models import system_models


class Listener(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)


class Event(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    listeners: fields.ManyToManyRelation[Listener] = fields.ManyToManyField(
        "models.Listener", related_name="events"
    )


class TestTortoiseAdapterM2MCreation:
    """Ensure the adapter handles many-to-many payloads safely."""

    adapter: ClassVar[Adapter]

    @classmethod
    def setup_class(cls) -> None:
        asyncio.run(
            Tortoise.init(
                db_url="sqlite://:memory:",
                modules={
                    "models": [__name__],
                    "admin": list(system_models.module_names()),
                },
            )
        )
        asyncio.run(Tortoise.generate_schemas())
        cls.adapter = Adapter()

    @classmethod
    def teardown_class(cls) -> None:
        asyncio.run(Tortoise.close_connections())

    @pytest.mark.asyncio
    async def test_many_to_many_payload_does_not_replace_manager(self) -> None:
        """Verify that the adapter keeps the relation manager intact."""

        listener = await Listener.create(name="first")
        payload = {"name": "event", "listeners": [{"id": listener.id}]}

        event = await self.adapter.create(Event, include_m2m=["listeners"], **payload)

        await self.adapter.fetch_related(event, "listeners")

        relation = fields.relational.ManyToManyRelation(
            event, Event._meta.fields_map["listeners"]
        )
        related = await relation.all()
        assert len(related) == 1
        assert related[0].id == listener.id


# The End
