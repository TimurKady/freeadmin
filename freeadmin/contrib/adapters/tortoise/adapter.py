# -*- coding: utf-8 -*-
"""
tortoise

Tortoise ORM adapter utilities.

This module defines :class:`Adapter`, a light abstraction over
Tortoise ORM that exposes common database operations through an object
oriented interface.  It allows the rest of the admin application to
interact with models without depending directly on Tortoise APIs.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from typing import Any, Iterable

from tortoise import Tortoise, connections
from tortoise import fields
from tortoise.exceptions import (
    ConfigurationError,
    DoesNotExist as TortoiseDoesNotExist,
    IntegrityError as TortoiseIntegrityError,
    MultipleObjectsReturned as TortoiseMultipleObjectsReturned,
    ParamsError,
)
from tortoise.expressions import Q as TortoiseQ
from tortoise.models import Model as TortoiseModel
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction  # noqa: F401

from ....core.schema.descriptors import (
    Choice, FieldDescriptor, ModelDescriptor, Relation
)
from .. import registry
from ....core.interface.filters import FilterSpec


Model = TortoiseModel


class Adapter:
    """Facade for Tortoise ORM providing instance-based helpers.

    All interactions are offered as instance methods to keep calling code
    decoupled from Tortoise internals while still exposing familiar query
    patterns.
    """

    name = "tortoise"
    QuerySet = QuerySet
    Model = Model
    Q = TortoiseQ
    DoesNotExist = TortoiseDoesNotExist
    IntegrityError = TortoiseIntegrityError
    MultipleObjectsReturned = TortoiseMultipleObjectsReturned
    model_modules = [
        "freeadmin.contrib.adapters.tortoise.users",
        "freeadmin.contrib.adapters.tortoise.setting",
        "freeadmin.contrib.adapters.tortoise.groups",
        "freeadmin.contrib.adapters.tortoise.content_type",
    ]

    def __init__(self) -> None:
        """Initialize the adapter and register admin models."""
        self._register_admin_models()

    def _register_admin_models(self) -> None:
        """Register admin models with Tortoise ORM under ``admin`` app."""
        Tortoise.init_models(
            [
                "freeadmin.contrib.adapters.tortoise.users",
                "freeadmin.contrib.adapters.tortoise.setting",
                "freeadmin.contrib.adapters.tortoise.groups",
                "freeadmin.contrib.adapters.tortoise.content_type",
            ],
            app_label="admin",
        )
        from .users import AdminUser, AdminUserPermission, PermAction
        from .groups import AdminGroup, AdminGroupPermission
        from .content_type import AdminContentType
        from .setting import SettingValueType, SystemSetting

        for model in [
            AdminUser,
            AdminUserPermission,
            AdminGroup,
            AdminGroupPermission,
            AdminContentType,
            SystemSetting,
        ]:
            model._meta.default_connection = "default"

        self.user_model = AdminUser
        self.user_permission_model = AdminUserPermission
        self.perm_action = PermAction
        self.group_model = AdminGroup
        self.group_permission_model = AdminGroupPermission
        self.content_type_model = AdminContentType
        self.system_setting_model = SystemSetting
        self.setting_value_type = SettingValueType

    def normalize_import_data(self, model: type[Model], data: dict[str, Any]) -> dict[str, Any]:
        """Convert raw import values into ORM-friendly types."""
        meta = getattr(model, "_meta", None)
        if not meta:
            return data
        cleaned: dict[str, Any] = {}
        for name, value in data.items():
            field = meta.fields_map.get(name)
            if not field:
                cleaned[name] = value
                continue
            if isinstance(
                field,
                (
                    fields.relational.ForeignKeyFieldInstance,
                    fields.relational.OneToOneFieldInstance,
                ),
            ):
                if getattr(value, "_saved_in_db", False):
                    cleaned[name] = value
                else:
                    cleaned[f"{name}_id"] = value
                continue
            if getattr(field, "enum_type", None) and isinstance(value, str):
                if value.isdigit():
                    cleaned[name] = int(value)
                    continue
            cleaned[name] = value
        return cleaned

    def assign(self, obj: Model, data: dict[str, Any]) -> None:
        """Set attributes on ``obj`` handling type coercion."""
        cleaned = self.normalize_import_data(type(obj), data)
        for field, value in cleaned.items():
            setattr(obj, field, value)

    def get_model(self, dotted: str) -> type[Model]:
        """Return a Tortoise model by dotted path.

        Args:
            dotted: Model path in ``app.Model`` notation.

        Returns:
            type[Model]: Resolved model class.
        """
        try:
            return Tortoise.get_model(dotted)
        except (AttributeError, KeyError, ConfigurationError):  # pragma: no cover - legacy support
            app_label, model_name = dotted.rsplit(".", 1)
            return Tortoise.apps.get(app_label, {}).get(model_name)  # type: ignore

    def get_pk_attr(self, model: type[Any]) -> str:
        """Return the primary-key attribute name for ``model``.

        Args:
            model: Model class to inspect.

        Returns:
            str: Primary-key field attribute.

        The method tolerates models without Tortoise metadata and defaults
        to ``id`` when the information is unavailable.
        """
        meta = getattr(model, "_meta", None)
        return getattr(meta, "pk_attr", "id") if meta else "id"

    def all(self, model: type[Model] | str) -> QuerySet[Model]:
        """Build a queryset for all records of ``model``.

        Args:
            model: Model class or its dotted path.

        Returns:
            QuerySet[Model]: Deferred queryset yielding every record.
        """
        model_cls = self.get_model(model) if isinstance(model, str) else model
        return model_cls.all()

    def filter(
        self,
        model: type[Model] | str,
        *expressions: TortoiseQ,
        **filters: Any,
    ) -> QuerySet[Model]:
        """Build a queryset applying Tortoise filters.

        Args:
            model: Model class or its dotted path.
            *expressions: Additional ``TortoiseQ`` expressions.
            **filters: Field lookups passed to ``filter``.

        Returns:
            QuerySet[Model]: Filtered queryset for deferred evaluation.
        """
        model_cls = self.get_model(model) if isinstance(model, str) else model
        return model_cls.filter(*expressions, **filters)

    def apply_filter_spec(
        self, qs_or_model: Any, specs: list[FilterSpec]
    ) -> QuerySet[Model]:
        """Apply ``FilterSpec`` objects to a queryset or model."""
        qs = (
            qs_or_model
            if hasattr(qs_or_model, "filter")
            else self.all(qs_or_model)
        )
        for spec in specs:
            lookup = spec.lookup()
            if spec.op == "eq":
                if isinstance(spec.value, str) and spec.value.lower() == "null":
                    qs = self.filter(qs, **{f"{lookup}__isnull": True})
                else:
                    qs = self.filter(qs, **{lookup: spec.value})
            elif spec.op == "icontains":
                qs = self.filter(qs, **{f"{lookup}__icontains": spec.value})
            elif spec.op == "gte":
                qs = self.filter(qs, **{f"{lookup}__gte": spec.value})
            elif spec.op == "lte":
                qs = self.filter(qs, **{f"{lookup}__lte": spec.value})
            elif spec.op == "gt":
                qs = self.filter(qs, **{f"{lookup}__gt": spec.value})
            elif spec.op == "lt":
                qs = self.filter(qs, **{f"{lookup}__lt": spec.value})
            elif spec.op == "in":
                qs = self.filter(qs, **{f"{lookup}__in": spec.value})
        return qs

    def _available_connection_names(self) -> list[str]:
        """Return aliases configured for active Tortoise connections."""
        try:
            db_config = connections.db_config
        except ConfigurationError:
            return []
        if isinstance(db_config, dict):
            return list(db_config.keys())
        if isinstance(db_config, Iterable):
            return list(db_config)
        return []

    def _resolve_connection_name(self) -> str:
        """Return the appropriate connection name for transactional work.

        Raises:
            ParamsError: If multiple connections exist without a clear choice.
        """
        conn_name = getattr(self, "connection_name", None)
        if conn_name:
            return conn_name
        connection_names = self._available_connection_names()
        if len(connection_names) == 1:
            return connection_names[0]
        if "default" in connection_names:
            return "default"
        if connection_names:
            raise ParamsError(
                "Adapter cannot determine which Tortoise connection to use for "
                "transactions. Provide `connection_name` or configure a 'default' "
                "connection."
            )
        return "default"

    def in_transaction(self):
        """Return Tortoise's ``in_transaction`` async context manager.

        Returns:
            context manager: Asynchronous transaction wrapper.
        """
        conn_name = self._resolve_connection_name()
        return in_transaction(conn_name)

    async def create(
        self,
        model_cls: type[Model],
        *,
        include_m2m: Iterable[str] | None = None,
        **data: Any,
    ) -> Model:
        """Create and persist a model instance.

        Args:
            model_cls: Model class to instantiate.
            include_m2m: Iterable of many-to-many field names whose values are
                provided in ``data`` and should be assigned after instance
                creation.
            **data: Field values for the new record.

        Returns:
            Model: Newly created instance.

        This coroutine must be awaited.
        """
        include_m2m = list(include_m2m or [])
        m2m_values: dict[str, list[Any]] = {}

        for fname in include_m2m:
            if fname not in data:
                continue
            value = data.pop(fname)
            if value is None:
                m2m_values[fname] = []
                continue
            if isinstance(value, (list, tuple, set)):
                m2m_values[fname] = list(value)
            else:
                m2m_values[fname] = [value]

        data = self.normalize_import_data(model_cls, data)
        obj = await model_cls.create(**data)

        for fname, values in m2m_values.items():
            manager = getattr(obj, fname)
            remote_model = manager.remote_model
            pk_attr = self.get_pk_attr(remote_model)

            normalized: list[Any] = []
            for value in values:
                if value is None:
                    continue
                if isinstance(value, remote_model):
                    normalized.append(value)
                    continue
                if isinstance(value, dict) and pk_attr in value:
                    normalized.append(value[pk_attr])
                    continue
                if isinstance(value, str) and value.isdigit():
                    normalized.append(int(value))
                    continue
                normalized.append(value)

            if normalized:
                await manager.add(*normalized)


        return obj

    async def get(
        self,
        model_or_qs: type[Model] | QuerySet[Model],
        **filters: Any,
    ) -> Model:
        """Retrieve a single model instance.

        Args:
            model_or_qs: Model class or queryset to search.
            **filters: Field lookups for ``get``.

        Returns:
            Model: Matching instance.

        This coroutine must be awaited.
        """
        return await model_or_qs.get(**filters)

    async def get_or_none(
        self,
        model: type[Model],
        **filters: Any,
    ) -> Model | None:
        """Retrieve a model instance or ``None`` if not found.

        Args:
            model: Model class to query.
            **filters: Field lookups for ``get_or_none``.

        Returns:
            Model | None: Matching instance or ``None``.

        This coroutine must be awaited.
        """
        return await model.get_or_none(**filters)

    async def exists(self, qs: QuerySet) -> bool:
        """Check whether the queryset yields any records.

        Args:
            qs: Queryset to evaluate.

        Returns:
            bool: ``True`` if at least one record exists.

        This coroutine must be awaited.
        """
        return await qs.exists()

    async def count(self, qs: QuerySet) -> int:
        """Return the number of records in the queryset.

        Args:
            qs: Queryset to evaluate.

        Returns:
            int: Total record count.

        This coroutine must be awaited.
        """
        return await qs.count()

    async def save(
        self, obj: Model, update_fields: Iterable[str] | None = None
    ) -> Model:
        """Persist changes to an object.

        Args:
            obj: Model instance to save.
            update_fields: Optional iterable of fields to update.

        Returns:
            Model: The saved object.

        This coroutine must be awaited.
        """
        await obj.save(update_fields=update_fields)
        return obj

    async def delete(self, obj: Model) -> None:
        """Remove an object from the database.

        Args:
            obj: Model instance to delete.

        This coroutine must be awaited.
        """
        await obj.delete()

    async def fetch_related(self, obj: Model, *fields: str) -> None:
        """Populate related fields on an object.

        Args:
            obj: Model instance to populate.
            *fields: Relation names to load.

        This coroutine must be awaited.
        """
        await obj.fetch_related(*fields)

    async def m2m_clear(self, manager) -> None:
        """Clear all links from a many-to-many relation manager.

        Args:
            manager: Relation manager handling the link table.

        This coroutine must be awaited.
        """
        await manager.clear()

    async def m2m_add(self, manager, objs: Iterable[Model]) -> None:
        """Add multiple objects to a many-to-many relation manager.

        Args:
            manager: Relation manager for the many-to-many field.
            objs: Iterable of model instances to attach.

        This coroutine must be awaited.
        """
        await manager.add(*objs)

    def values(self, qs: QuerySet, *fields: str) -> QuerySet:
        """Select specific fields for deferred evaluation.

        Args:
            qs: Queryset to operate on.
            *fields: Field names to include.

        Returns:
            QuerySet: Queryset yielding dictionaries of selected fields.
        """
        return qs.values(*fields)

    def values_list(
        self, qs: QuerySet, *fields: str, flat: bool = False
    ) -> QuerySet:
        """Select fields as tuples or list for deferred evaluation.

        Args:
            qs: Queryset to operate on.
            *fields: Field names to include.
            flat: Return single values instead of tuples when one field is selected.

        Returns:
            QuerySet: Queryset yielding tuples or single values.
        """
        return qs.values_list(*fields, flat=flat)

    async def fetch_all(self, qs: QuerySet) -> list[Model]:
        """Evaluate ``qs`` and return a list of model instances."""
        return await qs

    async def fetch_values(
        self, qs: QuerySet, *fields: str, flat: bool = False
    ) -> list[Any]:
        """Evaluate ``qs`` returning selected field values."""
        return await qs.values_list(*fields, flat=flat)

    def order_by(self, qs: QuerySet, *ordering: str) -> QuerySet:
        """Apply ordering to a queryset.

        Args:
            qs: Queryset to sort.
            *ordering: Field names to order by, prefix with ``-`` for descending.

        Returns:
            QuerySet: Ordered queryset.
        """
        return qs.order_by(*ordering)

    def limit(self, qs: QuerySet, limit: int) -> QuerySet:
        """Limit queryset to a maximum number of rows.

        Args:
            qs: Queryset to limit.
            limit: Maximum number of records to return.

        Returns:
            QuerySet: Limited queryset.
        """
        return qs.limit(limit)

    def offset(self, qs: QuerySet, offset: int) -> QuerySet:
        """Offset a queryset by a number of rows.

        Args:
            qs: Queryset to offset.
            offset: Number of rows to skip.

        Returns:
            QuerySet: Offset queryset.
        """
        return qs.offset(offset)

    def select_related(self, qs: QuerySet, *fields: str) -> QuerySet:
        """Eagerly load related models in a queryset.

        Args:
            qs: Queryset to operate on.
            *fields: Relation names to include.

        Returns:
            QuerySet: Queryset with relations selected.
        """
        return qs.select_related(*fields)

    def prefetch_related(self, qs: QuerySet, *fields: str) -> QuerySet:
        """Prefetch related models for later access.

        Args:
            qs: Queryset to operate on.
            *fields: Relation names to prefetch.

        Returns:
            QuerySet: Queryset with relations prefetched.
        """
        return qs.prefetch_related(*fields)

    def only(self, qs: QuerySet, *fields: str) -> QuerySet:
        """Restrict a queryset to only the given fields.

        Args:
            qs: Queryset to operate on.
            *fields: Field names to include.

        Returns:
            QuerySet: Queryset selecting only specified fields.
        """
        return qs.only(*fields)

    def annotate(self, qs: QuerySet, **annotations: Any) -> QuerySet:
        """Add computed annotations to a queryset.

        Args:
            qs: Queryset to annotate.
            **annotations: Expressions to add.

        Returns:
            QuerySet: Annotated queryset.
        """
        return qs.annotate(**annotations)

    def distinct(self, qs: QuerySet, *fields: str) -> QuerySet:
        """Ensure results are distinct for given fields.

        Args:
            qs: Queryset to operate on.
            *fields: Field names defining distinctness.

        Returns:
            QuerySet: Queryset with distinct clause applied.
        """
        return qs.distinct(*fields)

    def _app_label(self, model: type[Any]) -> str:
        """Return the app label for a model, with safe fallback."""
        meta = getattr(model, "_meta", None)
        label = getattr(meta, "app", None)
        if label in {None, "models"}:
            parts = model.__module__.split(".")
            if len(parts) > 1:
                return parts[1] if parts[0] == "apps" else parts[0]
        return label or model.__module__.split(".")[0]

    def _build_choices(self, f: fields.Field) -> list[Choice] | None:
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
                        Choice(const=pair["value"], title=str(pair["label"]))
                    )
            return out or None
        return None

    def _kind_for_field(self, f: fields.Field) -> str:
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
        file_field = getattr(fields, "FileField", None)
        if file_field and isinstance(f, file_field):
            return "file"
        if isinstance(f, (fields.BinaryField,)):
            return "binary"
        if isinstance(f, (fields.TextField,)):
            return "text"
        # By default, everything else is considered string (CharField and so on)
        return "string"

    def _relation_for_field(self, f: fields.Field) -> Relation | None:
        """Return relation metadata for ``f`` if it defines FK or M2M."""
        # ForeignKey / ManyToMany
        if isinstance(f, fields.relational.ForeignKeyFieldInstance):
            target = getattr(f, "related_model", None) or getattr(
                f, "model_name", None
            )
            if target is None:
                return None
            if isinstance(target, str):
                dotted = target
                to_field = "id"
            else:
                meta = getattr(target, "_meta", None)
                app_label = getattr(meta, "app", None) if meta else None
                app_label = app_label or self._app_label(target)
                dotted = f"{app_label}.{target.__name__}"
                to_field = getattr(meta, "pk_attr", "id") if meta else "id"
            return Relation(kind="fk", target=dotted, to_field=to_field)
        if isinstance(f, fields.relational.ManyToManyFieldInstance):
            target = getattr(f, "related_model", None) or getattr(
                f, "model_name", None
            )
            if target is None:
                return None
            if isinstance(target, str):
                dotted = target
                to_field = "id"
            else:
                meta = getattr(target, "_meta", None)
                app_label = getattr(meta, "app", None) if meta else None
                app_label = app_label or self._app_label(target)
                dotted = f"{app_label}.{target.__name__}"
                to_field = getattr(meta, "pk_attr", "id") if meta else "id"
            return Relation(kind="m2m", target=dotted, to_field=to_field)
        return None

    def _field_descriptor(self, name: str, f: fields.Field) -> FieldDescriptor:
        """Build a :class:`FieldDescriptor` from a Tortoise field."""
        kind = self._kind_for_field(f)
        rel = self._relation_for_field(f)
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
            auto_now=bool(getattr(f, "auto_now", False)),
            auto_now_add=bool(getattr(f, "auto_now_add", False)),
            generated=bool(getattr(f, "generated", False)),
            max_length=getattr(f, "max_length", None),
            decimal_places=getattr(f, "decimal_places", None),
            max_digits=getattr(f, "max_digits", None),
            relation=rel,
            choices=self._build_choices(f),
        )
        return desc

    def get_model_descriptor(self, model: type[Any]) -> ModelDescriptor:
        """Build a descriptor with metadata for ``model``.

        Args:
            model: Model class to introspect.

        Returns:
            ModelDescriptor: Structured metadata describing the model.

        The adapter tolerates classes lacking Tortoise metadata by returning a
        minimal descriptor with sensible defaults.
        """
        meta = getattr(model, "_meta", None)
        app = self._app_label(model)
        dotted = f"{app}.{getattr(model, '__name__', 'Model')}"
        table_name = getattr(meta, "db_table", f"{app}_{getattr(model, '__name__', 'model').lower()}")
        fds: list[FieldDescriptor] = []
        if meta is not None:
            from tortoise import fields as tfields

            fields_map = getattr(meta, "fields_map", {})
            field_names = set(fields_map.keys())

            for name, f in fields_map.items():
                if isinstance(
                    f,
                    (
                        tfields.relational.BackwardFKRelation,
                        tfields.relational.ReverseRelation,
                    ),
                ):
                    continue

                if name.endswith("_id"):
                    base_name = name[:-3]
                    if base_name in field_names:
                        # Skip duplicate ``*_id`` entries when relation exists.
                        continue
                    if isinstance(f, tfields.relational.ForeignKeyFieldInstance):
                        name = base_name

                fds.append(self._field_descriptor(name, f))

        mds = ModelDescriptor(
            app_label=app,
            model_name=getattr(model, "__name__", "Model").lower(),
            dotted=dotted,
            table=table_name,
            pk_attr=self.get_pk_attr(model),
            fields=fds,
        )
        return mds

    def get_models_descriptors(
        self, models: Iterable[type[Model]]
    ) -> list[ModelDescriptor]:
        """Return descriptors for a collection of models.

        Args:
            models: Iterable of Tortoise model classes.

        Returns:
            list[ModelDescriptor]: Descriptors for each provided model.
        """
        return [self.get_model_descriptor(m) for m in models]


tortoise_adapter = adapter = Adapter()
registry.register(adapter)

__all__ = ["Adapter", "adapter", "tortoise_adapter", "Model"]

# The End

