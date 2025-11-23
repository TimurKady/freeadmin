# Core Concepts and Terminology

Before extending FreeAdmin it helps to understand the main services, registries, and data structures that appear throughout the code base. The sections below summarise the pieces you will interact with most frequently when wiring the admin into a FastAPI project.


## AdminSite and AdminHub

The **AdminSite** is the central registry. It stores model admins, custom views, dashboard cards, and menu entries. The site instance is created by the **AdminHub**, which also performs package discovery.

In day-to-day code you import the shared instance from `freeadmin.core.runtime.hub`:

```python
from freeadmin.core.runtime.hub import admin_site
from freeadmin.core.interface.models import ModelAdmin
from .models import Product


class ProductAdmin(ModelAdmin):
    """Configure list display, filters, and widgets for Product."""

    list_display = ("name", "price", "available")
    search_fields = ("name",)


admin_site.register(app="catalogue", model=Product, admin_cls=ProductAdmin)
```

The hub also exposes `hub.autodiscover([...])` for manual discovery, although most projects rely on `BootManager` to call it automatically during application start-up.


## ModelAdmin

A **ModelAdmin** describes how a model is displayed and edited. Subclasses inherit from `freeadmin.core.interface.models.ModelAdmin` and define declarative attributes:

* `list_display`, `search_fields`, and `ordering` control list views.
* `fields`, `readonly_fields`, and `widgets_overrides` customise the edit form.
* `actions` lists classes derived from `BaseAction` that are available on the changelist page.

Model admins never execute ORM operations directly. Instead they delegate persistence to the active adapter supplied by the admin site.


## InlineModelAdmin

`InlineModelAdmin` classes describe related objects that appear on a parent form. They inherit from `freeadmin.core.interface.inline.InlineModelAdmin` and define:

* `model`: the related model class handled by the inline.
* `parent_fk_name`: the foreign key on the inline that points to the parent object.
* `display`: either `"tabular"` or `"stacked"`.

Once declared, include the inline class in the parent `ModelAdmin.inlines` tuple. The admin site will render the inline editor automatically and reuse the parent permissions for add/change/delete operations.


## Adapter

An **adapter** bridges the admin runtime and the persistence layer. All adapters derive from `freeadmin.contrib.adapters.base.BaseAdapter`. The built-in adapter targets **Tortoise ORM** and ships with models for authentication (`AdminUser`) and content types (`AdminContentType`).

Key responsibilities:

* Provide queryset helpers such as `all()`, `filter()`, `count()`, and `order_by()`.
* Create, update, and delete model instances in an async-friendly fashion.
* Expose metadata through `get_model_descriptor()` so the admin site can build forms and tables.

You can implement a custom adapter by subclassing `BaseAdapter` and registering it via `freeadmin.contrib.adapters.registry.register("name", adapter_instance)`.


## BootManager and FastAPI integration

`BootManager` (`freeadmin.core.boot`) is the entry point used by FastAPI applications. It performs three tasks:

1. Loads the configured adapter and any bundled models.
2. Adds middleware such as the admin guard and session management.
3. Runs discovery, mounts the admin router, and schedules startup/shutdown hooks.

Typical usage:

```python
from fastapi import FastAPI
from freeadmin.core.boot import BootManager


app = FastAPI()
boot = BootManager(adapter_name="tortoise")
boot.init(app, packages=["my_project.apps"])
```

This snippet initialises the adapter, discovers admin registrations inside `my_project.apps`, and mounts the admin interface at the path configured in `FreeAdminSettings.admin_path` (default `/admin`).


## AdminRouter

`AdminRouter` mounts the admin application onto FastAPI. You rarely instantiate it manually because `BootManager.init()` performs the work, but the class is available if you need full control over the mounting process or want to embed the admin site inside another ASGI application. The router is a lightweight wrapper around `RouterAggregator`, exposing the cached aggregator via `.aggregator` for advanced scenarios where you need to add extra routers or inspect the mounted state.


## Cards

A **card** is a dashboard widget backed by templates and optional server-sent-event publishers. Register cards with `admin_site.register_card(...)`. Cards can stream live updates by registering a publisher through `admin_site.cards.register_publisher(publisher_instance)`.

