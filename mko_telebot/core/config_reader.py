from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from platformdirs import user_config_dir
from mko_telebot.core.utils import (
    load_config, resolve_path, merge_dicts
)


class WorkingPaths(BaseSettings):
    """
    Defines essential working paths for configuration and user data.
    """
    root_dir: Path = Path(__file__).resolve().parent.parent
    module_name: str = root_dir.name
    user_folder: Path = Path(user_config_dir(module_name))

    default_settings: Path = Path.joinpath(root_dir, 'settings')
    user_settings: Path = Path.joinpath(user_folder, 'settings')
    state_file: Path = Path.joinpath(user_settings, 'state.json')

    config_files: dict[str, str] = {
        "config": "config.yaml",
        "log_config": "log_config.yaml",
        "secrets": "secrets.yaml",
    }

    model_config = {
        "env_prefix": "APP_",
        "env_nested_delimiter": "__",
        "extra": "ignore"
    }


PATHS = WorkingPaths()


# Telethon API settings
class TelethonApiSettings(BaseModel):
    """
    Configuration for the Telethon API.
    """
    is_user: bool = True
    phone_or_token: str
    client: dict[str, Any]

class MonitoringSettings(BaseSettings):
    """
    Configuration for the Telegram Channels Monitoring.
    """
    forward_to: list[str, Any]
    history_limit: int = 50
    channels: list[str]
    keywords: dict[str, Any]
    scan_delay: int = 300



# Logging settings
class LoggingSettings(BaseModel):
    """
    Logging configuration.
    """
    version: int = 1
    disable_existing_loggers: bool = False
    formatters: dict[str, Any]
    handlers: dict[str, Any]
    loggers: dict[str, Any]
    root: dict[str, Any]

    @field_validator("handlers", mode="before")
    @classmethod
    def validate_paths(cls, handlers: dict[str, Any]) -> dict[str, Any]:
        """
        Ensures log file paths exist before validation.
        """
        for handler in handlers.values():
            if isinstance(handler, dict) and "filename" in handler:
                filename = handler["filename"]
                handler["filename"] = resolve_path(filename, PATHS.user_folder / "logs")
        return handlers


# Main configuration class
class Config(BaseSettings):
    """
    Main configuration class that loads and merges all configurations.
    """

    TELETHON_API: TelethonApiSettings
    LOGGING: LoggingSettings
    MONITORING: MonitoringSettings

    model_config = {
        "env_prefix": "APP_",
        "env_nested_delimiter": "__",
        "extra": "ignore"
    }

    @classmethod
    def load(cls) -> "Config":
        """
        Loads and merges configurations from `DEFAULT_SETTINGS_FOLDER` and `USER_SETTINGS_FOLDER`.
        """
        merged_config = {}
        for folder in (PATHS.root_dir, PATHS.user_folder):
            for file in PATHS.config_files.values():
                path = Path.joinpath(folder, 'settings', file)
                data = load_config(path)  # Load YAML
                merge_dicts(merged_config, data)  # Merge configs

        return cls.model_validate(merged_config)

# Load the final configuration
CONFIG = Config.load()


# print(CONFIG.TELETHON_API.client)