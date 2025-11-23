# -*- coding: utf-8 -*-
"""
export

Advanced export service with format support and caching.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Sequence
from uuid import uuid4

from openpyxl import Workbook

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from freeadmin.config import FreeAdminSettings, current_settings
from ....contrib.adapters import BaseAdapter
from ..cache.sqlite_kv import SQLiteKeyValueCache


class FieldSerializer:
    """Serialize object fields to JSON-compatible values.

    Supported types include ``datetime``/``date`` (ISO 8601), ``list``/``tuple``
    (recursively serialized), ``set`` (converted to list) and nested
    structures like ``dict``.
    """

    def serialize(self, obj: Any, field: str) -> Any:
        """Return serialized value for ``field`` on ``obj``."""
        id_field = f"{field}_id"
        if hasattr(obj, id_field):
            return getattr(obj, id_field)
        value = getattr(obj, field, None)
        return self._serialize(value)

    def _serialize(self, value: Any) -> Any:
        """Recursively convert ``value`` to a JSON-friendly representation."""
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serialize(v) for v in value]
        if isinstance(value, set):
            return [self._serialize(v) for v in value]
        module = getattr(value, "__class__", object).__module__
        if module.startswith("tortoise"):
            cache = getattr(value, "_result_cache", None)
            if cache is not None:
                return [
                    self._serialize(getattr(obj, "id", obj))
                    for obj in cache
                ]
            if getattr(value, "_is_fetched", False):
                try:
                    return [
                        self._serialize(getattr(obj, "id", obj))
                        for obj in value
                    ]
                except Exception:
                    pass
        if hasattr(value, "id"):
            return getattr(value, "id")
        if hasattr(value, "dict"):
            try:
                return {
                    k: self._serialize(v)
                    for k, v in value.dict().items()
                }
            except Exception:
                pass
        return str(value)


@dataclass
class CachedFile:
    path: Path
    filename: str
    mime: str
    expires_at: datetime


class BaseCacheBackend:
    """Interface for cache backends."""

    def set(self, token: str, info: CachedFile) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def get(self, token: str) -> CachedFile | None:  # pragma: no cover - interface
        raise NotImplementedError

    def delete(self, token: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def items(self) -> list[tuple[str, CachedFile]]:  # pragma: no cover - interface
        raise NotImplementedError

    def prune_expired(self) -> None:
        """Remove expired entries when supported by the backend."""

        return None


class MemoryCacheBackend(BaseCacheBackend):
    """In-memory cache backend."""

    def __init__(self) -> None:
        self._store: dict[str, CachedFile] = {}

    def set(self, token: str, info: CachedFile) -> None:
        self._store[token] = info

    def get(self, token: str) -> CachedFile | None:
        return self._store.get(token)

    def delete(self, token: str) -> None:
        self._store.pop(token, None)

    def items(self) -> list[tuple[str, CachedFile]]:
        return list(self._store.items())

    def prune_expired(self) -> None:
        """Remove stale entries whose expiration has elapsed."""

        now = datetime.now()
        self._store = {
            token: info for token, info in self._store.items() if info.expires_at > now
        }


class SQLiteExportCacheBackend(BaseCacheBackend):
    """Persist export cache metadata in an SQLite database."""

    def __init__(
        self,
        path: str | None = None,
        *,
        table_name: str = "export_cache",
    ) -> None:
        """Create a new backend bound to ``path`` and ``table_name``."""

        self._store = SQLiteKeyValueCache(path, table_name=table_name)

    @property
    def path(self) -> str:
        """Return the SQLite database path used by this backend."""

        return self._store.path

    def set(self, token: str, info: CachedFile) -> None:
        """Persist ``info`` under ``token`` with its expiration timestamp."""

        payload = json.dumps(
            {
                "path": str(info.path),
                "filename": info.filename,
                "mime": info.mime,
            }
        ).encode("utf-8")
        self._store.set(token, payload, info.expires_at)

    def get(self, token: str) -> CachedFile | None:
        """Return cached file metadata for ``token`` if still valid."""

        record = self._store.get(token)
        if record is None:
            return None
        payload, expires_at = record
        try:
            data = json.loads(payload.decode("utf-8"))
        except (TypeError, ValueError, json.JSONDecodeError):
            self._store.delete(token)
            return None
        return CachedFile(
            path=Path(data["path"]),
            filename=data["filename"],
            mime=data["mime"],
            expires_at=expires_at,
        )

    def delete(self, token: str) -> None:
        """Remove cached metadata for ``token`` if it exists."""

        self._store.delete(token)

    def items(self) -> list[tuple[str, CachedFile]]:
        """Return all non-expired cached file entries."""

        items = []
        for token, payload, expires_at in self._store.items():
            try:
                data = json.loads(payload.decode("utf-8"))
            except (TypeError, ValueError, json.JSONDecodeError):
                self._store.delete(token)
                continue
            items.append(
                (
                    token,
                    CachedFile(
                        path=Path(data["path"]),
                        filename=data["filename"],
                        mime=data["mime"],
                        expires_at=expires_at,
                    ),
                )
            )
        return items

    def prune_expired(self) -> None:
        """Delete expired rows from the underlying SQLite table."""

        self._store.prune_expired()


class ExportTransformer(ABC):
    """Transform serialized rows into a formatted representation."""

    @abstractmethod
    def render(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> str | bytes:
        """Return formatted content for ``rows``."""

    @abstractmethod
    def stream(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> AsyncGenerator[bytes, None]:
        """Yield formatted chunks for ``rows``."""


class CsvTransformer(ExportTransformer):
    def render(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buffer.getvalue()

    async def stream(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> AsyncGenerator[bytes, None]:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)
        for row in rows:
            writer.writerow(row)
            yield buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)


class JsonTransformer(ExportTransformer):
    def render(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> str:
        return json.dumps(rows, ensure_ascii=False)

    async def stream(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> AsyncGenerator[bytes, None]:
        yield b"["
        first = True
        for row in rows:
            chunk = json.dumps(row, ensure_ascii=False).encode("utf-8")
            if not first:
                yield b"," + chunk
            else:
                yield chunk
                first = False
        yield b"]"


class XlsxTransformer(ExportTransformer):
    def render(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.append(fields)
        for row in rows:
            ws.append([row[f] for f in fields])
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    async def stream(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> AsyncGenerator[bytes, None]:
        raise HTTPException(status_code=400, detail="Streaming not supported")


class ExportWriter(ABC):
    """Handle file streaming and writing for export formats."""

    mime: str
    suffix: str

    def __init__(self, transformer: ExportTransformer) -> None:
        self.transformer = transformer

    @abstractmethod
    def write(
        self, path: Path, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> None:
        """Write ``rows`` to ``path``."""

    def stream(
        self, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> AsyncGenerator[bytes, None]:
        """Delegate to the transformer for streaming."""
        return self.transformer.stream(fields, rows)


class CsvWriter(ExportWriter):
    mime = "text/csv"
    suffix = ".csv"

    def write(
        self, path: Path, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> None:
        content = self.transformer.render(fields, rows)
        with path.open("w", newline="", encoding="utf-8") as f:
            f.write(content)


class JsonWriter(ExportWriter):
    mime = "application/json"
    suffix = ".json"

    def write(
        self, path: Path, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> None:
        content = self.transformer.render(fields, rows)
        with path.open("w", encoding="utf-8") as f:
            f.write(content)


class XlsxWriter(ExportWriter):
    mime = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    suffix = ".xlsx"

    def write(
        self, path: Path, fields: Sequence[str], rows: Sequence[dict[str, Any]]
    ) -> None:
        content = self.transformer.render(fields, rows)
        with path.open("wb") as f:
            f.write(content)


class QueryStep:
    """Fetch objects using the adapter and filter fields."""

    def __init__(self, adapter: BaseAdapter) -> None:
        self.adapter = adapter

    async def run(
        self, queryset: Any, fields: Sequence[str]
    ) -> tuple[Sequence[Any], list[str]]:
        objects = await self.adapter.fetch_all(queryset)
        allowed = list(dict.fromkeys(fields))
        return objects, allowed


class SerializationStep:
    """Serialize objects using ``FieldSerializer``."""

    def __init__(self, serializer: FieldSerializer) -> None:
        self.serializer = serializer

    def run(
        self, objects: Sequence[Any], fields: Sequence[str]
    ) -> list[dict[str, Any]]:
        return [
            {name: self.serializer.serialize(obj, name) for name in fields}
            for obj in objects
        ]


class FormattingStep:
    """Select writer implementation for given format."""

    def __init__(self, writers: dict[str, ExportWriter]) -> None:
        self.writers = writers

    def run(self, fmt: str) -> ExportWriter:
        writer = self.writers.get(fmt)
        if not writer:
            raise HTTPException(status_code=400, detail="Unsupported format")
        return writer


class FileWriterStep:
    """Write formatted data to disk and cache the file."""

    def __init__(
        self,
        tmp_dir: str,
        ttl: int,
        cache: BaseCacheBackend,
        schedule_cleanup: Callable[[str, datetime], None],
    ) -> None:
        self.tmp_dir = tmp_dir
        self.ttl = ttl
        self.cache = cache
        self.schedule_cleanup = schedule_cleanup

    async def run(
        self,
        writer: ExportWriter,
        fields: Sequence[str],
        rows: Sequence[dict[str, Any]],
        model_name: str | None = None,
    ) -> str:
        prune = getattr(self.cache, "prune_expired", None)
        if callable(prune):
            prune()

        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=writer.suffix, dir=self.tmp_dir
        )
        path = Path(tmp.name)
        tmp.close()

        await asyncio.to_thread(writer.write, path, fields, rows)
        mime = writer.mime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = (model_name or "export").lower()
        filename = f"{prefix}_{timestamp}{writer.suffix}"
        token = uuid4().hex
        expires_at = datetime.now() + timedelta(seconds=self.ttl)
        self.cache.set(token, CachedFile(path, filename, mime, expires_at))
        self.schedule_cleanup(token, expires_at)
        return token


class ExportPipeline:
    """Orchestrate export steps."""

    def __init__(
        self,
        query_step: QueryStep,
        serialization_step: SerializationStep,
        formatting_step: FormattingStep,
        file_writer_step: FileWriterStep,
    ) -> None:
        self.query_step = query_step
        self.serialization_step = serialization_step
        self.formatting_step = formatting_step
        self.file_writer_step = file_writer_step

    async def run(
        self,
        queryset: Any,
        fields: Sequence[str],
        fmt: str,
        model_name: str | None = None,
    ) -> str:
        objects, allowed = await self.query_step.run(queryset, fields)
        serialized = self.serialization_step.run(objects, allowed)
        writer = self.formatting_step.run(fmt)
        return await self.file_writer_step.run(
            writer, allowed, serialized, model_name=model_name
        )


class ExportService:
    """Export model data to various formats with temporary caching.

    Supports pluggable cache backends for distributed environments.
    """

    def __init__(
        self,
        adapter: BaseAdapter,
        tmp_dir: str | None = None,
        ttl: int | None = None,
        serializer: FieldSerializer | None = None,
        cache_backend: BaseCacheBackend | None = None,
        cleanup_interval: int = 60,
        *,
        settings: FreeAdminSettings | None = None,
    ) -> None:
        self.adapter = adapter
        self.settings = settings or current_settings()
        self.tmp_dir = tmp_dir or tempfile.gettempdir()
        self.ttl = ttl if ttl is not None else self.settings.export_cache_ttl
        self.serializer = serializer or FieldSerializer()
        self.cache = cache_backend or SQLiteExportCacheBackend(
            path=self.settings.export_cache_path
        )
        self.cleanup_interval = cleanup_interval
        self.writers: dict[str, ExportWriter] = {
            "csv": CsvWriter(CsvTransformer()),
            "json": JsonWriter(JsonTransformer()),
            "xlsx": XlsxWriter(XlsxTransformer()),
        }
        self.pipeline = ExportPipeline(
            QueryStep(self.adapter),
            SerializationStep(self.serializer),
            FormattingStep(self.writers),
            FileWriterStep(
                self.tmp_dir, self.ttl, self.cache, self._schedule_token_cleanup
            ),
        )
        self.cache.prune_expired()
        self._purge_temp_dir()
        self._restore_cache_state()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            loop.create_task(self._periodic_purge())

    async def _collect(
        self, queryset: Any, fields: Sequence[str], limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch objects and serialize ``fields``."""
        qs = self.adapter.limit(queryset, limit) if limit is not None else queryset
        objects, allowed = await self.pipeline.query_step.run(qs, fields)
        return self.pipeline.serialization_step.run(objects, allowed)

    async def export(self, queryset: Any, fields: Sequence[str]) -> list[dict[str, Any]]:
        """Return list of dictionaries for given queryset and fields."""
        return await self._collect(queryset, fields)

    async def preview(self, queryset: Any, fields: Sequence[str], limit: int = 20) -> list[dict[str, Any]]:
        """Return first ``limit`` rows for preview."""
        allowed = list(dict.fromkeys(fields))
        return await self._collect(queryset, allowed, limit)

    async def run(
        self,
        queryset: Any,
        fields: Sequence[str],
        fmt: str,
        model_name: str | None = None,
    ) -> str:
        """Export ``queryset`` into ``fmt`` file and cache it.

        Returns a cache token for later retrieval.
        """
        return await self.pipeline.run(queryset, fields, fmt, model_name=model_name)

    async def stream(
        self, queryset: Any, fields: Sequence[str], fmt: str
    ) -> StreamingResponse:
        """Stream exported data as ``StreamingResponse``."""
        objects, allowed = await self.pipeline.query_step.run(queryset, fields)
        rows = self.pipeline.serialization_step.run(objects, allowed)
        writer = self.pipeline.formatting_step.run(fmt)
        generator = writer.stream(allowed, rows)
        return StreamingResponse(generator, media_type=writer.mime)

    def get_file(self, token: str) -> CachedFile:
        """Return cached file metadata for ``token``."""
        info = self.cache.get(token)
        if not info or info.expires_at < datetime.now():
            self.cleanup(token)
            raise HTTPException(status_code=404)
        return info

    def cleanup(self, token: str) -> None:
        """Remove cached file for ``token`` from disk."""
        info = self.cache.get(token)
        self.cache.delete(token)
        if not info:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._unlink_file(info.path)
        else:
            loop.create_task(asyncio.to_thread(self._unlink_file, info.path))

    def _schedule_token_cleanup(self, token: str, expires_at: datetime) -> None:
        """Schedule removal of ``token`` when ``expires_at`` is reached."""

        delay = max((expires_at - datetime.now()).total_seconds(), 0.0)
        if delay <= 0:
            self.cleanup(token)
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.call_later(delay, lambda t=token: self.cleanup(t))

    def _restore_cache_state(self) -> None:
        """Reload persisted cache entries and reschedule their cleanups."""

        now = datetime.now()
        for token, info in list(self.cache.items()):
            if info.expires_at <= now:
                self.cleanup(token)
            else:
                self._schedule_token_cleanup(token, info.expires_at)

    @staticmethod
    def _unlink_file(path: Path) -> None:
        """Remove ``path`` from disk, ignoring missing files."""

        try:
            path.unlink(missing_ok=True)
        except TypeError:  # pragma: no cover - Python < 3.8 compatibility
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    async def _periodic_purge(self) -> None:
        while True:
            await asyncio.sleep(self.cleanup_interval)
            self.cache.prune_expired()
            for token, info in list(self.cache.items()):
                if info.expires_at < datetime.now():
                    self.cleanup(token)

    def _purge_temp_dir(self) -> None:
        now = datetime.now()
        for file in Path(self.tmp_dir).glob("export_*"):
            try:
                modified = datetime.fromtimestamp(file.stat().st_mtime)
                if now - modified > timedelta(seconds=self.ttl):
                    file.unlink()
            except Exception:
                pass

# The End

