# Admin widgets

## WidgetContext

The `freeadmin/contrib/widgets/context.py` module provides an immutable `WidgetContext` passed to every widget. The context stores metadata about the model, current request, and model instance:

```python
from freeadmin.contrib.widgets.context import WidgetContext

ctx = WidgetContext(
    admin=admin,
    descriptor=md,
    field=fd,
    name="author",
    instance=post,
    mode="edit",
    request=request,
)
```

Within a widget the current model instance is available as ``ctx.instance``
(`None` when creating a new object).

Field overview:

- ``admin`` – :class:`ModelAdmin` managing the model.
- ``descriptor`` – :class:`ModelDescriptor` for the model.
- ``field`` – :class:`FieldDescriptor` describing the field.
- ``name`` – field name in the form.
- ``instance`` – current object, ``None`` on add.
- ``mode`` – current admin view: ``add`` | ``edit`` | ``list``.
- ``request`` – optional FastAPI ``Request``.
- ``readonly`` – ``True`` when the field is read-only for the current mode.
- ``prefix`` – admin URL prefix used when resolving static assets.

Within a widget it's more convenient to access the instance via :meth:`BaseWidget.get_instance`.

## Creating a widget

A new widget subclasses :class:`BaseWidget` and is registered with the `@registry.register` decorator:

```python
from freeadmin.contrib.widgets import BaseWidget, registry

@registry.register("rating", priority=20)
class RatingWidget(BaseWidget):
    ...
```

Admin classes can override default widget resolution via ``Meta.widgets`` or the ``widgets`` attribute. Both mappings are merged together and inherited down the admin subclass chain, so base admin classes can define shared overrides reused by derived classes.

### BaseWidget utilities

`BaseWidget` provides a small set of hooks for building widgets:

- ``get_title()`` – label for the field (falls back to the field name).
- ``get_schema()`` – return a JSON Schema fragment describing the field.
- ``get_startval()`` – starting value for edit forms.
- ``prefetch()`` – optional async preparation before generating the schema.
- ``to_python(value, options=None)`` – convert an incoming value to Python.
- ``to_storage(value, options=None)`` – convert Python data for persistence.

```python
class RatingWidget(BaseWidget):
    async def prefetch(self):
        self._choices = [1, 2, 3, 4, 5]

    def get_schema(self):
        return {
            "type": "integer",
            "title": self.get_title(),
            "enum": self._choices,
        }

    def to_python(self, value, options=None):
        return int(value) if value is not None else None

    def to_storage(self, value, options=None):
        return str(value) if value is not None else None
```

### Schema generation

Widgets produce JSON Schema fragments via :meth:`get_schema`. The admin form
expects a single ``type`` and optional ``enum``/``enum_titles`` pairs. Optional
FK fields include an empty string in ``enum`` to represent a placeholder, with
the label provided by ``placeholder_option_text``. Schema combiners such as
``oneOf`` are not supported and should be avoided.

## Resolver and registry

`registry.register` registers a class in `WidgetRegistry` under the given key. When multiple widgets match a field, the registry selects the entry with the highest `priority` value.

### `WidgetRegistry.resolve_for_field`

`WidgetRegistry.resolve_for_field` chooses a default widget for a model field using the following rules:

* boolean fields → `checkbox`;
* relation fields (FK/M2M) → `relation`;
* fields with `choices` → `radio`;
* numeric types → `number`;
* date/time fields → `datetime`;
* other fields → `text`.

See [contrib/admin/widgets/registry.py](../../contrib/admin/widgets/registry.py) for the implementation details.

## Built-in widgets

### CheckboxWidget

- **Registration key:** `checkbox` (`@registry.register("checkbox")`)
- **Purpose:** render boolean values as a checkbox or Bootstrap switch.
- **Main options:** `format: "checkbox"`; `options.containerAttributes.class: "form-check form-switch"`; `options.inputAttributes` sets the input class, type, and `role="switch"`.

### ChoicesWidget

