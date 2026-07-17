"""Smoke test for the main entry point."""

from __future__ import annotations

from unittest.mock import patch


def test_main_entry_point_imports() -> None:
    """main entry point should be importable and callable."""
    from mko_telebot.main import main

    assert callable(main)


def test_main_calls_app() -> None:
    """main should call app when invoked."""
    with patch("mko_telebot.main.app") as mock_app:
        from mko_telebot.main import main

        main()
        mock_app.assert_called_once()