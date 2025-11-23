# -*- coding: utf-8 -*-
"""
descriptors

Admin schema descriptors.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field as PField

# Unified field types forming the basis for JSON Schema
FieldKind = Literal[
    "string", "text", "integer", "bigint", "float", "decimal",
    "boolean", "date", "datetime", "uuid", "json", "file", "binary"
]


class Choice(BaseModel):
    """Single selectable option for a field with discrete choices."""
    const: Any
    title: str


class Relation(BaseModel):
    """Information about a relation to another model."""
    kind: Literal["fk", "m2m"]
    target: str  # dotted path "app.Model"
    to_field: Optional[str] = None  # usually the target model's PK


class FieldDescriptor(BaseModel):
    """Unified representation of a model field used by the admin."""
    name: str
    kind: FieldKind
    nullable: bool = False
    required: bool = False
    primary_key: bool = False
    unique: bool = False
    default: Any | None = None

    auto_now: bool = False
    auto_now_add: bool = False
    generated: bool = False

    label: str | None = None

    max_length: int | None = None
    decimal_places: int | None = None
    max_digits: int | None = None

    relation: Relation | None = None
    choices: list[Choice] | None = None


class ModelDescriptor(BaseModel):
    """Metadata describing an ORM model for the admin interface."""
    app_label: str
    model_name: str
    dotted: str
    table: str
    pk_attr: str

    fields: list[FieldDescriptor] = PField(default_factory=list)

    def field(self, name: str) -> FieldDescriptor | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    @property
    def fields_map(self) -> dict[str, FieldDescriptor]:
        """Return a mapping of field names to descriptors.

        Older parts of the admin code expect ``ModelDescriptor`` instances to
        expose a ``fields_map`` attribute similar to Tortoise's ``_meta``.
        Providing it here preserves that behaviour and avoids attribute errors
        when the descriptor is used interchangeably with the ORM's metadata.
        """
        return {f.name: f for f in self.fields}

# The End

