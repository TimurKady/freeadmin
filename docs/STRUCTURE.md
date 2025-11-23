# FreeAdmin target package layout

This repository is being flattened so the most important modules live in predictable, shallow locations. The target state below groups related code while avoiding single-module subpackages.

## Desired directory tree

```
freeadmin/
  admin.py                 # stable home for AdminSite
  application.py           # FastAPI application factory and router protocol
  config.py                # FreeAdminSettings and configuration helpers
  core/
    boot/
    interface/             # admin UI, pages, cards, permissions, services
    network_router.py      # router foundation, admin router, aggregators
    orm/
    runtime/
    schema_descriptors.py  # shared schema helpers
  contrib/
    adapters/
    adapters/tortoise/
    api/
    apps/
    crud.py                # CRUD router builder
    widgets/
  utils/
  models/
  static/
  templates/
```

Grouping is driven by runtime responsibilities: `admin.py`, `config.py`, and `application.py` anchor the public API; `core/` holds runtime plumbing (boot, interface, ORM, routing, schema utilities); `contrib/` contains optional extensions and adapters; `utils/`, `models/`, `templates/`, and `static/` remain supportive resources.

## Flattened modules

- `freeadmin/application.py` replaces `freeadmin/core/application/factory.py`.
- `freeadmin/config.py` replaces `freeadmin/core/configuration/conf.py` and the `core/conf.py` facade.
- `freeadmin/admin.py` replaces `freeadmin/core/interface/site.py` and the `core/site.py` facade.
- `freeadmin/core/network_router.py` replaces `freeadmin/core/network/router/base.py` and `freeadmin/core/network/router/aggregator.py`.
- `freeadmin/contrib/crud.py` replaces `freeadmin/contrib/crud/operations.py`.
- `freeadmin/core/schema_descriptors.py` replaces `freeadmin/core/schema/descriptors.py`.

Each move folds a single-file package into a top-level module to remove needless depth and indirection.

## Legacy shim paths

The following legacy modules remain temporarily as shims that emit `DeprecationWarning` while importing from the new stable locations:

- `freeadmin/core/application/factory.py`
- `freeadmin/contrib/crud/operations.py`
- `freeadmin/core/schema/descriptors.py`
- `freeadmin/core/network/router/base.py`
- `freeadmin/core/network/router/aggregator.py`
- `freeadmin/core/interface/site.py`
- `freeadmin/core/site.py`
- `freeadmin/core/conf.py`
- `freeadmin/core/configuration/conf.py`

Projects should update imports to the flattened modules listed above; the shims will be removed after downstream consumers migrate.


# The End

