# Adapter Management

Adapters act as a bridge between the admin interface and the underlying database layer. They expose a small, object-oriented API that allows the admin to remain storage agnostic.

## Available adapters

| Name    | Target ORM  | Notes                                             |
|---------|-------------|---------------------------------------------------|
| default | Example ORM | Bundled adapter providing full schema sync support |

## Usage

An adapter is selected during boot when initializing the admin application. The chosen adapter prepares database connections and applies any configuration hooks.

See the [Admin Boot Process](boot.md#adapter-selection) for details on how the adapter is initialized.

## Building a custom adapter

```python
from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    @abstractmethod
    async def setup(self, app):
        """Prepare the ORM and install hooks."""
        raise NotImplementedError

class CustomAdapter(BaseAdapter):
    async def setup(self, app):
        ...
```

## ORM Adapter Protocol Overview
The admin panel interacts with the database exclusively through an adapter object.
This adapter encapsulates ORM-specific operations behind a shared interface, letting you swap Tortoise, SQLAlchemy, or any other ORM without touching the rest of the admin code.

### Loading an Adapter
The recommended entry point for adapter access is the :class:`~freeadmin.core.boot.BootManager`
instance coordinating your application boot. Each boot manager exposes its active adapter via
``boot_manager.adapter`` and propagates that adapter into the runtime hub (``runtime_hub.admin_site.adapter``).
This keeps discovery, registration, and finalisation aligned with the adapter selected for the
current application instance—especially when custom adapters coexist alongside the bundled
defaults.

```python
from freeadmin.core.boot import BootManager

boot = BootManager(adapter_name="my_adapter")
adapter = boot.adapter
```

Avoid importing ``boot_admin`` directly when working with alternative adapters. The ``boot_admin``
singleton exists for backwards compatibility and always targets the default adapter; relying on
it will bypass any adapter registered on a custom ``BootManager``. Each adapter must provide the
same set of methods, outlined below.

### Required Interface

**Model Resolution & Query Construction**

| Method                 | Purpose                                    | Notes |
|------------------------|--------------------------------------------|-------|
| get_model(dotted: str) | Resolve "app.Model" into a model class     | sync  |
| get_pk_attr(model)     | Return primary-key attribute name          | sync  |
| all(model)             | Return queryset with all records           | sync  |
| filter(model_or_qs, *expressions, **filters) | Apply filters to a queryset | sync  |
| Q(*args, **kwargs)     | Build a composable filter expression       | sync  |

**Query Evaluation & Modification**

| Method                 | Purpose                                    | Async |
|------------------------|--------------------------------------------|-------|
| exists(qs)             | Check if queryset yields results           |  ✅  |
| count(qs)              | Count queryset rows                        |  ✅  |
| values(qs, *fields) / values_list(qs, *fields, flat=False) | Field projection	| sync |
| order_by(qs, *ordering)	Sort results	| sync |
| limit(qs, n) / offset(qs, n)	Pagination helpers	| sync |
| select_related(qs, *relations) / prefetch_related(qs, *relations)	Relation loading	| sync |
| only(qs, *fields)	Restrict columns	| sync |
| annotate(qs, **annotations) / distinct(qs, *fields)	Query augmentation	| sync |

**CRUD Operations**
| Method                        | Purpose                        | Async |
|-------------------------------|--------------------------------|-------|
| create(model, **data)         | Create a new record            |   ✅ |
| get(model_or_qs, **filters)   | Retrieve a single object       |   ✅ |
| get_or_none(model, **filters) | Retrieve or return None        |   ✅ |
| save(obj, update_fields=None) | Persist object changes         |   ✅ |
| delete(obj)                   | Remove object                  |   ✅ |
| fetch_related(obj, *fields)   | Load relations for an instance |   ✅ |

**Many-to-Many Utilities**
| Method                 | Purpose               | Async |
|------------------------|-----------------------|-------|
| m2m_clear(manager)     | Clear relation links  |   ✅  |
| m2m_add(manager, objs) | Link multiple objects |   ✅  |

These helpers abstract the underlying relation manager calls:

```python
await adapter.m2m_clear(author.books)
await adapter.m2m_add(author.books, [book1, book2])
```

**Transactions**
| Method                 | Purpose                                         |
|-------------------|------------------------------------------------------|
| in_transaction()  | Return async context manager for transactional block |

**Implementation Notes**
* **Object-Oriented**: All methods live on the adapter class; no free functions.
* **Asynchronous**: Methods that hit the database are async and must be awaited.
* **Return Types**: Keep ORM-specific types hidden; callers interact with generic models/querysets.
* **Extensibility**: When porting to a new ORM, implement the same method signatures and semantics.

Example Skeleton

```python
class MyOrmAdapter:
    def get_model(self, dotted: str):
        ...

    async def create(self, model, **data):
        ...

    async def get(self, model_or_qs, **filters):
        ...
```

Register your adapter with boot_admin at startup, and the admin panel will use it transparently.



Methods required from an ORM adapter
Based on the registry above, the adapter must abstract the following operations (listed as the adapter class interface):

Model descriptor access

get_model_descriptor(model) — already implemented for Tortoise.

get_model(dotted_name) — fetch the model class by the "app.Model" dotted path.

get_pk_attr(model) — return the primary key attribute name.

Creating and reading objects

create(model, **data)

get(model_or_qs, **filters)

get_or_none(model, **filters)

all(model) → base QuerySet

filter(qs, **filters)

exists(qs)

count(qs)

values(qs, *fields)

values_list(qs, field, flat=False)

order_by(qs, expression)

limit(qs, n) / offset(qs, n)

select_related(qs, *relations) and prefetch_related(qs, *relations)

apply_only(qs, columns) (equivalent to .only/.values)

Working with instances

save(obj, update_fields=None)

delete(obj)

fetch_related(obj, *fields)

Many-to-many relationships

m2m_clear(manager) — remove all relations.
m2m_add(manager, iterable_of_objs) — add related objects.

Auxiliary

in_transaction() — context manager for transactions.

Q-expression builder or equivalent for composing complex filters.

Implementing these methods isolates the admin code from a specific ORM and allows switching between Tortoise, SQLAlchemy, or other solutions by providing the appropriate adapter.

# The End

