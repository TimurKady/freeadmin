"""Unit tests for admin integrity error handling."""

from __future__ import annotations

import pytest

from freeadmin.core.interface.base import BaseModelAdmin
from freeadmin.core.interface.exceptions import AdminIntegrityError


class DummyAdapter:
    """Minimal adapter stub for ``BaseModelAdmin`` tests."""

    def __init__(self) -> None:
        """Initialize the adapter stub without extra state."""


class DummyModel:
    """Placeholder model type for admin instantiation."""


def test_handle_integrity_error_preserves_detail() -> None:
    """Wrap integrity errors using the underlying exception message."""

    admin = BaseModelAdmin(DummyModel, DummyAdapter())
    with pytest.raises(AdminIntegrityError) as captured:
        admin.handle_integrity_error(Exception("unique constraint failed"))

    assert "unique constraint failed" in str(captured.value)


# The End

