# -*- coding: utf-8 -*-
"""tests.test_icon_paths

Regression tests for icon URL resolution helpers.

Version:0.1.0
Author: OpenAI Codex
"""

from __future__ import annotations

import pytest

from freeadmin.utils.icons.icon import IconPathMixin


class DummyIconOwner(IconPathMixin):
    """Expose the icon resolution helper for testing."""


@pytest.mark.parametrize(
    "icon_path, prefix, static_segment, expected",
    [
        (
            "freeadmin/static/images/icon-36x36.png",
            "/admin",
            "/staticfiles",
            "/staticfiles/images/icon-36x36.png",
        ),
        (
            "images/logo.png",
            "/admin",
            "static-content/",
            "/static-content/images/logo.png",
        ),
        (
            "https://cdn.example.com/icon.png",
            "/admin",
            "/staticfiles",
            "https://cdn.example.com/icon.png",
        ),
        (
            "//cdn.example.com/icon.png",
            "/admin",
            "/staticfiles",
            "//cdn.example.com/icon.png",
        ),
        (
            "static/logo.png",
            "/",
            "/",
            "/logo.png",
        ),
    ],
)
def test_resolve_icon_path(icon_path: str, prefix: str, static_segment: str, expected: str) -> None:
    """Relative icon paths should resolve against the static mount segment."""

    assert DummyIconOwner._resolve_icon_path(icon_path, prefix, static_segment) == expected


# The End
