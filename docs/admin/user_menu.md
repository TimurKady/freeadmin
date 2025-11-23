# User Menu Items

`AdminSite.register_user_menu` attaches links to the user dropdown. Each entry requires a title and path and may include a Bootstrap icon class. The method stores the item in the registry so it becomes part of the context used by templates during rendering.

```python
from freeadmin.admin import AdminSite

class ExtraUserMenuRegistrar:
    def register(self, site: AdminSite) -> None:
        site.register_user_menu(title="Profile", path="/profile", icon="bi-person")
```

## Bootstrapping

Call the registrar before or after booting the admin application to integrate additional links:

```python
from fastapi import FastAPI
from freeadmin.core.boot import admin
from freeadmin.core.runtime.hub import hub
from my_project.admin.user_menu import ExtraUserMenuRegistrar

app = FastAPI()
ExtraUserMenuRegistrar().register(hub.admin_site)
admin.init(app)
```

## Template rendering and icons

`build_template_ctx` exposes a `user_menu` list consumed by `base.html`. If an icon is provided, the template prepends it to the label; otherwise only the title appears.

# The End

