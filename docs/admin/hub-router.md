# Hub and Router

`AdminHub` manages the admin site's discovery and mounting logic.

## Autodiscovery

`AdminHub.autodiscover` walks the given packages and imports modules named `admin` or containing the `.admin` segment. Importing these modules registers admin pages so that the site can expose them later.

During discovery the hub also imports sibling modules named `views`, `service`, and `services`, which covers admin-specific views and publisher services. API routers defined in `router.py` modules are not part of the discovery pass, so custom FastAPI routers must be mounted explicitly rather than relying on autodiscovery.

```python
from freeadmin.core.runtime.hub import hub

hub.autodiscover(["apps.blog", "apps.shop"])
```

## init_app shortcut

`AdminHub.init_app` combines autodiscovery with mounting the site on a FastAPI application:

```python
from fastapi import FastAPI
from freeadmin.core.runtime.hub import hub

app = FastAPI()
hub.init_app(app, packages=["apps.blog", "apps.shop"])
```

The call above imports all admin modules from the listed packages and mounts the admin site on the application.

## Mounting and assets

`AdminRouter.mount` delegates to the underlying `RouterAggregator`. The aggregator attaches the admin router, stores the site on `app.state`, and delegates template and static handling to `TemplateProvider` while caching those mounts so repeated calls stay idempotent.

The admin router itself always exposes the bundled system API (authentication, configuration, cards, and migrations). It does not automatically include routers from application code, so mount additional routers on the FastAPI app or register them with `RouterAggregator`/`ExtendedRouterAggregator` when you need to serve extra endpoints alongside the admin interface.

`TemplateProvider` builds the `Jinja2Templates` environment and mounts static files under the admin's prefix so that templates and assets are available without additional configuration.

# The End

