# -*- coding: utf-8 -*-
"""
router.aggregator

Deprecated router aggregator forwarding to ``freeadmin.core.network_router``.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import warnings

from freeadmin.core.network_router import ExtendedRouterAggregator, RouterAggregator

warnings.warn(
    "freeadmin.core.network.router.aggregator is deprecated; use freeadmin.core.network_router instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ExtendedRouterAggregator", "RouterAggregator"]


# The End

