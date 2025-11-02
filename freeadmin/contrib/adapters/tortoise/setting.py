# -*- coding: utf-8 -*-
"""
setting

System settings stored in the database.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from tortoise import fields
from tortoise.models import Model
from typing import Any
import json

from ....models.choices import StrChoices


class SettingValueType(StrChoices):
    """Supported data types for ``SystemSetting.value``."""

    STRING = "string", "String"
    INTEGER = "int", "Integer"
    FLOAT = "float", "Float"
    BOOLEAN = "bool", "Boolean"
    JSON = "json", "JSON"


class SystemSetting(Model):
    """A single persisted system configuration value."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=150)
    key = fields.CharField(max_length=150, unique=True)
    class SettingJSONField(fields.JSONField):
        """JSON field that accepts plain strings."""

        def to_python_value(self, value: Any) -> Any:  # pragma: no cover - wrapper
            if isinstance(value, str):
                try:
                    return self.decoder(value)
                except Exception:
                    return value
            return super().to_python_value(value)

        def to_db_value(self, value: Any, instance: type[Model] | Model) -> str | None:  # pragma: no cover - wrapper
            if isinstance(value, str):
                return json.dumps(value)
            return super().to_db_value(value, instance)

    value = SettingJSONField()
    value_type = fields.CharEnumField(SettingValueType)
    meta = fields.JSONField(null=True)

    class Meta:
        table = "admin_system_settings"
        indexes = ("key",)

    def __str__(self) -> str:  # pragma: no cover - simple repr
        return f"{self.key}={self.value!r}"

# The End