```python
from freeadmin.core.runtime.hub import admin_site

admin_site.register_card(
    key="orders-today",
    app="sales",
    title="Orders today",
    template="cards/orders_today.html",
    icon="bi-receipt",
    channel="sales:orders",
)
```

When the FastAPI app starts, publishers registered on the card manager begin broadcasting updates to connected clients.


### Publishers

Cards stream live data through subclasses of `freeadmin.core.interface.sse.publisher.PublisherService`. A publisher attaches to a card key
, fetches fresh state, and calls `publish()` whenever a new payload is available.

```python
import asyncio
from collections.abc import Awaitable, Callable

from freeadmin.core.interface.sse.publisher import PublisherService
from freeadmin.core.runtime.hub import admin_site


class OrdersPublisher(PublisherService):
    """Push hourly order totals to the dashboard."""

    card_key = "orders-today"

    def __init__(self, fetch_totals: Callable[[], Awaitable[dict[str, int]]]) -> None:
        super().__init__()
        self._fetch_totals = fetch_totals

    async def run(self) -> None:
        while True:
            payload = await self._fetch_totals()
            self.publish(payload)
            await asyncio.sleep(300)


async def fetch_totals() -> dict[str, int]:
    # Query your persistence layer for the latest numbers.
    return {"orders": 42}


admin_site.cards.register_publisher(OrdersPublisher(fetch_totals))
```

Publishers are started automatically during FastAPI startup after cards are registered and remain active until application shutd
own.


## Views

Custom admin pages are registered with `admin_site.register_view()`, which acts as a decorator over an async callable. The decorated function receives the `Request` object and the authenticated `AdminUserDTO`.

```python
from typing import Any
from fastapi import Request
from freeadmin.core.runtime.hub import admin_site


@admin_site.register_view(path="/reports/export", name="Exports", icon="bi-download", label="Reports")
async def export_report(request: Request, user: Any) -> dict[str, Any]:
    return {
        "page_message": "Start a new export run from this screen.",
        "card_entries": [],
        "assets": {"css": (), "js": ()},
    }
```

The returned dictionary feeds the Jinja2 template responsible for rendering the page.


## Actions

Actions are operations that run on selected rows from the changelist. They inherit from `freeadmin.core.interface.actions.BaseAction` (or one of the bundled subclasses) and implement an async `run()` method.

```python
from freeadmin.core.interface.actions import BaseAction, ActionResult


class MarkFeaturedAction(BaseAction):
    """Flag selected products as featured."""

    name = "mark_featured"
    label = "Mark as featured"

    async def run(self, qs, params, user):
        count = await qs.update(featured=True)
        return ActionResult(success=True, message=f"Updated {count} products.")
```

Add the class to a `ModelAdmin.actions` tuple to expose it in the UI.


## Widgets

Widgets are frontend components referenced from `ModelAdmin.widgets_overrides` or declared on the `Meta.widgets` attribute. FreeAdmin bundles several JavaScript libraries under `freeadmin/static/vendors/`, including **Choices.js**, **JSONEditor**, **Select2**, and **JSBarcode**. These widgets are instantiated automatically based on the metadata returned by admin classes.


## Settings

Global configuration lives inside `freeadmin.config.FreeAdminSettings`. Instances are normally created with `FreeAdminSettings.from_env()`, which reads environment variables prefixed with `FA_`.

Important attributes include:

* `admin_path`: the URL prefix where the admin is mounted (default `/admin`).
* `session_secret` and `csrf_secret`: keys used for securing sessions and forms.
* `event_cache_path`: storage location for card payload caching.
* `brand_icon` and `admin_site_title`: values shown in the UI.

To override defaults in code, call `freeadmin.config.configure(settings_instance)` before initialising the boot manager.


## Key takeaway

FreeAdmin separates the **definition** of your admin (ModelAdmin, cards, views) from the **execution** (adapters, boot manager, router) and the **presentation** (Jinja2 templates and JavaScript widgets). By keeping each layer focused, the project remains easy to extend while still providing a ready-to-use administration panel for FastAPI and Tortoise ORM applications.
