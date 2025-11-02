# FreeAdmin Module Map

## 1. Current Module State

This information reflects the file and logical structure of the `freeadmin/` directory in the repository's current state. The focus is on nodes that participate in initializing the administrative core, integrating with FastAPI, and serving the user interface.

### 1.1 Key Modules and Direct Dependencies

| Path | Purpose | First-order Direct Dependencies |
| --- | --- | --- |
| `freeadmin/core/application/factory.py` | FastAPI application factory that wires settings, the ORM, and routers together | `freeadmin.core.boot.BootManager`, `freeadmin.core.orm.ORMConfig/ORMLifecycle`, `freeadmin.core.network.router.AdminRouter`, `freeadmin.core.runtime.hub.admin_site` |
| `freeadmin/core/boot/manager.py` | Manages adapters, model registration, and hub startup | Adapter registry (`freeadmin.contrib.adapters`), system settings (`freeadmin.core.configuration.conf`), middleware `freeadmin.core.runtime.middleware.AdminGuardMiddleware`, hub `freeadmin.core.runtime.hub` |
| `freeadmin/core/configuration/conf.py` | Configuration store and environment change observer | `os`, `pathlib`, synchronization via `threading.RLock` |
| `freeadmin/core/runtime/hub.py` | Central admin hub that manages the site, autodiscovery, and routers | Settings (`freeadmin.core.configuration.conf`), `freeadmin.core.interface.site.AdminSite`, `freeadmin.core.interface.discovery.DiscoveryService`, `freeadmin.core.network.router.AdminRouter`, `freeadmin.core.boot.admin` |
| `freeadmin/core/interface/site.py` | Admin site implementation: registers models/pages, menus, export | Interface services (`freeadmin.core.interface.*`), adapters, CRUD, card API, template provider, migration checks |
| `freeadmin/core/network/router/base.py` | Base helpers for mounting admin routes | `fastapi.FastAPI`, `freeadmin.core.interface.templates.TemplateService`, `freeadmin.core.interface.site.AdminSite` |
| `freeadmin/core/network/router/aggregator.py` | Coordinates creation and attachment of admin and public routers | `freeadmin.core.network.router.base.RouterFoundation`, `fastapi.APIRouter`, `freeadmin.core.interface.site.AdminSite`, `freeadmin.core.interface.templates.TemplateService` |
| `freeadmin/core/runtime/provider.py` | Manages templates, static files, and media | `fastapi`, `starlette.staticfiles.StaticFiles`, `freeadmin.core.configuration.conf.FreeAdminSettings`, `freeadmin.core.interface.settings.system_config` |
| `freeadmin/core/runtime/middleware.py` | Admin guard middleware (superuser, session) | `starlette` middleware, `freeadmin.core.configuration.conf`, `freeadmin.core.interface.settings`, `freeadmin.core.boot.admin` |
| `freeadmin/contrib/crud/operations.py` | Builds CRUD routes and file exchange | `fastapi`, `freeadmin.core.interface` services, `freeadmin.core.configuration.conf`, `freeadmin.core.interface.settings`, `freeadmin.core.interface.services` |
| `freeadmin/contrib/api/cards.py` | SSE and REST API for cards | `fastapi.APIRouter`, `freeadmin.core.interface.site.AdminSite`, `freeadmin.core.interface` services |
| `freeadmin/core/data/orm/config.py` | ORM configuration and Tortoise lifecycle | `tortoise` ORM, adapter registry, migration error classifier (`freeadmin.utils.migration_errors`) |

## 2. Importance Levels

- **Core**: `freeadmin/core/` (subpackages `application`, `boot`, `configuration`, `data`, `interface`, `network`, `runtime`), as well as `freeadmin/contrib/adapters/` and helper models. These elements handle configuration, resource registration, ORM integration, and global services.
- **Shells**: compatibility facades `freeadmin/router/`, `freeadmin/crud.py`, `freeadmin/middleware.py`, `freeadmin/pages/`, `freeadmin/widgets/`, `freeadmin/templates/`, `freeadmin/static/`, `freeadmin/runner.py`, `freeadmin/cli.py`. The modules provide HTTP interfaces, the UI, and auxiliary scripts.
- **Utilities**: `freeadmin/utils/`, `freeadmin/schema/`, `freeadmin/tests/`, `freeadmin/provider.py`, `freeadmin/meta.py`. Service components and extensible helpers.

## 3. Core Structure

### 3.1 Grouping Logic

* **`core/application/`** — factories and protocols that assemble FastAPI applications with the admin attached.
* **`core/boot/`** — startup manager that coordinates adapters, system apps, and middleware wiring.
* **`core/configuration/`** — settings and configuration manager that watches environment changes.
* **`core/data/`** — ORM integration and supporting data models.
* **`core/interface/`** — admin descriptors, services, template helpers, and top-level REST interfaces.
* **`core/network/`** — routers and aggregators that mount admin HTTP routes.
* **`core/runtime/`** — hub, middleware, template provider, and other runtime code.

External extensions and integrations live in `freeadmin/contrib/`, including adapters and CRUD utilities. In the current structure, high-level facades were removed: projects plug components directly from the `core/` and `contrib/` subpackages.

### 3.2 Main Public Modules

| Path | Purpose |
| --- | --- |
| `freeadmin/core/application` | FastAPI application factories. |
| `freeadmin/core/boot` | Startup manager and adapters. |
| `freeadmin/core/runtime/hub.py` | Central hub and autodiscovery. |
| `freeadmin/core/configuration/conf.py` | Settings and configuration manager. |
| `freeadmin/core/data/orm` | ORM configuration and lifecycle. |
| `freeadmin/core/network/router` | Aggregators and helper routers. |
| `freeadmin/core/runtime/provider.py` | Template and static provider. |
| `freeadmin/core/runtime/middleware.py` | AdminGuard and related middleware. |
| `freeadmin/contrib/crud/operations.py` | CRUD route builder. |
