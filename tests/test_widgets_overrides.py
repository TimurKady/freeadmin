# -*- coding: utf-8 -*-
"""
widgets overrides tests

Ensure ``Meta.widgets`` mappings are honored and inherited across admin subclasses.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import pytest

from freeadmin.contrib.widgets.base import BaseWidget
from freeadmin.core.interface.models import ModelAdmin
from freeadmin.core.schema.descriptors import FieldDescriptor, ModelDescriptor


class DummyAdapter:
    """Minimal adapter exposing a static model descriptor."""

    def __init__(self, descriptor: ModelDescriptor) -> None:
        self._descriptor = descriptor

    def get_model_descriptor(self, model):
        """Return the provided descriptor regardless of ``model``."""

        return self._descriptor


class TrackingWidget(BaseWidget):
    """Widget that records the field name used during schema generation."""

    def __init__(self, ctx=None):
        super().__init__(ctx)
        self.used_with: str | None = None

    def get_schema(self):
        """Return a simple schema fragment marking the last field name."""

        self.used_with = getattr(self.ctx, "name", None)
        return {"type": "string", "widget": self.used_with}


@pytest.mark.asyncio
async def test_meta_widgets_applied_to_schema() -> None:
    descriptor = ModelDescriptor(
        app_label="app",
        model_name="item",
        dotted="app.Item",
        table="item",
        pk_attr="id",
        fields=[FieldDescriptor(name="title", kind="string")],
    )
    adapter = DummyAdapter(descriptor)

    class ArticleAdmin(ModelAdmin):
        model = object

        class Meta:
            widgets = {"title": TrackingWidget()}

    admin = ArticleAdmin(object, adapter)
    schema = await admin.get_schema(None, None, descriptor, mode="add")
    widget_schema = schema["schema"]["properties"]["title"]

    assert widget_schema["widget"] == "title"
    assert admin.widgets_overrides["title"].ctx is not None


@pytest.mark.asyncio
async def test_meta_widgets_are_inherited() -> None:
    descriptor = ModelDescriptor(
        app_label="app",
        model_name="item",
        dotted="app.Item",
        table="item",
        pk_attr="id",
        fields=[
            FieldDescriptor(name="title", kind="string"),
            FieldDescriptor(name="slug", kind="string"),
        ],
    )
    adapter = DummyAdapter(descriptor)

    class BaseArticleAdmin(ModelAdmin):
        model = object

        class Meta:
            widgets = {"title": TrackingWidget()}

    class ChildArticleAdmin(BaseArticleAdmin):
        class Meta:
            widgets = {"slug": TrackingWidget()}

    admin = ChildArticleAdmin(object, adapter)
    schema = await admin.get_schema(None, None, descriptor, mode="add")
    props = schema["schema"]["properties"]

    assert props["title"]["widget"] == "title"
    assert props["slug"]["widget"] == "slug"
    assert admin.widgets_overrides["title"].ctx is not None
    assert admin.widgets_overrides["slug"].ctx is not None


# The End

