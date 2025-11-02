# -*- coding: utf-8 -*-
"""
autodiscoverer

Helper for autoloading of admin model submodules.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
import importlib
import pkgutil
from typing import Any, Generic, List, TypeVar, cast


T = TypeVar("T")


class ModelAutoDiscoverer(Generic[T]):
    """Autoload all submodules with models (except service ones)."""

    def __init__(self, model_base: type[T]) -> None:
        self.model_base = model_base
        self.models: List[type[T]] = []
        self._autodiscover_models()

    def _autodiscover_models(self) -> None:
        package = __package__ or ""
        pkg = importlib.import_module(package)
        for m in pkgutil.iter_modules(pkg.__path__):
            name = m.name
            if name.startswith("_") or name in {"choices", "autodiscoverer"}:
                continue
            module = importlib.import_module(f"{package}.{name}")
            for attr in module.__dict__.values():
                if isinstance(attr, type) and issubclass(attr, self.model_base):
                    model_cls = cast(type[T], attr)
                    meta = getattr(model_cls, "_meta", None)
                    if not getattr(meta, "abstract", False):
                        self.models.append(model_cls)
                        setattr(pkg, model_cls.__name__, model_cls)

# The End

