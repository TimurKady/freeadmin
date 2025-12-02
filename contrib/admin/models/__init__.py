# -*- coding: utf-8 -*-
"""
__init__

Single point of connection of Admin Models.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
import importlib
import pkgutil
from typing import List

from tortoise.models import Model

# Export enumerations
from .choices import StrChoices, IntChoices  # noqa: F401

__all__ = ["StrChoices", "IntChoices"]

# List of models that Tortoise uses when loading a package
__models__: List[type[Model]] = []


# Autoloading of all submodules with models (except service ones)
def _autodiscover_models() -> None:
    package = __name__
    for m in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        name = m.name
        if name.startswith("_") or name in {"choices"}:
            continue
        module = importlib.import_module(f"{package}.{name}")
        for attr in module.__dict__.values():
            if isinstance(attr, type) and issubclass(attr, Model) and not attr._meta.abstract:
                __models__.append(attr)
                globals()[attr.__name__] = attr


_autodiscover_models()

# export detected models to __all__
__all__ += [model.__name__ for model in __models__]

# The End
