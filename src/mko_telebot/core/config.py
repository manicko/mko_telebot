"""Configuration reader for mko_telebot.

Provides TelepostConfigReader for lazy-loading Pydantic-validated configuration
from config.yaml, telethon_config.yaml, and log_config.yaml files.

Usage:
    reader = TelepostConfigReader.from_user_dir()
    settings = reader.load()
    logging_config = reader.load_logging_config()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from mko_telebot.core.errors import ConfigError
from mko_telebot.core.models import TelepostSettings
from mko_telebot.core.paths import APP_PATHS

logger = logging.getLogger(__name__)


def resolve_path(path: str | Path, base_dir: Path | None = None) -> Path:
    """Resolve a path, handling relative paths and home-directory expansion.

    If a relative path is given, it is resolved against `base_dir`.

    Args:
        path: Path to resolve (can be absolute or relative).
        base_dir: Base directory for resolving relative paths.
            Defaults to the app settings directory.

    Returns:
        Resolved absolute Path.

    Raises:
        ConfigError: If the path cannot be resolved.
    """
    path = Path(path).expanduser()
    if path.is_absolute():
        return path
    base = base_dir or APP_PATHS.app_settings_dir
    return (base / path).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file, returning a dict.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed dictionary.

    Raises:
        ConfigError: If the file cannot be read or parsed.
    """
    if not path.exists():
        raise ConfigError("Configuration file not found", path=path)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ConfigError(
                "Expected a top-level mapping in YAML file", path=path
            )
        return data
    except yaml.YAMLError as e:
        raise ConfigError("Malformed YAML in configuration file", path=path) from e
    except OSError as e:
        raise ConfigError("Cannot read configuration file", path=path) from e


def _merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base, returning a new dict.

    Args:
        base: Base dictionary.
        overlay: Dictionary to merge in (overlay values win).

    Returns:
        New merged dictionary.
    """
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


class TelepostConfigReader:
    """Lazy configuration reader that loads and validates YAML config files.

    Reads config.yaml (monitoring) and telethon_config.yaml (Telethon API credentials),
    merges them, and validates the result against TelepostSettings.

    Attributes:
        config_path: Path to config.yaml.
        secrets_path: Path to telethon_config.yaml.
        log_config_path: Optional path to log_config.yaml.
    """

    def __init__(
        self,
        config_path: Path,
        secrets_path: Path,
        log_config_path: Path | None = None,
    ) -> None:
        """Initialize with explicit paths to config files.

        Args:
            config_path: Path to config.yaml.
            secrets_path: Path to telethon_config.yaml.
            log_config_path: Optional path to log_config.yaml.
        """
        self.config_path = config_path
        self.secrets_path = secrets_path
        self.log_config_path = log_config_path
        self._settings: TelepostSettings | None = None

    @classmethod
    def from_user_dir(cls, user_dir: Path | None = None) -> TelepostConfigReader:
        """Create a TelepostConfigReader from a user config directory.

        Args:
            user_dir: User config directory. Defaults to
                APP_PATHS.user_settings_dir.

        Returns:
            A new TelepostConfigReader instance.
        """
        base = user_dir or APP_PATHS.user_settings_dir
        return cls(
            config_path=base / "config.yaml",
            secrets_path=base / "telethon_config.yaml",
            log_config_path=base / "log_config.yaml",
        )

    def validate_files(self) -> None:
        """Validate that all required config files exist.

        Raises:
            ConfigError: If any required file is missing.
        """
        if not self.config_path.exists():
            raise ConfigError("Required config file not found", path=self.config_path)
        if not self.secrets_path.exists():
            raise ConfigError(
                "Required telethon config file not found", path=self.secrets_path
            )

    def load(self) -> TelepostSettings:
        """Load and merge config.yaml + telethon_config.yaml, validate against TelepostSettings.

        Returns:
            Validated TelepostSettings instance.

        Raises:
            ConfigError: If files are missing, malformed, or validation fails.
        """
        self.validate_files()
        config_data = _load_yaml(self.config_path)
        secrets_data = _load_yaml(self.secrets_path)
        merged = _merge_dicts(config_data, secrets_data)
        try:
            self._settings = TelepostSettings.model_validate(merged)
        except Exception as e:
            raise ConfigError(
                f"Configuration validation failed: {e}"
            ) from e
        return self._settings

    def load_logging_config(self) -> dict[str, Any]:
        """Load logging configuration from log_config.yaml.

        Resolves relative log file paths against APP_PATHS.log_dir.

        Returns:
            Logging config dict ready for logging.config.dictConfig().

        Raises:
            ConfigError: If the logging config file is missing or invalid.
        """
        path = self.log_config_path or APP_PATHS.log_config_file
        if not path.exists():
            raise ConfigError(
                "Logging configuration file not found", path=path
            )
        data = _load_yaml(path)
        # Handle LOGGING wrapper key if present
        logging_data: dict[str, Any] = data.get("LOGGING", data)
        # Resolve relative log file paths
        handlers = logging_data.get("handlers", {})
        for handler in handlers.values():
            if isinstance(handler, dict) and "filename" in handler:
                filename = handler["filename"]
                handler["filename"] = str(
                    resolve_path(filename, APP_PATHS.log_dir)
                )
        return logging_data

    @property
    def settings(self) -> TelepostSettings:
        """Return the loaded settings.

        Returns:
            The loaded TelepostSettings instance.

        Raises:
            ConfigError: If settings have not been loaded yet.
        """
        if self._settings is None:
            raise ConfigError("Settings not loaded. Call load() first.")
        return self._settings


__all__ = ["TelepostConfigReader", "resolve_path"]