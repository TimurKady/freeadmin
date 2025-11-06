# FreeAdmin Module Map

## 1. Current Module State

This information reflects the file and logical structure of the `freeadmin/` directory in the repository's current state. The focus is on nodes that participate in initializing the administrative core, integrating with FastAPI, and serving the user interface.

### 1.1 Key Modules and Direct Dependencies

| Path | Purpose | First-order Direct Dependencies |
| --- | --- | --- |
| `freeadmin/core/application/factory.py` | FastAPI application factory that wires settings, the ORM, and routers together | `freeadmin.core.boot.BootManager`, `freeadmin.core.orm.config.ORMConfig`, `freeadmin.core.network.router.AdminRouter`, `freeadmin.core.runtime.hub.admin_site` |
| `freeadmin/core/boot/manager.py` | Manages adapters, model registration, and hub startup | Adapter registry (`freeadmin.contrib.adapters.registry`), system settings (`freeadmin.core.configuration.conf`), middleware `freeadmin.core.runtime.middleware.AdminGuardMiddleware`, hub `freeadmin.core.runtime.hub` |
| `freeadmin/core/configuration/conf.py` | Configuration store and environment change observer | `os`, `pathlib`, synchronization via `threading.RLock` |
| `freeadmin/core/runtime/hub.py` | Central admin hub that manages the site, autodiscovery, and routers | Settings (`freeadmin.core.configuration.conf`), `freeadmin.core.interface.site.AdminSite`, `freeadmin.core.interface.discovery.DiscoveryService`, `freeadmin.core.network.router.AdminRouter`, `freeadmin.core.boot.admin` |
| `freeadmin/core/interface/site.py` | Admin site implementation: registers models/pages, menus, export | Interface services (`freeadmin.core.interface.*`), adapters, CRUD, card API, template provider, schema descriptors |
| `freeadmin/core/network/router/base.py` | Base helpers for mounting admin routes | `fastapi.FastAPI`, `freeadmin.core.interface.templates.TemplateService`, `freeadmin.core.interface.site.AdminSite` |
| `freeadmin/core/network/router/aggregator.py` | Coordinates creation and attachment of admin and public routers | `freeadmin.core.network.router.base.RouterFoundation`, `fastapi.APIRouter`, `freeadmin.core.interface.site.AdminSite`, `freeadmin.core.interface.templates.TemplateService` |
| `freeadmin/core/runtime/provider.py` | Manages templates, static files, and media | `fastapi`, `starlette.staticfiles.StaticFiles`, `freeadmin.core.configuration.conf.FreeAdminSettings`, `freeadmin.core.interface.templates.TemplateService` |
| `freeadmin/core/runtime/middleware.py` | Admin guard middleware (superuser, session) | `starlette` middleware, `freeadmin.core.configuration.conf`, `freeadmin.core.interface.settings`, `freeadmin.core.boot.admin` |
| `freeadmin/core/orm/config.py` | ORM configuration and Tortoise lifecycle | `tortoise` ORM, adapter registry, migration error classifier (`freeadmin.utils.migration_errors`) |
| `freeadmin/core/schema/descriptors.py` | Schema descriptors shared across interface services | `pydantic`, `freeadmin.core.interface` schema consumers |
| `freeadmin/contrib/crud/operations.py` | Builds CRUD routes and file exchange | `fastapi`, `freeadmin.core.interface` services, `freeadmin.core.configuration.conf`, `freeadmin.core.interface.settings`, `freeadmin.core.interface.services` |
| `freeadmin/contrib/api/cards.py` | SSE and REST API for cards | `fastapi.APIRouter`, `freeadmin.core.interface.site.AdminSite`, `freeadmin.core.interface` services |

## 2. Importance Levels

- **Core**: `freeadmin/core/` (subpackages `application`, `boot`, `configuration`, `interface`, `network`, `orm`, `runtime`, `schema`), as well as `freeadmin/contrib/adapters/` and helper models. These elements handle configuration, resource registration, ORM integration, and global services.
- **Shells**: entry points and runtime shims including `freeadmin/cli.py`, `freeadmin/runner.py`, and the bundled assets under `freeadmin/templates/` and `freeadmin/static/`. These modules expose command-line tooling, launch hooks, and the packaged UI resources.
- **Utilities**: `freeadmin/utils/`, `freeadmin/models/`, `freeadmin/meta.py`, and shared icons/security helpers. These pieces supply reusable utilities, domain models, and metadata helpers.

## 3. Core Structure

### 3.1 Grouping Logic

* **`core/application/`** — factories and protocols that assemble FastAPI applications with the admin attached.
* **`core/boot/`** — startup manager that coordinates adapters, system apps, and middleware wiring.
* **`core/configuration/`** — settings and configuration manager that watches environment changes.
* **`core/orm/`** — ORM integration and lifecycle helpers.
* **`core/schema/`** — Shared schema descriptors and validation helpers used by interface services.
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
| `freeadmin/core/orm` | ORM configuration and lifecycle. |
| `freeadmin/core/schema` | Schema descriptors and shared data shapes. |
| `freeadmin/core/network/router` | Aggregators and helper routers. |
| `freeadmin/core/runtime/provider.py` | Template and static provider. |
| `freeadmin/core/runtime/middleware.py` | AdminGuard and related middleware. |
| `freeadmin/contrib/crud/operations.py` | CRUD route builder. |
