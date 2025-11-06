# Installation and CLI

This guide walks through installing FreeAdmin, generating a project skeleton, and wiring the admin panel into a FastAPI + Tortoise ORM stack. The steps mirror the behaviour of the built-in CLI so the examples match the code that ships with this repository.


## Step 0. Prerequisites

* **Python 3.11+** (the package targets Python 3.11 and newer).
* **pip** and **venv** available on your PATH.
* A database supported by **Tortoise ORM**. SQLite works for local testing; PostgreSQL is recommended for production.

Check your interpreter and pip versions:

```bash
python --version
pip --version
```


## Step 1. Create and activate a virtual environment

**macOS / Linux**

```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Deactivate later with `deactivate`.


## Step 2. Install FreeAdmin

Install the latest release from PyPI:

```bash
pip install freeadmin
```

You can also install from a local clone by running `pip install .` inside the repository root.


## Step 3. Scaffold a project

Use the CLI to create the base layout:

```bash
freeadmin init myproject
cd myproject
```

The generator creates the following structure:

```
myproject/
├── config/
│   ├── main.py        # FastAPI application factory
│   ├── orm.py         # Placeholder for ORM configuration
│   ├── routers.py     # Provides an aggregator class and helper for admin routes
│   └── settings.py    # Pydantic settings model
├── apps/              # Your domain applications
├── pages/             # Optional static/markdown pages
├── static/            # Static assets
├── templates/         # Shared templates
└── README.md          # Short reminder about the scaffold
```

The generated files are intentionally minimal so you can adapt them to your stack. `config/routers.py` defines `ProjectRouterAggregator`, a thin subclass of `RouterAggregator` that centralises how the admin UI and related routers are mounted. The module also exports a ready-to-use `ROUTERS` instance so application code can rely on declarative mounting without re-implementing caching or asset registration. Override `ProjectRouterAggregator.get_additional_routers()` to describe extra routers that should accompany the admin site.


## Step 4. Configure project settings

Edit `config/settings.py` to describe your environment. The scaffold uses `pydantic_settings.BaseSettings`, so environment variables automatically override defaults:

```python
# config/settings.py
from pydantic_settings import BaseSettings


class ProjectSettings(BaseSettings):
    debug: bool = True
    database_url: str = "sqlite:///db.sqlite3"
    project_title: str = "myproject administration"


settings = ProjectSettings()
```

`project_title` controls the name rendered in the admin navigation and browser tab. If you prefer `.env` files, add `python-dotenv` to your project and call `load_dotenv()` before instantiating `ProjectSettings`.


## Step 5. Configure Tortoise ORM

Replace the placeholder in `config/orm.py` with a concrete configuration. The scaffold now exposes constants and an `ORMConfig` instance that you can tweak to match your adapter and model modules:

```python
# config/orm.py
from copy import deepcopy
from typing import Any, Dict

from freeadmin.contrib.adapters.tortoise.adapter import (
    Adapter as TortoiseAdapter,
)
from freeadmin.core.orm import ORMConfig

DB_ADAPTER = "tortoise"
APPLICATION_MODEL_MODULES: tuple[str, ...] = (
    "apps.blog.models",
)
SYSTEM_MODEL_MODULES: tuple[str, ...] = (
    "freeadmin.contrib.apps.system.models",
)
# Include adapter-provided admin models to enable the FreeAdmin UI resources.
ADMIN_MODEL_MODULES: tuple[str, ...] = tuple(TortoiseAdapter.model_modules)

ORM_CONFIG: Dict[str, Dict[str, Any]] = {
    "connections": {
        "default": "postgres://user:pass@localhost:5432/mydb",
    },
    "apps": {
        "models": {
            "models": list(APPLICATION_MODEL_MODULES),
            "default_connection": "default",
        },
        "system": {
            "models": list(SYSTEM_MODEL_MODULES),
            "default_connection": "default",
        },
        "admin": {
            "models": list(ADMIN_MODEL_MODULES),
            "default_connection": "default",
        },
    },
}

ORM: ORMConfig = ORMConfig.build(
    adapter_name=DB_ADAPTER,
    config=deepcopy(ORM_CONFIG),
)
```

For PostgreSQL or another backend, change the DSN stored in `ORM_CONFIG["connections"]` and adjust the module lists so discovery imports your models.


## Step 6. Create an application package

Generate an app skeleton with the CLI:

```bash
freeadmin add blog
```

This command adds `apps/blog/` containing empty files: `__init__.py`, `app.py`, `models.py`, `admin.py`, `views.py`, and `cards.py`. Fill these modules with your domain logic.

Register the package in your settings or discovery list. With the default scaffold you simply pass `"apps"` to the boot manager so every subpackage under `apps/` is discovered.


## Step 7. Define models and admin classes

Update `apps/blog/models.py` and `apps/blog/admin.py` to describe your data and how it should appear in the admin panel:

```python
# apps/blog/models.py
from tortoise import fields
from tortoise.models import Model


