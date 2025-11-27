# InlineModelAdmin contract

InlineModelAdmin builds on ModelAdmin to manage related objects within parent forms. Inline admin components allow editing of
related objects directly inside the parent form while respecting backend contracts for validation and persistence.

## Quick start
1. Define an inline class by subclassing the provided inline base.
2. Register the inline with its parent admin class.
3. Inline lists are rendered on the parent edit page via the ``/{pk}/_inlines`` endpoint and rely on ``admin-form.js`` to load ``admin-list.js`` dynamically. No extra template changes are required beyond the standard form template.

## Security considerations
- Validate permissions for both parent and inline models.
- Limit exposed fields to prevent mass-assignment vulnerabilities.
- Constrain querysets to the active user's data scope.

## Frontend contract
- Inline forms submit nested payloads keyed by the inline prefix.
- Each entry carries its `id`, field values, and a `DELETE` flag when removed.
- Server responses echo serialized inline objects using the same structure.

## Troubleshooting
- Missing inlines often indicate incomplete management form data.
- If add/remove buttons fail, ensure the inline JavaScript bundle is loaded.
- Review permission mixins when inline objects do not appear for certain users.

## Testing checklist
- [ ] Add and Add first buttons create inline forms when clicked.
- [ ] Creating and updating inline items persists data correctly.
- [ ] Validation errors appear next to the affected inline fields.
- [ ] Unauthorized users cannot view or modify restricted inlines.
- [ ] Parent edit pages render the inline host container and load admin-form.js.

## Attributes
- `model` – related model class
- `parent_fk_name` – foreign key name on the inline model pointing to the parent
- `can_delete` – allow object deletion
- `display` – "tabular" or "stacked"

## Authorization
Access to endpoints is handled via dependency injection (RBAC). InlineModelAdmin does **not** perform authorization.

## QuerySet hooks (all must return a QuerySet)
- `get_queryset()` -> QuerySet (typically `model.all()`)
- `get_list_queryset(request, user)` -> QuerySet
  = base -> `apply_select_related` -> `apply_only` -> `apply_row_level_security`
- `get_objects(request, user)` -> QuerySet
  = base -> `apply_select_related` -> `apply_row_level_security`
- `form_queryset(md, mode, qs=None)` -> QuerySet
  = `all()` -> `select_related` -> `prefetch_related`
- `apply_select_related(qs)` -> QuerySet
- `apply_only(qs)` -> QuerySet
- `apply_row_level_security(qs, user)` -> QuerySet (RLS)

## Business constraints (UI)
- `allow(user, action, obj=None)` -> bool
Used to hide buttons, set fields read-only, or apply soft business validation (403/422).
Does **not** replace RBAC.

## Actions
Administrative actions live in `contrib/admin/core/actions`. The package defines the
`BaseAction` interface and an `ActionSpec` describing each action's name, label,
parameters, and risk level. Parameter types are expressed as strings such as
"boolean" or "string". Actions operate on querysets in batches and may be
reused across different admins.

### `InlineModelAdmin.actions`, `list_actions`, `get_action` and `get_actions`
`InlineModelAdmin.actions` holds a tuple of available action classes. By default it
includes `DeleteSelectedAction`. Use `list_actions()` to enumerate action names
and `get_action(name)` to obtain a bound instance. The `get_actions()` method
instantiates all actions and returns a dictionary mapping each action's
`spec.name` to the corresponding instance for bulk access. Action names must be
unique; duplicates raise ``ValueError``.

### `DeleteSelectedAction`
Removes all objects from the queryset after confirmation.

- **spec.name**: `delete_selected`
- **scope**: `['ids', 'query']`
- **params**: `{"confirm": "boolean"}` — must be `True` to proceed

```python
result = await admin.perform_action(
    "delete_selected", queryset, {"confirm": True}, user
)
```

> **Note**
> Always require explicit confirmation before executing destructive actions.

## QuerySet contract
1. Every QuerySet hook must return a QuerySet.
2. `get_list_queryset` is built as `base → apply_select_related → apply_only → apply_row_level_security`.
3. `get_objects` is built as `base → apply_select_related → apply_row_level_security`.
4. `apply_row_level_security` is always executed last.
5. Returning a non-QuerySet raises `RuntimeError`.

## form_queryset and get_object

`form_queryset` builds the base QuerySet for form operations. By default it calls `all()` on the model and automatically adds `select_related` for foreign keys and `prefetch_related` for many-to-many relations. The method can be overridden to extend the selection:

```python
class BookInline(InlineModelAdmin):
    def form_queryset(self, md, mode, qs=None):
        qs = super().form_queryset(md, mode, qs)
        return qs.select_related("author").prefetch_related("tags")
```

`get_object` uses `get_objects` → `form_queryset` and returns an object via `get`/`aget`. Overriding allows custom retrieval logic:

```python
async def get_object(self, request, md, mode, user):
    obj = await super().get_object(request, md, mode, user)
    # additional processing
    return obj
```

## RLS invariants
- `get_list_queryset` and `get_objects` must apply `apply_row_level_security`.
- In `get_schema(mode="edit")` the object is retrieved through `get_objects(...)` (RLS).
- `has_view/add/change/delete_permission` methods have been removed.

