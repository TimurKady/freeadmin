# -*- coding: utf-8 -*-
"""
cards

Dashboard card management utilities and state storage.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Iterator, List, Set

from freeadmin.config import FreeAdminSettings, current_settings

from .cache import SQLiteCardCache, SQLiteEventCache

from .registry import CardEntry, PageRegistry
from .virtual import VirtualContentKey
from .sse.publisher import PublisherService


class CardManager:
    """Maintain card metadata, state and event publishing."""

    def __init__(
        self,
        registry: PageRegistry,
        *,
        event_cache_class: type[SQLiteEventCache] | None = None,
        event_cache: SQLiteEventCache | None = None,
        card_cache: SQLiteCardCache | None = None,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        """Initialize the manager with the registry and event cache backend."""

        self.registry = registry
        self._settings = settings or current_settings()
        self._event_cache_class = event_cache_class or SQLiteEventCache
        cache_path = getattr(self._settings, "event_cache_path", ":memory:")
        self._event_cache = event_cache or self._event_cache_class(path=cache_path)
        self._event_cache_path = (
            getattr(self._event_cache, "path", cache_path) if event_cache else cache_path
        )
        self._last_state: Dict[str, Any] = {}
        self._publishers: List[PublisherService] = []
        self._publisher_tasks: Dict[PublisherService, asyncio.Task[None]] = {}
        self._pending_events: Set[asyncio.Task[Any]] = set()
        self._publishers_started = False
        self.logger = logging.getLogger(__name__)
        self._card_cache = card_cache
        self._load_persisted_states()

    def register_card(
        self,
        key: str,
        app: str,
        title: str,
        template: str,
        *,
        icon: str | None = None,
        channel: str | None = None,
        col_class: str = "col-2",
        scripts: List[str] | None = None,
        styles: List[str] | None = None,
    ) -> None:
        """Register card metadata within the underlying registry.

        Args:
            key: Unique identifier of the card.
            app: Application label that groups the card in navigation.
            title: Display title rendered inside the card.
            template: Path to the template that implements the card.
            icon: Optional Bootstrap icon displayed near the title.
            channel: Optional SSE channel for live updates.
            col_class: Bootstrap column classes applied to the dashboard grid.
            scripts: Extra script asset paths required by the card.
            styles: Extra style asset paths required by the card.
        """

        self.registry.register_card(
            key=key,
            app=app,
            title=title,
            template=template,
            icon=icon,
            channel=channel,
            col_class=col_class,
            scripts=scripts,
            styles=styles,
        )
        entry = self.registry.get_card(key)
        self._restore_state_from_cache(entry)
        self._invalidate_card_cache()

    def get_card(self, key: str) -> CardEntry:
        """Return the registered card entry associated with ``key``."""

        return self.registry.get_card(key)

    def get_card_virtual(self, key: str) -> VirtualContentKey:
        """Return virtual metadata for the registered card ``key``."""

        entry = self.registry.get_card_virtual(key)
        if entry is None:
            raise ValueError(f"Unknown card: {key}")
        return entry

    def iter_cards(self) -> Iterator[CardEntry]:
        """Yield card entries preserved in the registry."""

        yield from self.registry.iter_cards()

    async def publish_event(self, key: str, payload: Any) -> None:
        """Persist the latest state and publish the payload to the card channel."""

        entry = self.get_card(key)
        message = self._persist_last_state(entry, payload)
        if not entry.channel or message is None:
            return
        await self._event_cache.publish(entry.channel, message)

    def get_last_state(self, key: str) -> Any:
        """Return the previously published payload for the given card."""

        if key in self._last_state:
            return self._last_state[key]
        entry = self.get_card(key)
        if not entry.channel:
            return None
        cached = self._event_cache.get_last_payload(entry.channel)
        if cached is None:
            return None
        payload = self._decode_payload(*cached)
        self._last_state[key] = payload
        return payload

    def configure_card_cache(self, cache: SQLiteCardCache | None) -> None:
        """Attach ``cache`` responsible for card list invalidation."""

        self._card_cache = cache

    def register_publisher(self, publisher: PublisherService) -> None:
        """Register a publisher responsible for streaming updates."""

        if not getattr(publisher, "card_key", None):
            raise ValueError("PublisherService must define a non-empty card_key")
        try:
            self.get_card(publisher.card_key)
        except ValueError as exc:
            raise ValueError(
                f"Card '{publisher.card_key}' must be registered before attaching a publisher"
            ) from exc
        if any(p.card_key == publisher.card_key for p in self._publishers):
            raise ValueError(f"Publisher already registered for card {publisher.card_key}")
        publisher.attach(self)
        self._publishers.append(publisher)

    async def start_publishers(self) -> None:
        """Start all registered publisher services exactly once."""

        if self._publishers_started:
            return
        self._publishers_started = True
        for publisher in self._publishers:
            try:
                initial_state = publisher.get_initial_state()
            except Exception as exc:  # pragma: no cover - defensive runtime logging
                self.logger.warning(
                    "Failed to fetch initial state from %s: %s", publisher.card_key, exc
                )
                initial_state = {}
            if initial_state is not None:
                try:
                    publisher.publish(initial_state)
                except Exception as exc:  # pragma: no cover - runtime guard
                    self.logger.warning(
                        "Failed to publish initial state for %s: %s", publisher.card_key, exc
                    )
            task = asyncio.create_task(self._run_publisher(publisher))
            self._publisher_tasks[publisher] = task
            task.add_done_callback(lambda t, pub=publisher: self._on_publisher_done(pub, t))

    async def shutdown_publishers(self) -> None:
        """Cancel publisher tasks and invoke their shutdown hooks."""

        publishers = list(self._publisher_tasks.keys())
        tasks = [self._publisher_tasks[publisher] for publisher in publishers]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for publisher in publishers:
            await self._call_publisher_shutdown(publisher)
        self._publisher_tasks.clear()
        if self._pending_events:
            pending = list(self._pending_events)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            self._pending_events.clear()
        self._publishers_started = False

    def receive_from_publisher(
        self, publisher: PublisherService, payload: Dict[str, Any]
    ) -> asyncio.Task[Any]:
        """Accept payload from publisher, update cache and propagate events."""

        self._accept_publisher_state(publisher.card_key, payload)
        task = asyncio.create_task(self.publish_event(publisher.card_key, payload))
        self._pending_events.add(task)
        task.add_done_callback(self._pending_events.discard)
        return task

    def _accept_publisher_state(self, key: str, payload: Dict[str, Any]) -> None:
        entry = self.get_card(key)
        self._persist_last_state(entry, payload)

    async def _call_publisher_shutdown(self, publisher: PublisherService) -> None:
        try:
            await publisher.shutdown()
        except Exception as exc:  # pragma: no cover - defensive runtime logging
            self.logger.warning(
                "Publisher %s failed during shutdown: %s", publisher.card_key, exc
            )

    async def _run_publisher(self, publisher: PublisherService) -> None:
        try:
            await publisher.run()
        except asyncio.CancelledError:  # pragma: no cover - cancellation path
            raise
        except Exception as exc:  # pragma: no cover - runtime guard
            self.logger.exception(
                "Publisher %s terminated with error: %s", publisher.card_key, exc
            )

    def _on_publisher_done(
        self, publisher: PublisherService, task: asyncio.Task[Any]
    ) -> None:
        self._publisher_tasks.pop(publisher, None)
        if task.cancelled():  # pragma: no cover - cancellation path
            return
        exc = task.exception()
        if exc is not None:  # pragma: no cover - runtime logging
            self.logger.warning(
                "Publisher %s stopped unexpectedly: %s", publisher.card_key, exc
            )

    @staticmethod
    def _encode_payload(payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, (bytes, bytearray)):
            return payload.decode("utf-8", errors="replace")
        try:
            return json.dumps(payload, ensure_ascii=False)
        except TypeError:
            return json.dumps({"payload": str(payload)}, ensure_ascii=False)

    def _load_persisted_states(self) -> None:
        for entry in self.registry.iter_cards():
            self._restore_state_from_cache(entry)

    def _restore_state_from_cache(self, entry: CardEntry) -> None:
        if entry.channel is None:
            return
        cached = self._event_cache.get_last_payload(entry.channel)
        if cached is None:
            return
        payload = self._decode_payload(*cached)
        self._last_state[entry.key] = payload

    def _persist_last_state(self, entry: CardEntry, payload: Any) -> str | None:
        self._last_state[entry.key] = payload
        if entry.channel is None:
            return None
        message, serializer = self._serialize_payload(payload)
        self._event_cache.store_last_payload(entry.channel, message, serializer)
        return message

    def _invalidate_card_cache(self) -> None:
        if self._card_cache is None:
            return
        try:
            self._card_cache.clear()
        except Exception:  # pragma: no cover - defensive logging
            self.logger.exception("Failed to clear card cache after registration")

    def _serialize_payload(self, payload: Any) -> tuple[str, str]:
        if isinstance(payload, str):
            return payload, "text"
        if isinstance(payload, (bytes, bytearray)):
            return payload.decode("utf-8", errors="replace"), "text"
        try:
            return json.dumps(payload, ensure_ascii=False), "json"
        except TypeError:
            fallback = json.dumps({"payload": str(payload)}, ensure_ascii=False)
            return fallback, "json"

    @staticmethod
    def _decode_payload(payload: str, serializer: str) -> Any:
        if serializer == "json":
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return payload
        return payload
 
    @property
    def event_cache(self) -> SQLiteEventCache:
        """Return the event cache responsible for persisting card events."""

        return self._event_cache

    def configure_event_cache(self, *, path: str | None = None) -> None:
        """Reconfigure the underlying event cache when settings change."""

        target = path or getattr(self._settings, "event_cache_path", ":memory:")
        if target == self._event_cache_path:
            return
        if hasattr(self._event_cache, "reconfigure"):
            self._event_cache.reconfigure(target)
        else:  # pragma: no cover - fallback for custom cache implementations
            self._event_cache = self._event_cache_class(path=target)
        self._event_cache_path = target

    def apply_settings(self, settings: FreeAdminSettings) -> None:
        """Update manager configuration and refresh dependent services."""

        self._settings = settings
        self.configure_event_cache(path=settings.event_cache_path)


__all__ = ["CardManager"]


# The End

