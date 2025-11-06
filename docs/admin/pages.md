# Built-in Pages

The admin panel ships with a registrar that defines placeholder pages for views, ORM models, and system settings.
It demonstrates how to wire handlers through `AdminSite.register_view` and `AdminSite.register_settings`.

## Registering default sections

```python
from freeadmin.contrib.apps.system.views import BuiltinPagesRegistrar
from freeadmin.core.runtime.hub import hub

BuiltinPagesRegistrar().register(hub.admin_site)
```

Internally, the registrar attaches handlers using decorators. The sidebar guard
skips section landing routes automatically, so the `include_in_sidebar` flag is
optional when you reuse these defaults:

```python
from freeadmin.core.interface.site import AdminSite
from freeadmin.core.interface.settings import SettingsKey, system_config

class BuiltinPagesRegistrar:
    def register(self, site: AdminSite) -> None:
        @site.register_view(
            path=self.views_prefix,
            name=self.views_title,
            icon=self.views_icon,
            include_in_sidebar=False,
        )
        async def views_placeholder(request, user):
            page_title = await system_config.get(SettingsKey.VIEWS_PAGE_TITLE)
            return site.build_template_ctx(request, user, page_title=page_title)

        @site.register_view(
            path=self.orm_prefix,
            name=self.orm_title,
            icon=self.orm_icon,
            include_in_sidebar=False,
        )
        async def orm_home(request, user):
            page_title = await system_config.get(SettingsKey.ORM_PAGE_TITLE)
            return site.build_template_ctx(request, user, page_title=page_title, is_settings=False)

        @site.register_settings(
            path=self.settings_prefix,
            name=self.settings_title,
            icon=self.settings_icon,
        )
        async def settings_home(request, user):
            page_title = await system_config.get(SettingsKey.SETTINGS_PAGE_TITLE)
            return site.build_template_ctx(request, user, page_title=page_title, is_settings=True)
```

## Registering standalone admin views

`AdminSite.register_view` now feeds both the navigation sidebar and the standalone routing table. Each view must be stored inside its
application package (`app/views.py` or `app/views/__init__.py`) and reuse the application label so the sidebar groups it together with
existing model admins.

```python
from fastapi import Request
from freeadmin.core.interface.templates.rendering import render_template
from freeadmin.core.runtime.hub import admin_site


@admin_site.register_view(
    path="/views/blog/stats",
    name="Statistics",
    label="Blog",
    icon="bi-graph-up",
)
async def blog_stats_view(request: Request):
    metrics = await load_blog_metrics()
    return render_template("blog/stats.html", {"metrics": metrics}, request=request)
```

> **Note:** `AdminRouter.mount()` automatically adds the admin base path as a prefix,
> so the route above resolves under the admin namespace without additional changes. Avoid
> duplicating the admin prefix when registering the view; otherwise the final endpoint would
> mount at `/admin/admin/...`, breaking `AdminSite.parse_section_path()` and sidebar
> highlighting.

The sidebar renders standalone views alongside registered models. When the `Blog` application exposes both a `PostAdmin` model and the
`Statistics` view above, the navigation accordion shows a single `Blog` group containing `Posts` (model) and `Statistics` (view). No
changes to `includes/sidebar.html` are required because each view entry is serialized with the same structure as a model entry.

Use `AdminSite.get_sidebar_views()` when you need direct access to the collected view metadata—for example, in custom dashboards or
analytics that replicate the sidebar. The data is returned as `{label: [view, ...]}` records with `display_name`, `path`, and optional
`icon` values ready for templating.

## Class-based pages with ``BaseTemplatePage``

When you prefer class-based organisation, inherit from
:class:`freeadmin.core.interface.pages.BaseTemplatePage` instead of writing
plain functions. The base class stores the site reference, registers template
directories, and exposes helpers that wrap :meth:`BaseTemplatePage.get_context`
into FastAPI handlers. This keeps route registration idempotent and removes the
need to duplicate boilerplate for every page.

```python
from pathlib import Path

from fastapi import Request

from freeadmin.core.interface.pages import BaseTemplatePage
from freeadmin.core.runtime.hub import admin_site

# from myproject.analytics import load_blog_metrics


class BlogStatisticsPage(BaseTemplatePage):
    """Expose blog metrics through a reusable class-based page."""

    path = "/views/blog/statistics"
    name = "Statistics"
    label = "blog"
    template = "blog/statistics.html"
    template_directory = Path(__file__).parent / "templates"

    def __init__(self) -> None:
        """Register the admin view once during application startup."""

        super().__init__(site=admin_site)
        self.register_admin_view()

    async def get_context(
        self, *, request: Request, user: object | None = None
    ) -> dict[str, object]:
        """Return context injected into the configured template."""

        metrics = await load_blog_metrics()
        return {"metrics": metrics}


blog_statistics_page = BlogStatisticsPage()
```