- **Registration key:** `choices` (`@registry.register("choices")`)
- **Purpose:** provide single or multi-select controls powered by Choices.js.
- **Main options:** `format: "choices"` for single selects; many-to-many fields use `format: "checkbox"` with labels in `items.options.enum_titles`; `options.enum_titles` supplies labels for single values; `options.choices_options` passes extra Choices.js settings; `options.placeholder` sets the empty label.

```json
{
  "type": "array",
  "format": "checkbox",
  "items": {
    "type": "string",
    "enum": ["py", "js"],
    "options": {"enum_titles": ["Python", "JavaScript"]}
  },
  "options": {"placeholder": "Select tags…"}
}
```

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import ChoicesWidget


class PostAdmin(ModelAdmin):
    class Meta:
        widgets = {"tags": ChoicesWidget()}
```

### BarCodeWidget

- **Registration key:** `barcode` (`@registry.register("barcode")`)
- **Purpose:** render UUID values as Code128 barcodes.
- **Main options:** `options` forwarded to [JsBarcode](https://github.com/lindell/JsBarcode#options) for customizing dimensions, font, and other styling. The barcode input is hidden by default; set `show_input` to `True` to display it.

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import BarCodeWidget


class TicketAdmin(ModelAdmin):
    class Meta:
        widgets = {
            "uuid": BarCodeWidget(options={"height": 80, "width": 2, "fontSize": 18}),
        }
```

### DateTimeWidget

- **Registration key:** `datetime` (`@registry.register("datetime")`)
- **Purpose:** handle `date`, `datetime`, and `time` fields using HTML5 inputs.
- **Main options:** `format` automatically set to `"date"`, `"time"`, or `"datetime-local"` based on the field kind.

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import DateTimeWidget


class EventAdmin(ModelAdmin):
    class Meta:
        widgets = {
            "start_at": DateTimeWidget(),
        }
```

### FilePathWidget

- **Registration key:** `filepath` (`@registry.register("filepath")`)
- **Purpose:** store file paths with upload support.
- **Main options:** `format: "url"`; includes `options.upload` with the upload handler and `media_prefix`. The `to_storage` method accepts absolute URLs (e.g., `https://site/media/file.txt`) and stores them as relative paths. Paths beginning with the `media/` prefix are automatically stripped before saving.
- **Assets:** ships with `/static/widgets/filepath.js` and `/static/widgets/filepath.css` to handle uploads and preview layout.

The JavaScript bundle exposes a `FilePathUploaderManager` singleton. The manager
waits for `JSONEditor` to be present, registers the upload callback declared in
the schema (`options.upload.upload_handler = "FilePathUploader"`), and
re-emits download links when editors finish rendering. Initialization is driven
by the `admin:jsoneditor:*` lifecycle events documented in
[`frontend.md`](frontend.md); the widget automatically subscribes to those
events when its asset is included, so no extra template code is required.

### NumberWidget

- **Registration key:** `number` (`@registry.register("number")`)
- **Purpose:** numeric input for integers or floating-point values.
- **Main options:** `type: "integer"` for integer fields; `type: "number"` for others.

### RadioWidget

- **Registration key:** `radio` (`@registry.register("radio")`)
- **Purpose:** display fields with choices as radio buttons.
- **Accepted choice formats:** dictionaries, iterables of `(value, label)` pairs, plain iterables of values, Python ``Enum`` classes, and Django ``Choices`` subclasses such as ``TextChoices`` or ``IntegerChoices``.
- **Main options:** `format: "radio"`; `enum` holds the values; `options.enum_titles` supplies labels.

```json
{
  "type": "integer",
  "format": "radio",
  "enum": [1, 2],
  "options": {"enum_titles": ["Active", "Inactive"]}
}
```

### RelationsWidget

