# Public pages

FreeAdmin can expose public FastAPI pages alongside the administrative interface. The
`ExtendedRouterAggregator` coordinates both the `/admin` routes and additional routers
mounted in the root URL space so that projects keep a single integration point.

## Architecture overview

``RouterAggregator`` builds the administrative router, mounts static files, and caches
the resulting `APIRouter`. `ExtendedRouterAggregator` inherits from it and introduces:

- `add_admin_router()` – register extra admin routers (mounted under the admin prefix;
  the primary admin router is provided automatically);
- `add_additional_router()` – register public routers without any prefix;
- `get_routers()` – retrieve all routers honouring the desired order;
- `router` – an aggregated `APIRouter` that can be included directly.

Pass `public_first=False` when instantiating the class to keep admin routes ahead of
public ones.

## Example: registering the welcome page

Create a public page in `example/pages/public_welcome.py` (the packaged example
follows the same structure) by extending :class:`freeadmin.core.interface.pages.BaseTemplatePage`:

```python
from pathlib import Path

from fastapi import Request

from freeadmin.core.interface.pages import BaseTemplatePage
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.runtime.hub import admin_site


class PublicWelcomePage(BaseTemplatePage):
    """Register the example welcome page with the admin site."""

    path = "/"
    name = "Welcome"
    template = "pages/welcome.html"
    template_directory = Path(__file__).resolve().parent.parent / "templates"
    icon = "bi-stars"

    def __init__(self) -> None:
        """Register the public welcome view when instantiated."""

        super().__init__(site=admin_site)
        self.register_public_view()
        self.register_public_navigation()

    def register_public_navigation(self) -> None:
        """Register supplemental public navigation entries for the example."""

        login_path = system_config.get_cached(SettingsKey.LOGIN_PATH, "/login")
        admin_site.register_public_menu(
            title="Sign in",
            path=login_path,
            icon="bi-box-arrow-in-right",
        )

    async def get_context(
        self,
        *,
        request: Request,
        user: object | None = None,
    ) -> dict[str, object]:
        """Return template context for the welcome example page."""

        return {
            "subtitle": "Rendered outside the admin",
            "user": user,
        }


public_welcome_page = PublicWelcomePage()
```

Handlers decorated with `register_public_view()` return a mapping used as template
context. The page manager injects the request, anonymous user, and page title before
rendering the template through :class:`PageTemplateResponder`.

``BaseTemplatePage`` registers declared template directories with the shared
renderer, so templates become available immediately after instantiation. The
same subclass can call :meth:`BaseTemplatePage.register_admin_view` when you
want to expose the page to authenticated staff while keeping
``register_public_view()`` for anonymous visitors. This allows you to share
context-building logic, templates, or even static assets between both
interfaces.

The site automatically registers each public view in the public navigation menu.
The example above supplements that menu with a dedicated "Sign in" entry by
calling :meth:`PublicWelcomePage.register_public_navigation`, which internally
invokes :func:`freeadmin.core.runtime.hub.AdminSite.register_public_menu`.
You can also register additional links directly when you need to expose a
standalone destination:

```python
from freeadmin.core.runtime.hub import admin_site

admin_site.register_public_menu(
    title="Documentation",
    path="/docs",
    icon="bi-journal-text",
)
```

Menu entries honour the ``PUBLIC_PREFIX`` setting, so you can host all public pages under a dedicated URL segment while keeping administrative navigation unaffected.

Place a template at `example/templates/pages/welcome.html`. It can extend the
administrative layout while remaining visually independent:

```jinja
{% extends "layout/base.html" %}
{% block title %}{{ title }}{% endblock %}
{% block content %}
<div class="fa-public-welcome">
    <section class="fa-public-welcome__hero">
        <h1 class="fa-public-welcome__title">{{ title }}</h1>
        <p class="fa-public-welcome__subtitle">{{ subtitle | default("This page lives outside the admin panel.") }}</p>
    </section>
    <section class="fa-public-welcome__body">
        <p>
            Customize this template freely. It shares the same rendering engine as the
            administration area but does not depend on its styling.
        </p>
    </section>
</div>
{% endblock %}
```

## Registering routers

```python
from fastapi import FastAPI

from freeadmin.core.runtime.hub import admin_site
from freeadmin.core.network.router import ExtendedRouterAggregator

app = FastAPI()
aggregator = ExtendedRouterAggregator(site=admin_site)
aggregator.mount(app)
```

`mount()` ensures the admin site is cached, registers the favicon, static files, and
exposes registered public pages alongside the automatically included admin router.
Additional routers can still be registered via
:meth:`ExtendedRouterAggregator.add_additional_router` when needed.

## Adding new public pages

1. Create a module under your project's pages package (for example,
   `example/pages/`).
2. Subclass :class:`BaseTemplatePage`, override :meth:`BaseTemplatePage.get_context`,
   and call :meth:`BaseTemplatePage.register_public_view`.
3. Provide a template in your project's template directory.
4. Call :meth:`ExtendedRouterAggregator.mount` or include
   :attr:`ExtendedRouterAggregator.router` in your FastAPI app to expose the admin
   and public routers.

## Integrating with an existing ``main.py``

```python
from fastapi import FastAPI

from freeadmin.core.runtime.hub import admin_site
from freeadmin.core.network.router import ExtendedRouterAggregator

app = FastAPI()

aggregator = ExtendedRouterAggregator(site=admin_site, public_first=True)
app.include_router(aggregator.router)
```

`aggregator.router` combines the admin router and every registered public router.
Calling `mount()` remains available when you need FreeAdmin to mount static assets
for you automatically.