``BaseTemplatePage`` keeps ``register_admin_view()`` and
``register_public_view()`` separate so each page can decide whether it should
live under the admin, the public site, or both. Override
``get_public_handler()`` when you need a dedicated FastAPI coroutine for public
routes; otherwise the base class reuses :meth:`get_handler`.

## URL prefixes and highlighting

`AdminSite.parse_section_path` inspects each request URL to keep the sidebar state synchronized with the current page. Standalone routes
use the prefix stored in `SettingsKey.VIEWS_PREFIX` (defaults to `/views/`). The prefix is automatically stripped to recover the
application label and view name, which are then injected into the template context as `current_app` and `current_model`. If you override
the prefix in settings, ensure that each registered path continues to follow the `/prefix/<app>/<view>/` format so breadcrumbs and
highlighting keep working.

## Admin view conventions

Admin views extend the model-first experience with dashboards, reports, custom workflows, or integrations that do not fit CRUD. They
must comply with the following guidelines:

1. **Purpose**
   * Use views for analytics, dashboards, advanced forms, or external integrations.
   * Do not duplicate CRUD behaviour, redefine authentication, or break the shared admin layout.
2. **Registration**
   * Always call `AdminSite.register_view` with the application label, human-readable name, and optional Bootstrap icon class.
   * Keep all view functions in `app/views.py` or `app/views/` to simplify discovery and registration.
3. **Implementation**
   * Implement routes as FastAPI callables that accept a `Request` and return `TemplateResponse` objects via the shared `render` helper.
   * Keep business logic in services; the view should assemble lightweight context dictionaries.
4. **Context and permissions**
   * Use `render(..., request=request)` so `AdminSite.build_template_ctx` injects sidebar data, user info, and settings.
   * Integrate with the existing RBAC system and raise `HTTPException(status_code=403)` for unauthorized access.
5. **Sidebar integration**
   * Views inherit their application label, ensuring they appear under the same group as model admins.
   * Global sections are not supported; every view belongs to an app.
6. **Best practices**
   * Name handlers with the `_view` suffix, place templates under `templates/<app>/`, and keep responses performant by delegating heavy
     lifting to background services.

These conventions keep custom pages consistent with the rest of the admin interface and ensure that navigation, breadcrumbs, and visual
styling operate without manual adjustments.

## Feeding the sidebar navigation

`AdminSite.register_view` now contributes entries to the left-hand sidebar so
that custom pages appear next to ORM models. The site groups everything by the
app label recorded for each view. Follow these conventions when you add custom
pages:

1. Place the view coroutine in the Django app that owns the related models,
   under `views.py` or a module inside the app's `views/` package. This keeps
   imports aligned with Django's app registry and makes the label available.
2. When registering the handler, reuse the app label so that the sidebar can
   merge the view with existing model links. You can set the label explicitly
   or rely on the default derived from the path's first segment.

```python
# apps/articles/views/manage.py
from freeadmin.core.interface.site import AdminSite


class ArticleAdminViews:
    def __init__(self, site: AdminSite):
        self._site = site

    def register(self) -> None:
        """Attach admin-only view handlers to the site."""

        @self._site.register_view(
            path="/views/articles/featured",
            name="Featured Articles",
            icon="bi-lightning",
            label="articles",  # matches the app label
        )
        async def featured_articles(request, user):
            return self._site.build_template_ctx(
                request,
                user,
                page_title="Featured Articles",
            )
```

The sidebar output now lists models and views together:

```
Articles
├── Article (model)
├── Category (model)
└── Featured Articles (view)
```

The `AdminSite.get_sidebar_views(settings=False)` helper exposes the grouped
view entries that power this navigation. Use it to inspect or test the
generated structure:

```python
groups = hub.admin_site.get_sidebar_views(settings=False)
# -> [("articles", [{"display_name": "Featured Articles", ...}]), ...]
```

Views registered with `settings=True` are collected separately so they only
appear when browsing the settings area.

## Routing prefixes and breadcrumbs

`AdminSite.build_template_ctx` uses routing prefixes stored in
`SystemSetting` to compute breadcrumbs and highlight the active menu item.
The `SettingsKey.VIEWS_PREFIX` value (default `/views`) must align with the
paths you pass to `register_view`; otherwise, the navigation highlight and
built-in breadcrumbs will not reflect the current page. Update the prefix when
you expose standalone views under a different URL root:

```python
from freeadmin.core.interface.settings import SettingsKey, system_config

await system_config.set(SettingsKey.VIEWS_PREFIX, "/console")
```

Remember to adjust your `register_view` paths so they still start with the new
prefix.

## Customizing titles and icons

All page labels and icons are stored in `SystemSetting` and accessed through `SettingsKey` constants. Update them to change how built-in pages appear:

```python
from freeadmin.core.interface.settings import SettingsKey, system_config

await system_config.set(SettingsKey.VIEWS_PAGE_TITLE, "Custom Views")
await system_config.set(SettingsKey.VIEWS_PAGE_ICON, "bi-star")
```

# The End

