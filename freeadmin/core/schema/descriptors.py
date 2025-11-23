# -*- coding: utf-8 -*-
"""
descriptors

Deprecated entry point forwarding to ``freeadmin.core.schema_descriptors``.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import warnings

from freeadmin.core.schema_descriptors import Choice, FieldDescriptor, ModelDescriptor, Relation

warnings.warn(
    "freeadmin.core.schema.descriptors is deprecated; import from freeadmin.core.schema_descriptors instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Choice", "FieldDescriptor", "ModelDescriptor", "Relation"]


# The End