- **Registration key:** `relation` (`@registry.register("relation")`)
- **Purpose:** select widget for foreign keys and many‑to‑many relations. During `prefetch`, the widget loads related objects and fills `FieldDescriptor.meta["choices_map"]` to avoid extra ORM queries.
- **Main options:** `enum` with possible keys; `options.enum_titles` with labels for single selects; multi‑value fields use `format: "checkbox"` and keep labels under `items.options.enum_titles`; placeholders remain under `options.placeholder` and are independent of `enum_titles`.

```json
{
  "type": "array",
  "title": "Tags",
  "format": "checkbox",
  "uniqueItems": true,
  "items": {
    "type": "string",
    "enum": ["1", "2"],
    "options": {"enum_titles": ["T1", "T2"]}
  },
  "options": {"placeholder": "--- Select ---"}
}
```

### Select2Widget

- **Registration key:** `select2` (`@registry.register("select2")`)
- **Purpose:** remote select widget powered by Select2 with AJAX lookups for ForeignKey fields.
- **Main options:** `format: "select2"`. The widget forms `enum` automatically, storing labels under `options.enum_titles` and builds the lookup URL centrally. Custom filter parameters are not accepted.

```json
{
  "type": "string",
  "format": "select2",
  "enum": ["1"],
  "options": {
    "enum_titles": ["A1"],
    "select2": {"ajax": {"url": "/lookup"}},
    "placeholder": "Select author"
  }
}
```

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import Select2Widget


class PostAdmin(ModelAdmin):
    class Meta:
        widgets = {
            "author": Select2Widget(),
        }
```

### TextWidget

- **Registration key:** `text` (`@registry.register("text")`)
- **Purpose:** simple text input.
- **Main options:** `type: "string"`; `format: "text"`.

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import TextWidget


class UserAdmin(ModelAdmin):
    class Meta:
        widgets = {"email": TextWidget(format="email")}
```

`BaseModelAdmin` reuses this instance, injecting the context at runtime.

### TextAreaWidget

- **Registration key:** `textarea` (`@registry.register("textarea")`)
- **Purpose:** multi-line text input with optional Ace-based syntax highlighting.
- **Main options:** `format: "textarea"`. To enable highlighting, set
  `FieldDescriptor.meta["syntax"]` to an Ace mode (e.g. `"python"`) or pass an
  `ace` configuration when instantiating the widget. An optional
  `FieldDescriptor.meta["ace_theme"]` chooses the theme (default `"chrome"`).
  The generated schema includes `options.ace` with the corresponding `mode` and
  `theme`. When syntax highlighting is enabled—either via field metadata or the
  widget's `ace` argument—the widget's asset bundler ensures the Ace library is
  loaded automatically.

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import TextAreaWidget


class ArticleAdmin(ModelAdmin):
    class Meta:
        widgets = {
            "body": TextAreaWidget(
                format="markdown",
                options={"simplemde": {"status": False}},
            )
        }
```

`options.simplemde` configures the embedded SimpleMDE editor, and the provided widget instance is preserved by `BaseModelAdmin`.

#### Examples with syntax highlighting

The widget can enable Ace highlighting either via field metadata or through the
`ace` argument at instantiation time. The following examples demonstrate common
configurations:

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import TextAreaWidget


class JsonPostAdmin(ModelAdmin):
    class Meta:
        widgets = {
            "payload": TextAreaWidget(
                format="textarea",
                ace={"mode": "json", "theme": "chrome"},
            ),
        }
```

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import TextAreaWidget


class ScriptAdmin(ModelAdmin):
    class Meta:
        widgets = {
            "script": TextAreaWidget(
                format="textarea",
                ace={"mode": "python", "theme": "monokai"},
            ),
        }
```

#### Example with additional parameters

The widget accepts extra configuration for the embedded editor. The example below
demonstrates how to enable Ace highlighting and tweak editor options:

```python
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.contrib.widgets import TextAreaWidget


class PostAdmin(ModelAdmin):
    class Meta:
        widgets = {
            "body": TextAreaWidget(
                ace={"mode": "python", "theme": "monokai"},
                editor={"lineNumbers": True},
            )
        }
```


<!-- # The End -->
