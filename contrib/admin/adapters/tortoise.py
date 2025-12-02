# -*- coding: utf-8 -*-
"""
tortoise

Tortoise ORM adapter utilities.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Iterable

from tortoise import fields
from tortoise.models import Model

from ..schema.descriptors import (
    Choice, FieldDescriptor, ModelDescriptor, Relation
)

# === helpers ===


def _app_label(model: type[Model]) -> str:
    """Return the app label for a Tortoise model."""
    # Tortoise stores app in _meta.app; fallback — from the module
    return getattr(model._meta, "app", None) or model.__module__.split(".")[0]


def _build_choices(f: fields.Field) -> list[Choice] | None:
    """Create ``Choice`` instances for enum or ``choices`` definitions."""
    # CharEnumField / IntEnumField / choices
    enum_type = getattr(f, "enum_type", None)
    if enum_type is not None:
        out: list[Choice] = []
        for m in enum_type:  # Enum
            out.append(Choice(const=m.value, title=getattr(m, "label", m.name)))
        return out
    raw_choices = getattr(f, "choices", None)
    if raw_choices:
        out = []
        for pair in raw_choices:
            # allow (value, label) or {"value":..., "label":...}
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                out.append(Choice(const=pair[0], title=str(pair[1])))
            elif isinstance(pair, dict) and "value" in pair and "label" in pair:
                out.append(
                    Choice(const=pair["value"], title=str(pair["label"])))
        return out or None
    return None


def _kind_for_field(f: fields.Field) -> str:
    """Map a Tortoise field instance to a generic field kind."""
    # Mapping to unified field types
    if isinstance(f, fields.BooleanField):
        return "boolean"
    if isinstance(f, (fields.IntField,)):
        return "integer"
    if isinstance(f, (fields.BigIntField,)):
        return "bigint"
    if isinstance(f, (fields.FloatField,)):
        return "float"
    if isinstance(f, (fields.DecimalField,)):
        return "decimal"
    if isinstance(f, (fields.DateField,)):
        return "date"
    if isinstance(f, (fields.DatetimeField,)):
        return "datetime"
    if isinstance(f, (fields.UUIDField,)):
        return "uuid"
    if isinstance(f, (fields.JSONField,)):
        return "json"
    if isinstance(f, (fields.BinaryField,)):
        return "binary"
    if isinstance(f, (fields.TextField,)):
        return "text"
    # By default, everything else is considered string (CharField and so on)
    return "string"


def _relation_for_field(f: fields.Field) -> Relation | None:
    """Return relation metadata for ``f`` if it defines FK or M2M."""
    # ForeignKey / ManyToMany
    if isinstance(f, fields.relational.ForeignKeyFieldInstance):
        target = getattr(f, "related_model", None) or getattr(f, "model_name", None)
        if target is None:
            return None
        if isinstance(target, str):
            dotted = target
            to_field = "id"
        else:
            dotted = f"{_app_label(target)}.{target.__name__}"
            to_field = getattr(target._meta, "pk_attr", "id")
        return Relation(kind="fk", target=dotted, to_field=to_field)
    if isinstance(f, fields.relational.ManyToManyFieldInstance):
        target = getattr(f, "related_model", None) or getattr(f, "model_name", None)
        if target is None:
            return None
        if isinstance(target, str):
            dotted = target
            to_field = "id"
        else:
            dotted = f"{_app_label(target)}.{target.__name__}"
            to_field = getattr(target._meta, "pk_attr", "id")
        return Relation(kind="m2m", target=dotted, to_field=to_field)
    return None


def _field_descriptor(name: str, f: fields.Field) -> FieldDescriptor:
    """Build a :class:`FieldDescriptor` from a Tortoise field."""
    kind = _kind_for_field(f)
    rel = _relation_for_field(f)
    raw_default = getattr(f, "default", None)
    default = None if callable(raw_default) else raw_default
    is_m2m = isinstance(f, fields.relational.ManyToManyFieldInstance)
    required = (
        not getattr(f, "null", False)
        and raw_default is None
        and not callable(raw_default)
        and not getattr(f, "pk", False)
        and not is_m2m
    )
    desc = FieldDescriptor(
        name=name,
        kind=kind,
        nullable=bool(getattr(f, "null", False)),
        required=required,
        primary_key=bool(getattr(f, "pk", False)),
        unique=bool(getattr(f, "unique", False)),
        default=default,
        max_length=getattr(f, "max_length", None),
        decimal_places=getattr(f, "decimal_places", None),
        max_digits=getattr(f, "max_digits", None),
        relation=rel,
        choices=_build_choices(f),
    )
    return desc


def get_model_descriptor(model: type[Model]) -> ModelDescriptor:
    meta = model._meta
    app = _app_label(model)
    dotted = f"{app}.{model.__name__}"
    table_name = getattr(meta, "db_table", f"{app}_{model.__name__.lower()}")
    fds: list[FieldDescriptor] = []
    for name, f in meta.fields_map.items():
        from tortoise import fields as tfields
        if isinstance(f, (tfields.relational.BackwardFKRelation, tfields.relational.ReverseRelation)):
            continue
        fds.append(_field_descriptor(name, f))

    mds = ModelDescriptor(
        app_label=app,
        model_name=model.__name__,
        dotted=dotted,
        table=table_name,
        pk_attr=getattr(meta, "pk_attr", "id"),
        fields=fds,
    )
    return mds


def get_models_descriptors(models: Iterable[type[Model]]) -> list[ModelDescriptor]:
    """Return descriptors for a collection of Tortoise models."""
    return [get_model_descriptor(m) for m in models]

# The End