class Post(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    body = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "blog_post"
```

```python
# apps/blog/admin.py
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.core.runtime.hub import admin_site

from .models import Post


class PostAdmin(ModelAdmin):
    """Expose blog posts through the administration panel."""

    list_display = ("title", "created_at")
    search_fields = ("title",)


admin_site.register(app="blog", model=Post, admin_cls=PostAdmin)
```

If you need to run startup logic (for example to register cards or background publishers) create `apps/blog/app.py` and expose a `default` instance of `freeadmin.core.interface.app.AppConfig`.


## Step 8. Review the generated bootstrap

`freeadmin init` now scaffolds a `config/main.py` that already wires the boot manager, binds the ORM lifecycle, and initialises FreeAdmin with sensible defaults. The scaffold provides an `ApplicationFactory` class so you can register extra packages or lifecycle hooks before building the FastAPI instance:

```python
# config/main.py
from collections.abc import Iterable
from typing import List

from fastapi import FastAPI

from freeadmin.core.boot import BootManager
from freeadmin.core.orm import ORMConfig

from .orm import ORM
from .settings import ProjectSettings


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

        self._bind_orm_events()
        self._boot.init(
            self._app,
            adapter=self._orm_lifecycle.adapter_name,
            packages=self._packages,
        )
        return self._app

    def _bind_orm_events(self) -> None:
        """Attach ORM lifecycle hooks to the FastAPI application."""

        if self._orm_events_bound:
            return
        self._orm_lifecycle.bind(self._app)
        self._orm_events_bound = True


app = ApplicationFactory().build()

```

The default discovery packages (`apps` and `pages`) match the directories created by the CLI, so FreeAdmin autodiscovers model admins and content pages without further configuration. `BootManager.init()` delegates to the admin hub, which mounts the default router aggregator as part of application startup, so no additional router wiring is required in the scaffold. Pass a different `packages` iterable to `ApplicationFactory` when you need to customise discovery. Update `config/orm.py` to implement real startup and shutdown hooks for your adapter.

`config/routers.py` keeps router composition in one place. Import the scaffolded `ProjectRouterAggregator` when you need to customise mounting behaviour—for example, to declare additional routers exposed by your project:

```python
# config/routers.py
from fastapi import APIRouter

from freeadmin.core.runtime.hub import admin_site
from freeadmin.core.network.router import RouterAggregator


class ProjectRouterAggregator(RouterAggregator):
    """Aggregate routers exposed by myproject."""

    def __init__(self) -> None:
        """Initialise the aggregator with the admin site."""

        super().__init__(site=admin_site)
        # Declare additional routers when your project exposes them:
        # reports_router = APIRouter()
        # self.add_additional_router(reports_router, "/reports")


ROUTERS = ProjectRouterAggregator()

```

Call `add_additional_router()` (or pass `additional_routers` to `RouterAggregator.__init__()`) whenever you need to expose extra APIs. The `RouterAggregator` base class ensures the admin router, static assets, and favicon are mounted once per application instance and provides helpers such as `register_additional_routers()` if you need to trigger mounting manually.


## Step 9. Configure the database URL

FreeAdmin reads `FA_DATABASE_URL` when using the bundled Tortoise adapter. Export the variable or set it in your process manager before running the app:

```bash
export FA_DATABASE_URL="sqlite:///./db.sqlite3"
```

For PostgreSQL use a DSN such as `postgres://user:password@localhost:5432/mydb`.


## Step 10. Create an admin user

The CLI can create superusers for the bundled authentication models. Make sure the required tables already exist (for example by running your migrations or calling `Tortoise.generate_schemas()` after initialising the ORM) before executing the command:

```bash
freeadmin create-superuser --username admin --email admin@example.com
```

If you omit the flags the command will prompt for the missing values. The CLI initialises the ORM and stores the user record using the active adapter.

For first-time setups you can create schemas programmatically after wiring the ORM configuration (see Step 5 for the scaffolded settings). One-off scripts often look like:

```python
import asyncio

from tortoise import Tortoise


async def prepare() -> None:
    await Tortoise.init(
        db_url="sqlite:///./db.sqlite3",
        modules={"models": ["apps.blog.models", "freeadmin.contrib.apps.system.models"]},
    )
    await Tortoise.generate_schemas()


asyncio.run(prepare())
```

`freeadmin.contrib.apps.system.models` ships with the adapter and exposes the system tables (including authentication models)
required by the admin interface.


## Step 11. Run the development server

Use Uvicorn (or your ASGI server of choice) to run the FastAPI application:

```bash
uvicorn config.main:app --reload
```

Visit `http://127.0.0.1:8000/admin` (or the prefix you configured) and sign in with the credentials created in the previous step. The default interface includes list and detail views for any registered `ModelAdmin`, plus navigation for cards and custom pages.

> **Heads up:** FreeAdmin boots even when your database has no migrations. Public routes and any custom FastAPI routers remain available, but visiting the admin will redirect you to a setup notice that explains the missing schema. Use the migration or schema generation workflow for your adapter to unlock the full interface.


## Step 12. Troubleshooting tips

* **CLI cannot find `apps/`:** run the command from the project root where the scaffold created the folder.
* **Models not discovered:** ensure the module path (e.g. `apps.blog.models`) is listed in `modules["models"]` when initialising Tortoise.
* **`create-superuser` fails because tables are missing:** run your migrations or execute `Tortoise.generate_schemas()` after initialising the ORM so the auth tables exist.
* **Missing static assets:** verify that `freeadmin.core.boot.BootManager.init()` has been called and that your ASGI server can serve the mounted static route.
* **Session errors:** set `FA_SESSION_SECRET` to a stable value in production so session cookies remain valid across restarts.

With these steps you now have a working FreeAdmin installation backed by FastAPI and Tortoise ORM. Continue exploring the other documentation chapters for more detail on cards, permissions, and custom views.
