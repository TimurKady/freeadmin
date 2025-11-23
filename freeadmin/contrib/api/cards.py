# -*- coding: utf-8 -*-
"""
cards

Server-Sent Events endpoints for cards.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from freeadmin.config import (
    FreeAdminSettings,
    current_settings,
    register_settings_observer,
)
from ...core.interface.settings import SettingsKey, system_config

from ...core.interface.auth import admin_auth_service
from ...core.interface.exceptions import PermissionDenied
from ...core.interface.permissions import permission_checker
from ...core.interface.services.auth import AdminUserDTO
from ...core.interface.services.permissions import PermAction
from ...core.interface.services.tokens import ScopeTokenService
from ...core.interface.cache import SQLiteEventCache

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from freeadmin.admin import AdminSite


class CardEventStreamer:
    """Manage event delivery for cards."""

    def __init__(
        self,
        event_cache: SQLiteEventCache | None = None,
        *,
        heartbeat_interval: float = 10.0,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        """Initialize the streamer with an optional event cache backend."""

        self._settings = settings or current_settings()
        cache_path = getattr(self._settings, "event_cache_path", ":memory:")
        self._event_cache = event_cache or SQLiteEventCache(path=cache_path)
        self._event_cache_class: type[SQLiteEventCache] = (
            type(event_cache) if event_cache is not None else SQLiteEventCache
        )
        self._event_cache_path = getattr(self._event_cache, "path", cache_path)
        self.heartbeat_interval = heartbeat_interval
        self.logger = logging.getLogger(__name__)

    @property
    def event_cache(self) -> SQLiteEventCache:
        """Return the event cache backend used to supply channel events."""

        return self._event_cache

    async def stream(
        self, channel: str | None, *, cache: SQLiteEventCache | None = None
    ) -> AsyncIterator[str]:
        """Yield SSE chunks for ``channel`` or heartbeat fallbacks using ``cache``."""
        if not channel:
            async for chunk in self._heartbeat():
                yield chunk
            return
        yield self._format_comment("connected")
        queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        backend = cache or self.event_cache

        async def _pump(
            name: str, iterator: AsyncIterator[str]
        ) -> None:
            try:
                async for message in iterator:
                    await queue.put((name, message))
            except asyncio.CancelledError:  # pragma: no cover - cancellation
                raise
            finally:
                await queue.put((name, None))

        tasks = {
            "channel": asyncio.create_task(
                _pump("channel", self._channel_stream(channel, backend))
            ),
            "heartbeat": asyncio.create_task(
                _pump("heartbeat", self._heartbeat())
            ),
        }
        finished: set[str] = set()
        try:
            while len(finished) < len(tasks):
                name, chunk = await queue.get()
                if chunk is None:
                    if name not in finished:
                        finished.add(name)
                        other = (set(tasks) - {name}).pop()
                        if other not in finished:
                            tasks[other].cancel()
                    continue
                yield chunk
        finally:
            for task in tasks.values():
                task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)

    async def _channel_stream(
        self, channel: str, cache: SQLiteEventCache
    ) -> AsyncIterator[str]:
        subscription = await cache.subscribe(channel)
        try:
            async for message in subscription:
                payload = self._serialize(message)
                yield self._format_data(payload)
        except asyncio.CancelledError:  # pragma: no cover - cancellation
            raise

    async def _heartbeat(self) -> AsyncIterator[str]:
        try:
            while True:
                yield "event: ping\n\n"
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:  # pragma: no cover - cancellation
            raise

    def _serialize(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, (bytes, bytearray)):
            try:
                return payload.decode("utf-8")
            except UnicodeDecodeError:
                return payload.decode("utf-8", errors="replace")
        return json.dumps(payload, ensure_ascii=False)

    def _format_data(self, payload: str) -> str:
        lines = payload.splitlines() or [""]
        body = "".join(f"data: {line}\n" for line in lines)
        return f"{body}\n"

    def _format_comment(self, message: str) -> str:
        return f": {message}\n\n"

    def configure_event_cache(self, *, path: str | None = None) -> None:
        """Reconfigure the internal cache when settings or overrides change."""

        target = path or getattr(self._settings, "event_cache_path", ":memory:")
        if target == self._event_cache_path:
            return
        if hasattr(self._event_cache, "reconfigure"):
            self._event_cache.reconfigure(target)
        else:  # pragma: no cover - fallback for alternate cache implementations
            self._event_cache = self._event_cache_class(path=target)
        self._event_cache_path = target

    def apply_settings(self, settings: FreeAdminSettings) -> None:
        """Refresh streamer configuration using the provided ``settings``."""

        self._settings = settings
        self.configure_event_cache(path=settings.event_cache_path)


class CardEventsTokenService:
    """Issue and verify signed tokens for card event streams."""

    def __init__(
        self,
        scope_service: ScopeTokenService | None = None,
        *,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        """Initialize the service with an optional ``scope_service``."""

        self._settings = settings or current_settings()
        self._scope_service = scope_service or ScopeTokenService(settings=self._settings)

    def issue(self, *, card_key: str, user: AdminUserDTO, ttl: int) -> str:
        """Return a signed token for ``card_key`` granted to ``user``."""

        payload = {
            "card": card_key,
            "user": {"id": user.id, "username": user.username},
        }
        return self._scope_service.sign(payload, ttl)

    def verify(self, token: str) -> dict[str, Any]:
        """Return the decoded payload from ``token`` if valid."""

        return self._scope_service.verify(token)

    def apply_settings(self, settings: FreeAdminSettings) -> None:
        """Refresh token signing configuration after settings changes."""
        self._settings = settings
        if hasattr(self._scope_service, "apply_settings"):
            self._scope_service.apply_settings(settings)
        else:  # pragma: no cover - legacy adapters without refresh support
            self._scope_service = ScopeTokenService(settings=self._settings)


class CardSSEAPI:
    """Expose SSE endpoint for cards."""

    def __init__(
        self,
        streamer: CardEventStreamer | None = None,
        token_service: CardEventsTokenService | None = None,
        token_ttl: int | None = None,
        *,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        """Configure router and dependencies for card events."""

        self._settings = settings or current_settings()
        self.streamer = streamer or CardEventStreamer(settings=self._settings)
        self.permission_checker = permission_checker
        self.token_service = token_service or CardEventsTokenService(settings=self._settings)
        self._token_ttl_override = token_ttl
        self.public_router = APIRouter()
        self.admin_router = APIRouter()
        self.router = self.admin_router
        self.public_router.get(
            "/api/cards/{key}/events", response_class=StreamingResponse
        )(self.stream_card_events)
        self.admin_router.get("/api/cards/{key}/state")(self.get_card_state)
        self.admin_router.get("/api/cards/{key}/events/token")(self.issue_card_token)
        register_settings_observer(self._apply_settings)

    @property
    def token_ttl(self) -> int:
        """Return the TTL used when issuing card event tokens."""

        if self._token_ttl_override is not None:
            return self._token_ttl_override
        return system_config.get_cached(
            SettingsKey.CARD_EVENTS_TOKEN_TTL,
            self._settings.card_events_token_ttl,
        )

    def _apply_settings(self, settings: FreeAdminSettings) -> None:
        """Update dependent services with refreshed configuration."""
        self._settings = settings
        self.streamer.apply_settings(settings)
        self.token_service.apply_settings(settings)

    def _get_admin_site(self, request: Request) -> "AdminSite":
        admin_site = getattr(request.app.state, "admin_site", None)
        if admin_site is None:
            raise HTTPException(status_code=500, detail="Admin site not configured")
        return admin_site

    def _get_card_entry(self, admin_site: "AdminSite", key: str) -> Any:
        try:
            return admin_site.cards.get_card(key)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def _ensure_card_permission(
        self,
        user: Any,
        key: str,
        admin_site: "AdminSite",
    ) -> None:
        if hasattr(admin_site.cards, "get_card_virtual"):
            await self.permission_checker.check_card(
                user,
                key,
                PermAction.view,
                admin_site=admin_site,
            )
            return
        permissions = getattr(user, "permissions", set())
        if getattr(user, "is_superuser", False):
            return
        if "view" not in permissions:
            raise PermissionDenied("Permission denied")

    async def stream_card_events(
        self,
        request: Request,
        key: str,
        token: str | None = None,
    ) -> StreamingResponse:
        """Return Server-Sent Events for ``key`` validated by ``token``."""

        admin_site = self._get_admin_site(request)
        if token:
            try:
                payload = self.token_service.verify(token)
            except ValueError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
            if payload.get("card") != key:
                raise HTTPException(
                    status_code=403,
                    detail="Token does not grant access to this card",
                )
        else:
            try:
                user = await admin_auth_service.get_current_admin_user(request)
            except HTTPException as exc:
                if exc.status_code == 401:
                    raise HTTPException(status_code=401, detail="Missing token") from exc
                raise
            orm_user = getattr(request.state, "user", None) or user
            try:
                await self._ensure_card_permission(orm_user, key, admin_site)
            except PermissionDenied as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
        entry = self._get_card_entry(admin_site, key)
        generator = self.streamer.stream(
            entry.channel, cache=admin_site.cards.event_cache
        )
        return StreamingResponse(generator, media_type="text/event-stream")

    async def get_card_state(
        self,
        request: Request,
        key: str,
        user: AdminUserDTO = Depends(admin_auth_service.get_current_admin_user),
    ) -> Any:
        """Return the latest known card state or ``{"status": "no-data"}``."""

        admin_site = getattr(request.app.state, "admin_site", None)
        if admin_site is None:
            raise HTTPException(status_code=500, detail="Admin site not configured")
        try:
            entry = admin_site.cards.get_card(key)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            orm_user = getattr(request.state, "user", None) or user
            await self._ensure_card_permission(orm_user, key, admin_site)
        except PermissionDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        state = admin_site.cards.get_last_state(key)
        if state is None:
            return {"status": "no-data"}
        return state

    async def issue_card_token(
        self,
        request: Request,
        key: str,
        user: AdminUserDTO = Depends(admin_auth_service.get_current_admin_user),
    ) -> dict[str, Any]:
        """Return a signed token granting SSE access to ``key``."""

        admin_site = self._get_admin_site(request)
        entry = self._get_card_entry(admin_site, key)
        orm_user = getattr(request.state, "user", None) or user
        try:
            await self._ensure_card_permission(orm_user, key, admin_site)
        except PermissionDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        ttl = self.token_ttl
        token = self.token_service.issue(card_key=entry.key, user=user, ttl=ttl)
        return {"token": token, "expires_in": ttl}


_api = CardSSEAPI()
router = _api.router
public_router = _api.public_router

__all__ = ["CardSSEAPI", "router", "public_router"]


# The End

