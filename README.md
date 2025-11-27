# FastAPI FreeAdmin 
## Coming soon (Q1 2026)

**Modular admin panel for FastAPI and Tortoise ORM**

[![Tests](https://github.com/TimurKady/freeadmin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/TimurKady/freeadmin/actions/workflows/ci.yml)
[![Docs](https://readthedocs.org/projects/freeadmin/badge/?version=latest)](https://freeadmin.readthedocs.io/)
[![PyPI](https://img.shields.io/pypi/v/freeadmin.svg)](https://pypi.org/project/freeadmin/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Sponsor](https://img.shields.io/github/sponsors/TimurKady)](https://github.com/sponsors/TimurKady)

## Overview

FreeAdmin delivers a modular administration panel for FastAPI projects that couples a Django-inspired workflow with asynchronous services and a Bootstrap 5 UI. It supports CRUD automation, live dashboards, and custom pages without sacrificing extensibility or security controls.

* **ORM-first data management**. Model admins encapsulate the entire CRUD experience: list tables expose configurable columns, default ordering, and instant search/filter controls, while detail forms respect custom field layouts, widgets, and readonly rules. Each admin class can further tailor queryset hooks for list, detail, and form operations, ensuring that row-level security and select/prefetch strategies stay under application control.

    Related data does not require context switching. Inline admin components embed nested forms directly inside the parent editor, reusing the same queryset hooks and action system so teams can manage one-to-many relationships with the same validation and RBAC guarantees as top-level models.

* **Custom admin views and pages**. Beyond CRUD, the site router can mount arbitrary FastAPI handlers as admin views. Registered pages automatically join the sidebar next to ORM models, inherit shared layout/breadcrumb logic, and can opt into the settings area when needed. This makes it straightforward to add dashboards, reports, or workflow-specific screens without leaving the admin shell.

* **Live cards with Server-Sent Events**. The cards subsystem streams real-time updates through a dedicated SSE API. Each card endpoint issues signed access tokens, enforces per-user permissions, and reuses cached state so dashboards can recover the latest payload instantly while background publishers push fresh events.

* **Import and export pipelines**. Bulk data moves through dedicated services. The import workflow caches uploads, parses CSV/JSON/XLSX files, filters selected fields, and persists rows via the active `ModelAdmin`, all while producing detailed progress reports and supporting dry runs.

    Exports follow a similar pipeline: query adapters collect the dataset, serializers normalize fields, and writers produce CSV, JSON, or XLSX files stored in a temporary cache with automatic cleanup and streaming helpers for large downloads.

* **Additional highlights**. FreeAdmin ships with JSON Schema-driven forms, reusable widgets, role-based access control, a CLI scaffold, and an extensible adapter layer so the panel can target multiple ORMs while keeping the Bootstrap frontend consistent.

FreeAdmin is a modern, ORM-agnostic administration panel inspired by Django Admin, but built for the FastAPI ecosystem. It provides a powerful, extensible interface for managing your application data and settings with minimal boilerplate.

![FreeAdmin dashboard preview](https://raw.githubusercontent.com/TimurKady/freeadmin/main/docs/images/scr-0.jpg)

## Installation

```bash
pip install freeadmin
```

### Requirements

* Python 3.11+
* FastAPI
* Tortoise ORM
* PostgreSQL (recommended)

## Quickstart

Follow these high-level steps to get an admin interface up and running. Detailed instructions live in [Installation and Getting Started Guide](https://github.com/TimurKady/freeadmin/blob/main/docs/installation-and-cli.md).

### 1. Scaffold a project

Use the CLI to create the basic layout and change into the new directory:

```bash
freeadmin init demo_admin
cd demo_admin
freeadmin add blog
```

### 2. Define your models and admin configuration

Populate `apps/blog/models.py` and `apps/blog/admin.py` with your domain objects and admin classes:

```python
from tortoise import fields
from tortoise.models import Model

from freeadmin.core.interface.models import ModelAdmin
from freeadmin.core.runtime.hub import admin_site


class Post(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        app = "blog"


class PostAdmin(ModelAdmin):
    """Admin configuration describing how blog posts appear in the panel."""

    list_display = ("id", "title", "created_at")


admin_site.register(app="blog", model=Post, admin_cls=PostAdmin)
```

### 3. Mount the admin panel

Initialise FreeAdmin inside your FastAPI application (usually in `config/main.py`):

```python
from freeadmin.core.application import ApplicationFactory


application = ApplicationFactory()
app = application.build()
```

### 4. Run the server

```bash
export FA_DATABASE_URL="sqlite:///./db.sqlite3"
freeadmin create-superuser
uvicorn config.main:app --reload
```

Open [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) and log in with the credentials you created.

## Documentation

See the [Documentation](https://github.com/TimurKady/freeadmin/blob/main/docs/index.md).

## Roadmap

* Support for additional ORMs (SQLAlchemy, GINO).
* Extended set of built-in widgets.
* Internationalization (i18n).

## License
### FreeAdmin licenses
FreeAdmin is **dual-licensed**:

* **AGPL-3.0** (default): You are free to use, modify, and distribute this project under the terms of the GNU Affero General Public License v3.0.
  Any software or service that uses FreeAdmin, including SaaS and internal platforms, **must make its complete source code available under AGPL-3.0**.

* **Commercial License**: Available for organizations that wish to use FreeAdmin without the copyleft requirements of AGPL-3.0.
  This option allows proprietary, closed-source, or commercial use of the software.
  To obtain a commercial license, contact with [me](https://github.com/TimurKady).

### Third-party licenses

The package depends on and bundles third-party components. When redistributing the project (including deployment in a
SaaS environment) you must retain the notices listed below and keep the referenced license texts available to users.

#### Python runtime dependencies

| Dependency | License | Compliance notes |
| --- | --- | --- |
| FastAPI | MIT | Include the upstream MIT license and copyright notice when redistributing binary or source builds.
| Starlette | BSD-3-Clause | Preserve the BSD disclaimer and copyright notice in any redistributed copies or documentation.
| Jinja2 | BSD-3-Clause | Keep the BSD license text together with any redistributed source/binary artifacts.
| itsdangerous | BSD-3-Clause | Preserve the BSD license notice and warranty disclaimer when shipping the software.
| Tortoise-ORM | Apache-2.0 | Provide the Apache 2.0 license text and propagate any NOTICE file; document local modifications if you change the code.
| python-multipart | Apache-2.0 | Ship the Apache 2.0 license text and carry forward any NOTICE information.
| Pydantic | MIT | Bundle the MIT license text and include attribution in your documentation or “About” page.
| PyJWT | MIT | Keep the MIT license text together with the distributed package.
| openpyxl | MIT | Retain the MIT copyright statement and license grant in redistributed materials.

For MIT-licensed dependencies the standard requirement is to provide the full MIT license and attribution. For the
Apache 2.0 dependencies ensure that the license text and NOTICE file (if present) remain accessible to end users and that
any modifications are documented. BSD-licensed dependencies require preserving their license and disclaimer text.

#### Bundled frontend assets

| Asset | Version | License and source | Compliance notes |
| --- | --- | --- | --- |
| Bootstrap | 5.3.3 | MIT – bundled in `freeadmin/static/vendors/bootstrap/LICENSE` (upstream: <https://github.com/twbs/bootstrap>) | Keep the MIT license reference visible and ship the bundled license file with redistributions.
| Bootstrap Icons | 1.11.3 | MIT – bundled in `freeadmin/static/vendors/bootstrap-icons/LICENSE` (upstream: <https://github.com/twbs/icons>) | Distribute alongside the provided MIT license file.
| jQuery | 3.7.1 | MIT – bundled in `freeadmin/static/vendors/jquery/LICENSE.txt` (upstream: <https://jquery.org/license>) | Retain the header notice and make the MIT license text available via the bundled file.
| JsBarcode | 3.12.1 | MIT – bundled in `freeadmin/static/vendors/jsbarcode/LICENSE` (upstream: <https://github.com/lindell/JsBarcode>) | Preserve the MIT header comments and keep the bundled license file with redistributed builds.
| Select2 | 4.0.13 | MIT – bundled in `freeadmin/static/vendors/select2/LICENSE` (upstream: <https://github.com/select2/select2>) | Bundle the MIT license file and link from documentation where appropriate.
| Choices.js | 11.1.0 | MIT – bundled in `freeadmin/static/vendors/choices/LICENSE` (upstream: <https://github.com/Choices-js/Choices>) | Ship the MIT license file together with the packaged assets.
| Ace (Ace Editor builds) | 1.43.3 | BSD-3-Clause – bundled in `freeadmin/static/vendors/ace-builds/LICENSE` (upstream: <https://github.com/ajaxorg/ace-builds>) | Retain the BSD license text within your documentation or redistribution package.
| JSONEditor | 9.x | MIT – bundled `freeadmin/static/vendors/json-editor/LICENSE` file | Keep the included MIT license file with the distributed assets.

If you update any of the vendor bundles, refresh the version numbers above and bring along their current license files so
that downstream consumers have access to the required texts.

#### Distribution footprint review

To keep release reviews straightforward we periodically record the size of bundled assets and build artifacts:

* `du -sh freeadmin/static` → ~37 MB (vendor assets dominate the total, especially Bootstrap Icons and Ace Editor language/snippet packs).
* `python -m build` produces:
  * Wheel: `dist/freeadmin-0.1.0-py3-none-any.whl` ≈ 7.7 MB.
  * Source archive: `dist/freeadmin-0.1.0.tar.gz` ≈ 6.2 MB.

The sizes are acceptable for the current release cadence, but the Ace and JSONEditor test fixtures remain the largest contributors. If future distributions need to slim down further, consider pruning unused Ace modes/snippets or excluding JSONEditor test pages while keeping the required license files listed above.

## Credits

This work is built brick by brick and released as real Open Source.  If you find it useful, help me ship the next bricks faster, you can support the development via [GitHub Sponsors](https://github.com/sponsors/your-username).
I’m committed to production-grade, documented, and maintained tools.  Your support funds tests, docs, and releases.

---

*This project is under active development. Contributions are welcome!*
