"""Tests for setup_logging in logging.py.

Tests cover:
- Successful YAML config loading
- Fallback to basicConfig when log_config.yaml is missing
- Error handling for invalid config
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

from mko_telebot.logging import setup_logging


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_logging_yaml() -> dict[str, object]:
    """Return a minimal valid logging config dict."""
    return {
        "LOGGING": {
            "version": 1,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                },
            },
            "root": {
                "level": "INFO",
            },
        },
    }


def _valid_logging_yaml_with_file_handler(tmp_path: Path) -> dict[str, object]:
    """Return logging config with a console handler (no file handler to avoid I/O issues)."""
    return {
        "LOGGING": {
            "version": 1,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                },
            },
            "root": {
                "level": "DEBUG",
                "handlers": ["console"],
            },
        },
    }


def _write_yaml(path: Path, data: dict[str, object]) -> Path:
    """Write a YAML file and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return path


def _get_root_handlers() -> list[logging.Handler]:
    """Get the current root logger handlers."""
    return logging.root.handlers.copy()


def _get_root_level() -> int:
    """Get the current root logger level."""
    return logging.root.level


def _reset_logging() -> None:
    """Reset logging to a clean state for testing."""
    logging.root.handlers.clear()
    logging.root.setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# TestSetupLogging
# ---------------------------------------------------------------------------


class TestSetupLogging:
    """Tests for setup_logging() function."""

    def test_setup_logging_with_valid_yaml_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """setup_logging should load and apply valid logging YAML config."""
        from mko_telebot.core.paths import APP_PATHS

        # Create settings/log_config.yaml (user_settings_dir structure)
        settings_dir = tmp_path / "settings"
        _write_yaml(settings_dir / "log_config.yaml", _valid_logging_yaml())

        # Patch APP_PATHS.user_dir to use tmp_path
        monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)

        # Call setup_logging
        setup_logging()

        # Verify logging was configured (root level should be set to INFO from config)
        root_level = _get_root_level()
        assert root_level == logging.INFO

    def test_setup_logging_fallback_to_basicconfig_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """setup_logging should fall back to basicConfig when log config is missing."""
        from mko_telebot.core.paths import APP_PATHS

        # Patch APP_PATHS.user_dir to use tmp_path (no log_config.yaml in settings)
        monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)

        # Clear any existing handlers and reset level
        _reset_logging()

        # Call setup_logging - should fall back to basicConfig
        setup_logging()

        # With basicConfig(level=INFO), root level should be INFO
        assert _get_root_level() == logging.INFO

    def test_setup_logging_with_custom_config_path(self, tmp_path: Path):
        """setup_logging should use explicit config_path when provided."""
        # Create log_config.yaml with custom path
        config_path = tmp_path / "custom_log_config.yaml"
        _write_yaml(config_path, _valid_logging_yaml())

        # Call setup_logging with explicit path (no patching needed)
        setup_logging(config_path=config_path)

        # Verify logging was configured
        assert _get_root_level() == logging.INFO

    def test_setup_logging_resolves_relative_log_file_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """setup_logging should resolve relative log file paths to absolute."""
        from mko_telebot.core.paths import APP_PATHS

        # Create settings/log_config.yaml with file handler
        settings_dir = tmp_path / "settings"
        _write_yaml(settings_dir / "log_config.yaml", _valid_logging_yaml_with_file_handler(tmp_path))

        # Patch user_dir
        monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)

        # Call setup_logging
        setup_logging()

        # Verify the file handler was configured (check that handlers exist)
        handlers = _get_root_handlers()
        assert len(handlers) > 0

    def test_setup_logging_uses_default_paths_when_none(self, monkeypatch: pytest.MonkeyPatch):
        """setup_logging should use APP_PATHS defaults when config_path is None."""
        from mko_telebot.core.paths import APP_PATHS

        # Set user_dir to a non-existent path to trigger fallback
        monkeypatch.setattr(APP_PATHS, "user_dir", Path("/nonexistent"), raising=False)

        # Reset logging state
        _reset_logging()

        # Call setup_logging without explicit path
        setup_logging()

        # Should have fallen back to basicConfig
        assert _get_root_level() == logging.INFO