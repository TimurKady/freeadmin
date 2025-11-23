# Settings Mode

This guide explains how the admin panel's settings mode differs from standard ORM pages and how to register global configuration views.

## Purpose and `/orm` vs `/settings`

- **`/orm`** – CRUD interface for regular models. Routes live under `/orm/{app}/{model}` and enforce per-model permissions such as `app.model.view` or `app.model.change`. The `{model}` segment is the model's class name in lowercase (e.g., `StreamGraph` becomes `streamgraph`).
- **`/settings`** – exposes configuration models that apply globally. Routes mount at `/settings/{app}/{model}` and check only global permissions (`view`, `add`, `change`, `delete`) without binding them to a specific content type.

## Registering a settings admin

Use `AdminSite.register` with `settings=True` to mount a model under `/settings`:

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.admin import AdminSite

class SiteConfigAdmin(ModelAdmin):
    model = SiteConfig

site = AdminSite()
site.register(app="core", model=SiteConfig, admin_cls=SiteConfigAdmin, settings=True, icon="bi-gear")

# or register for both ORM and settings in one call
site.register_both(
    app="core",
    model=SiteConfig,
    admin_cls=SiteConfigAdmin,
    icon="bi-gear",
)
```

`AdminSite.register` automatically initializes permissions, metadata and the navigation entry.

## Routes and permissions

The router mounts CRUD endpoints for settings using the same patterns as ORM pages:

```
/settings/{app}/{model}/        # list view
/settings/{app}/{model}/add     # create form
/settings/{app}/{model}/{pk}/edit
```

Every route depends on `require_global_permission`, so users need the corresponding global `view`, `add`, `change`, or `delete` right. ORM pages instead rely on `require_model_permission` and check per-model codenames like `streams.streamgraph.view`.

## Template reuse

Both `/orm` and `/settings` use a unified `context/list.html` template for their list views, so there is no separate variant per mode. The same `context/form.html` is also shared. Only the top-level pages (`pages/settings.html` and `pages/settings_index.html`) differ, so UI tweaks usually apply to both modes.

## Troubleshooting

- **403 Forbidden** – the user is authenticated but lacks the required global permission.
- **404 Not Found** – the path refers to an unregistered admin or a missing object. Verify that `register(..., settings=True)` was called and that the model exists.

