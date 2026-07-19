"""Unit tests for shared Streamlit navigation page registry."""

from __future__ import annotations

import pytest
from archium.ui import app_navigation


def test_get_app_page_unknown_raises() -> None:
    app_navigation._PAGES.clear()
    with pytest.raises(KeyError, match="Unknown app page"):
        app_navigation.get_app_page("missing")
