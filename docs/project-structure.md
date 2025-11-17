# Project structure

When you run `freeadmin init` the CLI creates a predictable tree so configuration, discovery, and application code stay organised. This document explains how each folder contributes to the runtime behaviour of FreeAdmin.


## 1. Root layout

A freshly generated project looks like this:

```
myproject/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── main.py
│   ├── orm.py
│   └── settings.py
├── apps/
├── pages/
├── static/
├── templates/
└── README.md
```

Only `config/` contains executable code out of the box. Everything else is ready for you to populate with domain-specific logic, assets, or documentation.


## 2. Configuration package (`config/`)

The `config` package defines how the admin integrates with your FastAPI application and database. The CLI writes minimal placeholders that you are expected to customise:

| File | Purpose |
| ---- | ------- |
| `main.py` | Creates the FastAPI app and should call `BootManager.init()` to mount FreeAdmin. |
| `orm.py` | Declares adapter constants and exports an `ORMConfig` instance with lifecycle helpers. |
| `settings.py` | Declares the `ProjectSettings` model backed by `pydantic_settings.BaseSettings`. |

After customisation a typical `main.py` instantiates the generated `ApplicationFactory`, which in turn coordinates `BootManager` and the ORM lifecycle:

```python
from collections.abc import Iterable
from typing import List

from fastapi import FastAPI

from freeadmin.core.boot import BootManager
from freeadmin.core.orm import ORMConfig

from config.orm import ORM
from config.settings import ProjectSettings


class ApplicationFactory:
    """Create FastAPI applications for the project."""

    def __init__(
        self,
        *,
        settings: ProjectSettings | None = None,
        orm: ORMConfig | None = None,
        packages: Iterable[str] | None = None,
    ) -> None:
        self._settings = settings or ProjectSettings()
        self._orm = orm or ORM
        self._orm_lifecycle = self._orm.create_lifecycle()
        self._boot = BootManager(adapter_name=self._orm_lifecycle.adapter_name)
        self._app = FastAPI(title=self._settings.project_title)
        self._packages: List[str] = list(packages or ["apps", "pages"])
        self._orm_events_bound = False

    def build(self) -> FastAPI:
        """Return a FastAPI instance wired with FreeAdmin integration."""

        if not self._orm_events_bound:
            self._orm_lifecycle.bind(self._app)
            self._orm_events_bound = True
        self._boot.init(
            self._app,
            adapter=self._orm_lifecycle.adapter_name,
            packages=self._packages,
        )
        return self._app


app = ApplicationFactory().build()
```

`BootManager.init()` wires the admin router, session middleware, and card publishers into the FastAPI application. The list of packages controls autodiscovery: every package listed is scanned for admin registrations. `config/orm.py` complements this by exposing a ready-to-use `ORMConfig` instance whose `.create_lifecycle()` method binds startup and shutdown handlers to the FastAPI instance.


## 3. Application packages (`apps/<name>/`)

Each folder inside `apps/` represents a logical component of your system. The CLI scaffolder creates empty modules so you can decide how to organise the code:

| File        | Typical contents |
| ----------- | ---------------- |
| `app.py`    | `AppConfig` subclass for startup hooks. |
| `models.py` | Tortoise ORM models. |
| `admin.py`  | `ModelAdmin` classes and calls to `admin_site.register`. |
| `views.py`  | Optional custom admin views registered with `admin_site.register_view`. |
| `cards.py`  | Optional dashboard card registrations. |
| `router.py` | Optional application API endpoints |
| `tasks.py`  | Optional application Cellery tasks |

A minimal `views.py` might expose a bespoke report page:

```python
from typing import Any

from fastapi import Request

from freeadmin.core.interface.services.auth import AdminUserDTO
from freeadmin.core.runtime.hub import admin_site


@admin_site.register_view(path="/reports/sales", name="Sales report", label="Reports", icon="bi-graph-up")
async def sales_report(request: Request, user: AdminUserDTO) -> dict[str, Any]:
    data = await request.app.state.report_service.fetch_sales_summary()
    return {
        "page_message": "Latest sales metrics.",
        "card_entries": [],
        "context": {"totals": data},
        "assets": {"css": (), "js": ()},
    }
```

`AppConfig` (from `freeadmin.core.interface.app`) lets you run code during discovery or startup. Example:

```python
from freeadmin.core.interface.app import AppConfig
from freeadmin.core.runtime.hub import admin_site

from .admin import PostAdmin
from .models import Post


class BlogConfig(AppConfig):
    app_label = "blog"
    name = "apps.blog"

    async def startup(self) -> None:
        admin_site.register(app="blog", model=Post, admin_cls=PostAdmin)


default = BlogConfig()
```

You can also register models directly inside `admin.py` if you prefer not to use an `AppConfig`. Both patterns are supported.


## 4. Optional folders

* `pages/` – store Markdown or HTML documents and expose them via custom admin views.
* `static/` – add project-specific CSS or JavaScript. The boot manager mounts this directory alongside FreeAdmin's bundled assets.
* `templates/` – override FreeAdmin templates or add new ones used by your custom views.

All three folders are left empty so you can organise them according to your team's conventions.


## 5. Discovery process

During startup `BootManager` invokes the discovery service with the packages you supplied (for example `["apps"]`). Discovery imports each package's `admin.py`, `app.py`, and other modules that register resources on `admin_site`. Once discovery finishes the admin site knows about:

* Model admins declared via `admin_site.register`.
* Standalone views registered with `admin_site.register_view`.
* Cards registered with `admin_site.register_card`.
* Optional startup hooks implemented on `AppConfig.startup()`.

Understanding this flow helps when you need to debug why an admin class is not appearing — ensure the module containing the registration is importable and that the package is listed for discovery.


## 6. Summary

| Area | Location | Notes |
| ---- | -------- | ----- |
| FastAPI integration | `config/main.py` | Instantiates `BootManager` and mounts the admin router. |
| ORM setup | `config/orm.py` | Declares the adapter, module lists, and `ORMConfig` instance for the active adapter. |
| Environment configuration | `config/settings.py` | Wraps environment variables with a typed settings model. |
| Domain code | `apps/` | Holds models, admins, cards, and optional startup hooks. |
| Presentation assets | `templates/`, `static/` | Extend or override frontend resources. |
| Supplementary content | `pages/` | Provide documentation or helper pages accessible from the admin. |

Following this structure keeps your project organised and makes FreeAdmin's discovery process predictable as your code base grows.
