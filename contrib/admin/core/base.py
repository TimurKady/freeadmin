# -*- coding: utf-8 -*-
"""
base

Base class for model admin objects.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from fastapi import HTTPException
from tortoise import Tortoise, fields as tfields
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.fields.relational import (
    ForeignKeyFieldInstance,
    ManyToManyFieldInstance,
)
from tortoise.queryset import QuerySet

from ..widgets import registry as widget_registry
from ..widgets.context import WidgetContext
from ..widgets.base import BaseWidget



class BaseModelAdmin:
    """Basic interface of the model admin class.

    Responsibility lines
    --------------------
    * All ``get_*_queryset`` methods return :class:`~tortoise.queryset.QuerySet`.
    * ``apply_row_level_security`` is applied to all read and edit operations.
    * The ``allow`` hook only affects the UI and does not replace RBAC checks.
    """

    # Name for menu and headings (plural and singular)
    label: str | None = None
    label_singular: str | None = None

    list_display: Sequence[str] = ()
    search_fields: Sequence[str] = ()
    list_filter: Sequence[str] | None = None
    ordering: Sequence[str] = ("id",)
    fieldsets: tuple[tuple[str, dict[str, Any]], ...] | None = None
    fields: Sequence[str] | None = None
    readonly_fields: set[str] = set()
    autocomplete_fields: Sequence[str] = ()
    list_use_only: bool = False
    # Later: list_display, search_fields, list_filter, ordering, fieldsets, etc.
    
    # Global Admin Assets
    admin_assets_css: tuple[str, ...] = ()
    admin_assets_js: tuple[str, ...] = ()

    FILTER_OPS = {"": "eq", "icontains": "icontains", "gte": "gte", "lte": "lte", "gt": "gt", "lt": "lt", "in": "in"}
    widgets_overrides: dict[str, str] = {}

    class Meta:
        """Meta class for BaseModelAdmin."""

        pass

    def __init__(self, model: type[Any]):
        """Save the model class administered by this instance."""
        self.model = model

    # --- attribute accessors -------------------------------------------------

    def get_label(self) -> str | None:
        """Return plural label for the model."""
        return self.label

    def get_label_singular(self) -> str | None:
        """Return singular label for the model."""
        return self.label_singular

    def get_list_display(self) -> Sequence[str]:
        """Return fields displayed in list views."""
        return self.list_display

    def get_list_filter(self) -> Sequence[str]:
        """Return configured list filters."""
        return self.list_filter or ()

    def get_ordering(self) -> Sequence[str]:
        """Return default ordering for list views."""
        return self.ordering

    def get_readonly_fields(self) -> Sequence[str]:
        """Return fields marked as read-only."""
        return self.readonly_fields

    def get_autocomplete_fields(self) -> Sequence[str]:
        """Return fields using autocomplete widgets."""
        return self.autocomplete_fields

    def is_field_readonly(self, md, name: str, mode: str, obj=None) -> bool:
        if name in self.readonly_fields:
            return True
        fd = md.fields_map[name]
        if getattr(fd, "primary_key", False):
            return True
        if name in {"created_at", "updated_at"}:
            return True
        return False

    # --- verbose names ---------------------------------------------------------

    def get_verbose_name(self) -> str:
        """
        Human-friendly singular name for the model.

        Preference order:
          1) self.model._meta.verbose_name
          2) self.label_singular
          3) self.label
          4) model class name normalized
        """
        md = getattr(self.model, "_meta", None)
        name = None
        if md is not None:
            name = getattr(md, "verbose_name", None)
        if not name and hasattr(self.model, "Meta"):
            name = getattr(self.model.Meta, "verbose_name", None)
        if not name:
            name = getattr(self, "label_singular", None) or getattr(self, "label", None)
        if not name:
            # Fallback: class name -> "Foo Bar", not "foo_bar"
            raw = getattr(self.model, "__name__", "") or "Model"
            name = raw.replace("_", " ").title()
        return str(name)

    def get_verbose_name_plural(self) -> str:
        """
        Human-friendly plural name for the model.

        Preference order:
          1) self.model._meta.verbose_name_plural
          2) self.label
          3) singular + 's' (very naive) OR normalized class name
        """
        md = getattr(self.model, "_meta", None)
        name = None
        if md is not None:
            name = getattr(md, "verbose_name_plural", None)
        if not name and hasattr(self.model, "Meta"):
            name = getattr(self.model.Meta, "verbose_name_plural", None)
        if not name:
            name = getattr(self, "label", None)
        if not name:
            # Fallback: try naive plural from singular
            singular = self.get_verbose_name()
            if singular and singular != "Model":
                name = f"{singular}s"
            else:
                raw = getattr(self.model, "__name__", "") or "Models"
                name = raw.replace("_", " ").title()
        return str(name)

    # --- permissions ------------------------------------------------------

    def allow(self, user: Any, action: str, obj: Optional[Any] = None) -> bool:
        """Return ``True`` if ``user`` may perform ``action`` on ``obj``.

        This hook only controls UI behaviour and is not a substitute for RBAC
        checks enforced elsewhere.
        """
        return True

    # --- Assets -----------------------------------------------------------

    def collect_assets(self, md, mode: str, obj=None, request=None, fields: list[str] | None = None) -> dict:
        """Collect CSS/JS assets for all widgets used in a form.

        Returns a dict of the form ``{"css": [...], "js": [...]}`` where duplicates are
        removed while preserving the order: first any global admin assets and then the
        widget-provided ones.
        """
        fields = fields or self.get_fields(md)

        css_ordered: list[str] = list(self.admin_assets_css)
        js_ordered: list[str] = list(self.admin_assets_js)
        seen_css = set(css_ordered)
        seen_js = set(js_ordered)

        for name in fields:
            # Important: do not build the widget twice if schema generation already did it.
            # The easiest approach is to collect assets in the same loop where
            # ``w.get_schema()`` is called, but this helper handles the fallback case.
            w = self._build_widget(md, name, mode, obj=obj, request=request)
            assets = w.get_assets() or {}
            for href in assets.get("css", []):
                if href not in seen_css:
                    seen_css.add(href)
                    css_ordered.append(href)
            for src in assets.get("js", []):
                if src not in seen_js:
                    seen_js.add(src)
                    js_ordered.append(src)

        return {"css": css_ordered, "js": js_ordered}

    # --- queryset hooks ---------------------------------------------------

    def get_queryset(self) -> QuerySet:
        """Return base queryset for this admin."""
        qs = self.model.all()
        if not isinstance(qs, QuerySet):  # pragma: no cover - runtime safety
            raise RuntimeError("get_queryset must return QuerySet")
        return qs

    def apply_select_related(self, qs: QuerySet) -> QuerySet:
        """Apply ``select_related`` to the queryset if needed.

        Implementations should extend the automatically selected foreign
        keys from list columns rather than replace them.
        """
        qs = qs
        if not isinstance(qs, QuerySet):  # pragma: no cover - runtime safety
            raise RuntimeError("apply_select_related must return QuerySet")
        return qs

    def apply_only(self, qs: QuerySet, columns: Sequence[str], md) -> QuerySet:
        """Apply ``only`` to the queryset when list views opt-in.

        ``columns`` contains the resolved list columns while ``md`` provides
        the model descriptor.  Subclasses may override this hook to customise
        field selection for list views.
        """
        if self.list_use_only:
            only_fields = list(columns)
            if md.pk_attr not in only_fields:
                only_fields.append(md.pk_attr)
            qs = qs.only(*only_fields)
        if not isinstance(qs, QuerySet):  # pragma: no cover - runtime safety
            raise RuntimeError("apply_only must return QuerySet")
        return qs

    def get_autocomplete_queryset(
        self, fd, q: str, *, search_fields: list[str]
    ) -> QuerySet:
        """Return queryset for relation field autocomplete.

        Default implementation searches ``search_fields`` of the related model
        for the substring ``q``.
        """

        if hasattr(Tortoise, "get_model"):
            rel_model = Tortoise.get_model(fd.relation.target)
        else:  # pragma: no cover - older Tortoise versions
            app_label, model_name = fd.relation.target.rsplit(".", 1)
            rel_model = Tortoise.apps.get(app_label, {}).get(model_name)
        qs = rel_model.all()
        if q and search_fields:
            filters = {f"{sf}__icontains": q for sf in search_fields}
            cond = None
            for k, v in filters.items():
                q_obj = Q(**{k: v})
                cond = q_obj if cond is None else (cond | q_obj)
            if cond is not None:
                qs = qs.filter(cond)
        if not isinstance(qs, QuerySet):  # pragma: no cover - runtime safety
            raise RuntimeError("get_autocomplete_queryset must return QuerySet")
        return qs

    def apply_row_level_security(self, qs: QuerySet, user: Any) -> QuerySet:
        """Apply row level security constraints for ``user``.

        Called by all read and edit operations to ensure consistent access
        control.
        """
        qs = qs
        if not isinstance(qs, QuerySet):  # pragma: no cover - runtime safety
            raise RuntimeError("apply_row_level_security must return QuerySet")
        return qs

    def get_objects(self, request: Any, user: Any) -> QuerySet:
        """Return queryset used for retrieving objects.

        Row-level security is enforced via :meth:`apply_row_level_security`.
        """
        qs = self.get_queryset()
        qs = self.apply_select_related(qs)
        qs = self.apply_row_level_security(qs, user)
        if not isinstance(qs, QuerySet):  # pragma: no cover - runtime safety
            raise RuntimeError("get_objects must return QuerySet")
        return qs

    def handle_integrity_error(self, exc: IntegrityError) -> None:
        """Handle ``IntegrityError`` raised during save operations.

        Subclasses may override this to provide custom responses.
        """
        raise HTTPException(status_code=400, detail="Integrity error.")
    
    def get_fields(self, md) -> list[str]:
        """Return field names for the admin form.

        If ``self.fields`` is specified, return it as a list. Otherwise,
        build the list from the model's field descriptors and exclude
        ``"id"`` and the primary key attribute. If descriptors are not
        available, fall back to ``md.fields_map`` when provided.
        """

        if self.fields is not None:
            return list(self.fields)

        pk_name = getattr(md, "pk_attr", None)
        excluded = {"id", pk_name}

        descriptors = getattr(md, "fields", []) or []
        fields_map = getattr(md, "fields_map", None) or {}

        # Preserve the declaration order from descriptors if available,
        # falling back to ``fields_map`` which mirrors the ORM's ``fields_map``.
        names: list[str] = []
        for fd in descriptors:
            try:
                name = fd.name
            except AttributeError:
                name = fd
            if name not in names:
                names.append(name)
        if not names:
            names = list(fields_map.keys())

        # Remove excluded fields while preserving order.
        ordered: list[str] = []
        for name in names:
            if name in excluded:
                continue
            ordered.append(name)

        # Append any extra fields from fields_map that weren't already listed
        # in descriptors while preserving original order.
        for name in fields_map.keys():
            if name in excluded or name in ordered:
                continue
            ordered.append(name)

        # Avoid duplicate ``<field>`` and ``<field>_id`` entries for foreign keys.
        cleaned: list[str] = []
        for name in ordered:
            if name.endswith("_id") and name[:-3] in ordered:
                continue
            cleaned.append(name)
        return cleaned

    def get_fieldsets(self, md) -> tuple[tuple[str, dict[str, Any]], ...]:
        """Return configured fieldsets for the admin form."""

        if self.fieldsets is not None:
            return self.fieldsets

        return (("Main", {"fields": self.get_fields(md)}),)

    # --- minimal public API -------------------------------------------------

    def _resolve_widget_key(self, fd, field_name: str) -> str:
        if field_name in (getattr(self, "widgets_overrides", {}) or {}):
            return self.widgets_overrides[field_name]
        meta = getattr(fd, "meta", None) or {}
        if "widget" in meta:
            return str(meta["widget"])
        return widget_registry.resolve_for_field(fd)
    
    def _build_widget(
        self,
        md,
        name: str,
        mode: str,
        obj=None,
        request=None,
    ) -> BaseWidget:
        fd = md.fields_map[name]
        key = self._resolve_widget_key(fd, name)  # <-- single source of truth
        cls = widget_registry.get(key)
        if cls is None:
            model_name = getattr(md, "name", str(md))
            raise RuntimeError(
                f"No widget registered for key '{key}' "
                f"(field='{name}', model='{model_name}')"
            )
        ctx = WidgetContext(
            admin=self,
            descriptor=md,
            field=fd,
            name=name,
            instance=obj,
            mode=mode,
            request=request,
            readonly=self.is_field_readonly(md, name, mode, obj),
        )
        return cls(ctx)

    async def get_schema(self, request, user, md, mode: str, obj=None) -> dict:
        """Assemble JSON ``schema`` and ``startval`` for the form."""

        field_names: tuple[str, ...] = tuple(self.get_fields(md))

        properties: dict = {}
        required: list[str] = []
        startval: dict = {}

        for name in field_names:
            w = self._build_widget(md, name, mode, obj=obj, request=request)

            pf = getattr(w, "prefetch", None)
            if callable(pf):
                import inspect  # noqa: F401
                import asyncio  # noqa: F401
                if inspect.iscoroutinefunction(pf):
                    await pf()

            properties[name] = w.get_schema()
            if getattr(md.fields_map[name], "required", False) and not w.ctx.readonly:
                required.append(name)

            sv = w.get_startval()
            if sv is not None:
                try:
                    sv = w.to_storage(sv)
                except Exception:
                    pass
                startval[name] = sv
            else:
                fd = md.fields_map.get(name)
                rel = getattr(fd, "relation", None) if fd else None
                is_many = bool(
                    getattr(fd, "many", False)
                    or (rel and getattr(rel, "kind", "") == "m2m")
                )
                if mode in ("add", "edit"):
                    default = getattr(fd, "default", None) if fd else None
                    if is_many:
                        sv = default if default is not None else []
                    else:
                        sv = default if default is not None else ""
                    try:
                        sv = w.to_storage(sv)
                    except Exception:
                        pass
                    startval[name] = sv

        schema = {
            "type": "object",
            "properties": properties,
            "required": required,
            "defaultProperties": list(field_names),
        }

        return {"schema": schema, "startval": startval}

    def clean(
        self, payload: Dict[str, Any], *, for_update: bool = False
    ) -> Tuple[Dict[str, Any], List[Tuple[str, Iterable[Any] | None]]]:
        """Normalize ``payload`` for create or update operations.

        Returns a tuple ``(data, m2m_ops)`` where ``data`` contains direct
        assignments (including foreign keys expressed as ``<name>_id``) and
        ``m2m_ops`` is a list of many‑to‑many operations to perform after the
        instance is saved.  ``for_update`` controls how missing M2M keys are
        treated.  Subclasses may override this hook to perform custom
        validation or transformation and may raise
        :class:`fastapi.HTTPException` with ``status_code=422`` when
        validation fails.
        """

        md = self.model._meta
        readonly = {name for name in md.fields_map if self.is_field_readonly(md, name, "edit")}
        hidden = set(getattr(self, "hidden_fields", []) or [])
        blocked = readonly | hidden

        data: Dict[str, Any] = {}
        m2m_ops: List[Tuple[str, Iterable[Any] | None]] = []
        for name, fd in md.fields_map.items():
            if getattr(fd, "pk", False) or name in blocked:
                continue
            if isinstance(fd, ManyToManyFieldInstance):
                ids = payload.get(name, None if for_update else [])
                if ids is None:
                    if for_update:
                        m2m_ops.append((name, None))
                        continue
                    ids = []
                if not isinstance(ids, (list, tuple)):
                    ids = [ids]  # normalize str or single value
                m2m_ops.append((name, ids))
                continue
            if isinstance(fd, ForeignKeyFieldInstance):
                data[f"{name}_id"] = payload.get(name, None)
                continue
            if name in payload:
                val = payload[name]
                if (
                    val == ""
                    and (
                        getattr(fd, "nullable", False)
                        or getattr(fd, "null", False)
                    )
                    and isinstance(fd, (tfields.CharField, tfields.TextField))
                ):
                    val = None
                data[name] = val
        return data, m2m_ops

    async def create(
        self,
        request: Any,
        user: Any,
        md,
        payload: Dict[str, Any],
    ) -> Any:
        """Create a new model instance from ``payload``.

        ``request``, ``user`` and ``md`` are passed for symmetry with
        :meth:`update` and allow subclasses to take them into account.
        Foreign keys and many‑to‑many relations are handled automatically.
        Subclasses may override this to implement custom create behaviour.
        """

        data, m2m_ops = self.clean(payload, for_update=False)
        obj = await self.model.create(**data)
        for fname, ids in m2m_ops:
            if ids is None:
                continue
            await obj.fetch_related(fname)
            manager = getattr(obj, fname)
            await manager.clear()
            if ids:
                model_cls = manager.remote_model
                pk_attr = model_cls._meta.pk_attr
                related = await model_cls.filter(**{f"{pk_attr}__in": ids})
                await manager.add(*related)
        return obj

    async def update(
        self,
        request: Any,
        user: Any,
        md,
        obj: Any,
        payload: Dict[str, Any],
    ) -> Any:
        """Update ``obj`` using ``payload``.

        Cleaned values are applied, the instance is saved and many‑to‑many
        relations updated.  Subclasses may override to hook into the update
        cycle.
        """

        data, m2m_ops = self.clean(payload, for_update=True)
        for key, val in data.items():
            setattr(obj, key, val)
        if data:
            await obj.save(update_fields=list(data.keys()))
        for fname, ids in m2m_ops:
            if ids is None:
                continue
            await obj.fetch_related(fname)
            manager = getattr(obj, fname)
            await manager.clear()
            if ids:
                model_cls = manager.remote_model
                pk_attr = model_cls._meta.pk_attr
                related = await model_cls.filter(**{f"{pk_attr}__in": ids})
                await manager.add(*related)
        return obj

    def get_list_columns(self, md) -> Sequence[str]:
        """Return column names used by list views.

        Defaults to :meth:`get_list_display` or the model's primary key.  Override
        this to supply custom dynamic column sets.
        """

        cols = list(self.get_list_display())
        if not cols:
            cols = [md.pk_attr]
        return cols

    def get_search_fields(self, md) -> list[str]:
        """Return field names used for text search in list views.

        If ``self.search_fields`` is explicitly configured, it is returned
        as a list. Otherwise the model's fields are inspected and only
        ``TextField`` and ``CharField`` types are included.
        """

        if self.search_fields:
            return list(self.search_fields)

        fd_map = getattr(md, "fields_map", {}) or {}
        result: list[str] = []
        for name in self.get_fields(md):
            fd = fd_map.get(name)
            if not fd:
                continue
            kind = getattr(fd, "kind", None)
            if kind is not None:
                if kind in {"text", "string"} and not getattr(fd, "choices", None):
                    result.append(name)
            elif (
                isinstance(fd, (tfields.TextField, tfields.CharField))
                and not getattr(fd, "choices", None)
                and getattr(fd, "enum_type", None) is None
            ):
                result.append(name)
        return result

    def get_list_filters(self, md) -> List[Dict[str, Any]]:
        """Return filter specifications based on ``get_list_filter``.

        Each specification contains ``name``, ``label``, ``kind`` and allowed
        operations ``ops``. Choice fields include a ``choices`` list.
        """

        specs: List[Dict[str, Any]] = []
        list_filter = self.get_list_filter()
        if not list_filter:
            return specs

        fields = getattr(md, "fields", {}) or {}
        for item in list_filter:
            fname = item if isinstance(item, str) else None
            if not fname:
                continue
            fd = None
            if isinstance(fields, dict):
                fd = fields.get(fname)
            else:
                for f in fields:
                    if getattr(f, "name", None) == fname:
                        fd = f
                        break
            if fd is None:
                continue

            kind = getattr(fd, "kind", "")
            label = getattr(fd, "verbose_name", fname.replace("_", " ").title())

            if kind == "integer":
                kind = "number"
            if getattr(fd, "choices", None):
                kind = "choice"

            if kind == "string":
                ops = ["eq", "icontains", "in"]
            elif kind == "boolean":
                ops = ["eq"]
            elif kind == "number":
                ops = ["eq", "gte", "lte", "gt", "lt", "in"]
            elif kind in {"date", "datetime"}:
                ops = ["gte", "lte", "gt", "lt"]
            elif kind == "choice":
                ops = ["eq", "in"]
            else:
                ops = ["eq"]

            spec: Dict[str, Any] = {
                "name": fname,
                "label": label,
                "kind": kind,
                "ops": ops,
            }
            if kind == "choice":
                spec["choices"] = [
                    {"value": v, "label": str(lbl)}
                    for v, lbl in getattr(fd, "choices", [])
                ]
            specs.append(spec)
        return specs

    def parse_filters(self, params, md):
        """
        Parse query parameters like ``filter.<field>[__op]=value`` into a list of
        ``(field, op, coerced_value)`` tuples.
        ``md``: model descriptor (fields with types), see adapter.
        """
        filters = []
        for key, raw in params.items():
            if not key.startswith("filter."):
                continue
            frag = key[7:]
            if "__" in frag:
                fname, op = frag.split("__", 1)
            else:
                fname, op = frag, ""
            fd = None
            if hasattr(md, "fields"):
                try:
                    fd = md.fields.get(fname)
                except AttributeError:
                    for f in md.fields or []:
                        if getattr(f, "name", None) == fname:
                            fd = f
                            break
            if fd is None:
                fd = getattr(md, "fields_map", {}).get(fname)
            if fd is None:
                continue
            op = self.FILTER_OPS.get(op, "eq")
            val = self._coerce_value_for_filter(fd, raw, op)
            raw_txt = str(raw).strip().lower()
            if (val is not None) or (op == "eq" and raw_txt == "null"):
                filters.append((fname, op, val))
        return filters

    def _coerce_value_for_filter(self, fd, raw, op):
        """
        Coerce a filter value according to the field descriptor
        (``fd.kind``: 'string'|'integer'|'number'|'boolean'|'datetime'|'date', etc.).
        """
        txt = str(raw).strip()

        if op == "in":
            items = [x.strip() for x in txt.split(",") if x.strip() != ""]
            if getattr(fd, "kind", "") == "integer":
                return [int(x) for x in items]
            if getattr(fd, "kind", "") == "number":
                return [float(x) for x in items]
            if getattr(fd, "kind", "") == "boolean":
                return [x.lower() in {"1", "true", "yes", "on"} for x in items]
            return items

        kind = getattr(fd, "kind", "")

        if kind == "boolean":
            return txt.lower() in {"1", "true", "yes", "on"}

        if kind == "integer":
            try:
                return int(txt)
            except ValueError:
                return None
        if kind == "number":
            try:
                return float(txt)
            except ValueError:
                return None

        if kind in {"datetime", "date"}:
            return txt

        return txt

    def apply_filters_to_queryset(self, qs, flist):
        """
        Apply a list of filters to a ``QuerySet`` (Tortoise ORM).
        """
        for fname, op, val in flist:
            if op == "eq":
                if isinstance(val, str) and val.lower() == "null":
                    qs = qs.filter(**{f"{fname}__isnull": True})
                else:
                    qs = qs.filter(**{fname: val})
            elif op == "icontains":
                qs = qs.filter(**{f"{fname}__icontains": val})
            elif op == "gte":
                qs = qs.filter(**{f"{fname}__gte": val})
            elif op == "lte":
                qs = qs.filter(**{f"{fname}__lte": val})
            elif op == "gt":
                qs = qs.filter(**{f"{fname}__gt": val})
            elif op == "lt":
                qs = qs.filter(**{f"{fname}__lt": val})
            elif op == "in":
                qs = qs.filter(**{f"{fname}__in": val})
        return qs

    def get_list_queryset(self, request, user, md, params: Dict[str, Any]) -> QuerySet:
        """Construct the queryset for list views.

        Applies searching, filtering and ordering. Row-level security is always
        enforced via :meth:`apply_row_level_security`. Foreign keys present in
        the list columns are eagerly loaded with ``select_related``. Subclasses
        may override to inject additional constraints.
        """

        search = params.get("search", "") or ""
        order = params.get("order", "")

        qs = self.get_queryset()
        qs = self.apply_row_level_security(qs, user)
        flist = self.parse_filters(getattr(request, "query_params", {}), md)
        qs = self.apply_filters_to_queryset(qs, flist)

        search_fields = self.get_search_fields(md)
        if search and search_fields:
            cond = None
            for sf in search_fields:
                lookup = f"{sf}__icontains"
                q_obj = Q(**{lookup: search})
                cond = q_obj if cond is None else (cond | q_obj)
            if cond is not None:
                qs = qs.filter(cond)

        if not order:
            ordering = self.get_ordering()
            if ordering:
                order = ordering[0]
            else:
                order = f"-{md.pk_attr}"

        columns = self.get_list_columns(md)
        sortable_keys = {c["key"] for c in self.columns_meta(md, columns) if c["sortable"]}
        ord_field = order[1:] if order.startswith("-") else order
        if ord_field not in sortable_keys:
            order = f"-{md.pk_attr}"
        qs = qs.order_by(order)
        params["order"] = order

        fk_to_select: List[str] = []
        fd_map = getattr(md, "fields_map", {})
        for col in columns:
            fd = fd_map.get(col)
            if fd and fd.relation and fd.relation.kind == "fk":
                fk_to_select.append(col)
        qs = self.apply_select_related(qs)
        # ``fk_to_select`` is appended after ``apply_select_related``
        if fk_to_select:
            qs = qs.select_related(*fk_to_select)

        qs = self.apply_only(qs, columns, md)
        if not isinstance(qs, QuerySet):  # pragma: no cover - runtime safety
            raise RuntimeError("get_list_queryset must return QuerySet")
        return qs


    async def serialize_list_row(self, obj: Any, md, columns: Sequence[str]) -> Dict[str, Any]:
        """Serialize ``obj`` for list output.

        Handles foreign keys and many‑to‑many values.  Override to customise
        serialization for list rows.
        """

        fd_map = getattr(md, "fields_map", {})
        row: Dict[str, Any] = {md.pk_attr: getattr(obj, md.pk_attr)}
        for col in columns:
            fd = fd_map.get(col)
            val = getattr(obj, col, None)
            if fd and fd.relation:
                try:
                    if fd.relation.kind == "fk":
                        rel_obj = getattr(obj, col)
                        row[col] = str(rel_obj) if rel_obj is not None else None
                    elif fd.relation.kind == "m2m":
                        try:
                            cnt = await getattr(obj, col).count()
                            row[col] = f"{cnt} items"
                        except Exception:
                            row[col] = None
                except Exception:
                    row[col] = None
            else:
                if val is not None and hasattr(val, "isoformat"):
                    row[col] = val.isoformat()
                else:
                    row[col] = val
        return row

    def columns_meta(self, md, columns: Sequence[str]) -> List[Dict[str, Any]]:
        """Return metadata for list ``columns``.

        Metadata describes labels, data types and sorting capabilities.  This
        method provides sensible defaults and may be overridden for custom
        column descriptions.
        """

        fd_map = getattr(md, "fields_map", {})

        def _col_type(fd) -> str:
            if not fd:
                return "string"
            if fd.relation:
                return "relation"
            if fd.choices:
                return "choice"
            if fd.kind in {"integer", "bigint", "float", "decimal"}:
                return "number"
            if fd.kind == "boolean":
                return "boolean"
            if fd.kind in {"date", "datetime"}:
                return "datetime"
            return "string"

        meta: List[Dict[str, Any]] = []
        for col in columns:
            fd = fd_map.get(col)
            entry = {
                "key": col,
                "label": getattr(fd, "verbose_name", None)
                or col.replace("_", " ").title(),
                "type": _col_type(fd),
                "sortable": False
                if fd is None or (fd.relation and fd.relation.kind == "m2m")
                else True,
            }
            if fd and getattr(fd, "choices", None):
                ch_map = {}
                for ch in fd.choices:
                    try:
                        key, label = ch
                    except Exception:
                        key = getattr(ch, "value", ch)
                        label = getattr(ch, "label", str(ch))
                    ch_map[str(key)] = str(label)
                entry["choices_map"] = ch_map
            meta.append(entry)
        return meta

# The End
