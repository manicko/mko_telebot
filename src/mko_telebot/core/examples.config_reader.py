"""
Configuration reader for mko_telepost.

Loads and validates user configuration from YAML files in user settings directory.
Supports configuration files:
- app_config.yaml: main application settings
- log_config.yaml: logging configuration
"""

import copy
import logging
from pathlib import Path

import pydantic

from mko_telepost.core.errors import ConfigError
from mko_telepost.core.models import TelepostSettings
from mko_telepost.core.paths import APP_PATHS, PathResolver
from mko_telepost.core.utils import yaml_to_dict

logger = logging.getLogger(__name__)


class TelepostConfigReader:
    """
    Configuration reader for mko_telepost.

    Loads configuration from user settings directory and validates against
    Pydantic models.

    Attributes:
        resolver: PathResolver for handling relative paths
        config_path: Path to main config file
        log_config_path: Path to logging config file

    Example:
        # >>> reader = TelepostConfigReader()
        # >>> settings = reader.load()
        # >>> print(f"Chats: {len(settings.chats)}")
    """

    def __init__(
        self,
        config_path: Path | None = None,
        log_config_path: Path | None = None,
    ):
        """
        Initialize config reader.

        Args:
            config_path: Path to app_config.yaml (defaults to user_settings_dir/app_config.yaml)
            log_config_path: Path to log_config.yaml (defaults to user_settings_dir/log_config.yaml)
        """
        self.config_path: Path = config_path or APP_PATHS.app_config
        self.log_config_path: Path = log_config_path or APP_PATHS.log_config

        # Always resolve relative paths against APP_PATHS.user_dir (single source of truth)
        self.resolver = PathResolver(APP_PATHS.user_dir)

        self._settings: TelepostSettings | None = None

    def _resolve_path(self, path: Path) -> Path:
        """Resolve path relative to user settings directory."""
        return self.resolver.resolve(path)

    def _load_yaml(self, path: Path) -> dict[str, object]:
        """Load YAML file with error handling."""
        resolved = self._resolve_path(path)

        if not resolved.exists():
            raise ConfigError(
                f"Configuration file not found: {resolved}\n"
                f"Run 'mko-telepost init' to create default configuration."
            )

        data = yaml_to_dict(resolved)
        if data is None:
            raise ConfigError(f"Failed to parse configuration file: {resolved}")

        return data

    def load(self) -> TelepostSettings:
        """
        Load and validate configuration.

        In Pydantic v2, model_validate() runs the full validation pipeline
        including @model_validator(mode="after") validators.

        Returns:
            Validated TelepostSettings instance

        Raises:
            ConfigError: If configuration is invalid or cannot be loaded
        """
        logger.debug(f"Loading configuration from: {self.config_path}")

        try:
            config_data = self._load_yaml(self.config_path)
            self._settings = self._validate_settings(config_data)

            self._resolve_settings_paths()

            return self._settings

        except ConfigError:
            raise
        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}") from None

    def _resolve_settings_paths(self) -> None:
        """Resolve relative paths in settings to absolute paths."""
        if self._settings is None:
            return

        if not self._settings.google_sheets.credentials_file.is_absolute():
            self._settings.google_sheets.credentials_file = (
                APP_PATHS.user_dir / self._settings.google_sheets.credentials_file
            )
        if not self._settings.google_sheets.token_file.is_absolute():
            self._settings.google_sheets.token_file = (
                APP_PATHS.user_dir / self._settings.google_sheets.token_file
            )
        if self._settings.content_dir and not self._settings.content_dir.is_absolute():
            self._settings.content_dir = APP_PATHS.user_dir / self._settings.content_dir

    @staticmethod
    def _validate_settings(config_data: dict[str, object]) -> TelepostSettings:
        """
        Validate configuration data and return TelepostSettings instance.

        Uses model_validate() which in Pydantic v2 runs the full validation
        pipeline including @model_validator(mode="after") validators.

        Args:
            config_data: Raw configuration dictionary from YAML

        Returns:
            Validated TelepostSettings instance

        Raises:
            ConfigError: If configuration is invalid
        """
        try:
            return TelepostSettings.model_validate(config_data)
        except pydantic.ValidationError as e:
            error_details = []
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                error_type = error["type"]
                error_details.append(f"{loc}: {error_type}")
            sanitized_msg = f"Invalid configuration: {'; '.join(error_details)}"
            raise ConfigError(sanitized_msg) from None

    def load_logging_config(self) -> dict[str, object]:
        """
        Load logging configuration with resolved paths.

        Returns:
            Dictionary with logging configuration
        """
        try:
            config = self._load_yaml(self.log_config_path)
            # Resolve relative paths in handlers
            config = self._resolve_log_paths(config)
            return config
        except ConfigError:
            logger.warning("Logging config not found, using defaults")
            return self._default_logging_config()

    def _resolve_log_paths(self, config: dict[str, object]) -> dict[str, object]:
        """
        Resolve relative file paths in logging handler configurations
        and ensure parent directories exist.

        Args:
            config: Logging configuration dict

        Returns:
            Config with resolved file paths
        """
        config_copy = copy.deepcopy(config)

        handlers = config_copy.get("handlers", {})
        if isinstance(handlers, dict):
            for handler_config in handlers.values():
                if isinstance(handler_config, dict) and "filename" in handler_config:
                    filename = handler_config["filename"]
                    if isinstance(filename, str) and not Path(filename).is_absolute():
                        filename = str(
                            self.resolver.resolve(Path(filename))
                        )
                        handler_config["filename"] = filename
                    # Ensure parent directory for the log file exists
                    if isinstance(filename, str):
                        PathResolver.ensure_file_parent(Path(filename))
        return config_copy

    @staticmethod
    def _default_logging_config() -> dict[str, object]:
        """Return minimal logging configuration."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "loggers": {
                "mko_telepost": {
                    "level": "INFO",
                    "propagate": False,
                    "handlers": ["console"],
                },
                "telethon": {
                    "level": "WARNING",
                    "propagate": False,
                    "handlers": ["console"],
                },
            },
            "root": {"level": "WARNING", "handlers": ["console"]},
        }

    def validate_files(self) -> list[str]:
        """
        Validate that required files exist and are accessible.

        Returns:
            List of validation errors (empty if all OK)
        """
        errors: list[str] = []

        # Check config exists
        config_resolved = self._resolve_path(self.config_path)
        if not config_resolved.exists():
            errors.append(f"Config file not found: {config_resolved}")

        # Check credentials file
        if self._settings:
            creds_path = self._resolve_path(
                self._settings.google_sheets.credentials_file
            )
            if not creds_path.exists():
                errors.append(f"Credentials file not found: {creds_path}")

        return errors

    @classmethod
    def from_user_dir(cls) -> TelepostConfigReader:
        """Create reader configured for the user's config directory.

        Canonical entry point for loading configuration from the default user
        directory (~/.config/mko_telepost/settings/). Used by the CLI when no
        custom --config path is provided.

        Returns:
            TelepostConfigReader instance configured with default user directory paths.
        """
        return cls()
