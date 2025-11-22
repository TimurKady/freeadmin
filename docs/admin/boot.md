# Admin Boot Process

Initialize the admin application through the ``admin`` boot manager.
It wires configuration startup hooks, registers middleware, registers
built-in pages and mounts the admin site onto the ASGI application.

## Quick start

```python
from fastapi import FastAPI
from freeadmin.contrib.adapters import registry
from freeadmin.core.boot import admin
from my_project.adapters import MyAdapter

app = FastAPI()

# Register the adapter instance so the boot manager can resolve it by name.
registry.register(MyAdapter())

admin.init(app, adapter="my_adapter", packages=["apps", "contrib", "core"])

```

## Adapter selection

Provide the database backend via the ``adapter`` keyword (for example
``adapter="tortoise"`` for the bundled Tortoise ORM integration). Supply your
own adapter by creating an instance that implements the adapter protocol and
registering it with ``freeadmin.contrib.adapters.registry`` before referencing the name
with ``admin.init``. Existing adapter instances should be registered with the
registry rather than passed directly to ``BootManager.init`` so they can be
reused across the runtime. Access the active adapter through the
``BootManager.adapter`` property (or ``runtime_hub.admin_site.adapter``) so that
custom adapters selected at boot are propagated consistently across discovery,
registration, and finalisation.

## BootManager responsibilities

``BootManager`` consolidates tasks that previously required manual setup:

- registering middleware and configuration hooks
- loading page definitions from the supplied packages
- mounting the admin site on the ASGI application

These steps replace any manual ``AdminRouter`` mounting.

## Middleware

``AdminGuardMiddleware`` protects the admin interface. It redirects unauthenticated users to the login page and forces initial setup when no superuser exists. Configuration values are read from ``SystemConfig`` and cached for efficiency:

- ``ADMIN_PREFIX`` – base URL prefix for the admin site.
- ``LOGIN_PATH`` – relative path to the login view.
- ``LOGOUT_PATH`` – relative path to the logout view.
- ``SETUP_PATH`` – path used for the initial superuser creation.
- ``STATIC_PATH`` – location of static assets served by the admin.
- ``SESSION_KEY`` – session key storing the authenticated user identifier.
- ``SESSION_COOKIE`` – session cookie name.

Example FastAPI integration:

```python
from fastapi import FastAPI
from freeadmin.core.runtime.middleware import AdminGuardMiddleware

app = FastAPI()
app.add_middleware(AdminGuardMiddleware)
```

## CSRF Protection

Login and setup forms embed a CSRF token stored in the session. Each POST
handler verifies the ``csrf_token`` field before processing the request.

For details on manual mounting and autodiscovery see [Hub and Router](hub-router.md).


# The End

