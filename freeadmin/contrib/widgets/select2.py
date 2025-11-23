# -*- coding: utf-8 -*-
"""
Select2 Widget

Remote select widget backed by Select2.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional

from ...core.interface.settings import SettingsKey, system_config
from freeadmin.config import current_settings
from .base import BaseWidget
from .mixins import RelationChoicesMixin, RelationPrefetchMixin, RelationValueMixin
from .registry import registry


logger = logging.getLogger(__name__)


@registry.register("select2")
class Select2Widget(
    RelationChoicesMixin, RelationPrefetchMixin, RelationValueMixin, BaseWidget
):
    """Select2 field for FK relations with proper ajax.url and lazy loading."""

    prefetch_requires_instance = False
    prefetch_sample_size: int = 8
    assets_css = ("/static/vendors/select2/css/select2.min.css",)
    assets_js = (
        "/static/vendors/jquery/jquery-3.7.1.min.js",
        "/static/vendors/select2/js/select2.min.js",
        "/static/widgets/select2.js",
    )

    @property
    def base_url(self) -> str:
        """Return the base lookup API prefix: '/<ADMIN>/<API>/lookup'."""
        admin_prefix = system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, current_settings().admin_path
        )
        api_prefix = system_config.get_cached(SettingsKey.API_PREFIX, "/api")
        lookup = system_config.get_cached(SettingsKey.API_LOOKUP, "/lookup")

        admin_prefix = admin_prefix.strip("/")
        api_prefix = api_prefix.strip("/")
        lookup_path = lookup.lstrip("/")
        full_prefix = "/".join(filter(None, [admin_prefix, api_prefix]))

        if not lookup_path:
            msg = "API_LOOKUP setting cannot be empty."
            logger.error(msg)
            raise ValueError(msg)

        if lookup_path.startswith(full_prefix):
            return f"/{lookup_path}"

        for prefix in (admin_prefix, api_prefix):
            if prefix and (lookup_path == prefix or lookup_path.startswith(f"{prefix}/")):
                lookup_path = lookup_path[len(prefix):].lstrip("/")

        if lookup_path.startswith(admin_prefix) or lookup_path.startswith(api_prefix):
            msg = "API_LOOKUP conflicts with configured prefixes."
            logger.error(msg)
            raise ValueError(msg)

        return f"/{full_prefix}/{lookup_path}" if lookup_path else f"/{full_prefix}"

    # ----------------- helpers -----------------

    @staticmethod
    def _norm(x: Any) -> str:
        return str(x).strip().lower().replace(".", "_").replace(" ", "_") if x else ""

    def _get_owner_app_model(self) -> tuple[Optional[str], Optional[str]]:
        """Return the owning app/model pair extracted from ``ctx.descriptor``."""

        ctx = getattr(self, "ctx", None)
        descriptor = getattr(ctx, "descriptor", None)
        if descriptor is None:
            return None, None

        app_label = getattr(descriptor, "app_label", None)
        model_name = getattr(descriptor, "model_name", None)
        return app_label, model_name

    def _resolve_lookup_url(self) -> str:
        """
        Build ajax.url by checking, in order:
          1) meta['lookup_path'] or self.lookup_path (highest priority)
          2) /<admin>/<api>/lookup/<owner_app>/<owner_model>/<field>
          3) /<admin>/<api>/lookup/<field> (final fallback)
        """
        base = self.base_url.rstrip("/")

        # 1) Explicit override
        fd = getattr(getattr(self, "ctx", None), "field", None)
        meta = dict(getattr(fd, "meta", {}) or {})
        override = meta.get("lookup_path") or getattr(self, "lookup_path", None)
        if override:
            override = str(override).lstrip("/")
            return f"{base}/{override}"

        # 2) Owner app + field name
        field_name = getattr(fd, "name", None)
        app, model = self._get_owner_app_model()

        app_s = self._norm(app)
        model_s = self._norm(model)
        field_s = self._norm(field_name)

        if app_s and model_s and field_s:
            return f"{base}/{app_s}/{model_s}/{field_s}"

        # 3) Fallback: field name only
        if field_s:
            return f"{base}/{field_s}"

        logger.warning("Select2Widget: unable to resolve full lookup URL, fallback to base only")
        return base

    def _limit_prefetched_choices(
        self, enum: List[str], titles: List[str]
    ) -> Tuple[List[str], List[str]]:
        """Trim the list to ``sample_size`` while preserving the selected value."""
        limit = getattr(self, "prefetch_sample_size", 0)
        if limit <= 0 or len(enum) <= limit:
            return enum, titles

        start_value = self.get_startval()
        selected = str(start_value) if start_value not in (None, "", []) else None

        trimmed_enum: List[str] = []
        trimmed_titles: List[str] = []
        seen: set[str] = set()
        counted: int = 0

        for value, label in zip(enum, titles):
            trimmed_enum.append(value)
            trimmed_titles.append(label)
            seen.add(value)
            if value != "":
                counted += 1
            if counted >= limit:
                break

        if selected and selected not in seen and selected in enum:
            idx = enum.index(selected)
            trimmed_enum.append(enum[idx])
            trimmed_titles.append(titles[idx])

        return trimmed_enum, trimmed_titles

    async def prefetch(self) -> None:
        """Prepare ``choices_map`` and trim it down to ``prefetch_sample_size``."""
        await super().prefetch()

        fd_ctx = getattr(self, "ctx", None)
        fd = getattr(fd_ctx, "field", None)
        rel = getattr(fd, "relation", None)
        if not fd or not rel or getattr(rel, "kind", "").lower() != "fk":
            return

        meta = dict(getattr(fd, "meta", {}) or {})
        choices_map = dict(meta.get("choices_map") or {})
        if not choices_map:
            object.__setattr__(fd, "meta", meta)
            return

        sample_size = getattr(self, "prefetch_sample_size", 0)
        if sample_size <= 0:
            object.__setattr__(fd, "meta", meta)
            return

        items = list(choices_map.items())
        limited_map: dict[str, str] = dict(items[:sample_size])

        start_value = self.get_startval()
        if start_value not in (None, "", []) and start_value in choices_map:
            limited_map[str(start_value)] = choices_map[str(start_value)]

        meta["choices_map"] = limited_map
        object.__setattr__(fd, "meta", meta)

    # ----------------- schema -----------------

    def get_schema(self) -> Dict[str, Any]:
        """Return JSON Schema for FK/M2M without calling ``super().get_schema()``."""

        ajax_url = self._resolve_lookup_url()

        select2_opts = {
            "ajax": {
                "url": ajax_url,
                "delay": 250,
                "processResults": {
                    "__js__": "data => ({results: data.results.map(o => ({id:o.id, text:o.title}))})"
                },
            },
            "minimumInputLength": 0,
        }

        fd_ctx = getattr(self, "ctx", None)
        fd = getattr(fd_ctx, "field", None)
        rel = getattr(fd, "relation", None)

        if not rel or getattr(rel, "kind", "").lower() != "fk":
            msg = "Select2Widget supports only FK relations."
            logger.error(msg)
            raise ValueError(msg)

        enum: List[str] = []
        enum_titles: List[str] = []
        placeholder = "--- Select ---"
        if fd is not None:
            required = bool(getattr(fd, "required", False))
            enum, enum_titles, placeholder = self.build_choices(fd, False, required)
            enum, enum_titles = self._limit_prefetched_choices(enum, enum_titles)

        if placeholder and "" not in enum:
            enum.insert(0, "")
            enum_titles.insert(0, placeholder)

        select2_config = {**select2_opts, "placeholder": placeholder}

        schema = {
            "type": "string",
            "format": "select2",
            "options": {
                "select2": select2_config,
                "placeholder": placeholder,
            },
        }
        schema["title"] = self.get_title()
        schema["enum"] = enum
        schema["options"]["enum_titles"] = enum_titles
        return self.merge_readonly(schema)

# The End

