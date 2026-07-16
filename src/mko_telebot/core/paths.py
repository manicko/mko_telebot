"""
Paths management for mko_telebot.

Provides:
- AppPaths: Pydantic model defining all application directory/file paths
- APP_PATHS: Module-level singleton instance of AppPaths
"""
from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir
from pydantic import BaseModel, ConfigDict

# Package name derived from package hierarchy
APP_NAME: str = (__package__ or "").split(".")[0]

# Absolute path to package source directory
APP_DIR: Path = Path(__file__).resolve().parent.parent

# User-specific config directory (cross-platform via platformdirs)
USER_DIR: Path = Path(user_config_dir(APP_NAME))


class AppPaths(BaseModel):
    """Application path configuration model.

    All path properties are computed from the base fields
    (app_dir, app_name, user_dir).
    """

    model_config = ConfigDict(extra="forbid")

    app_dir: Path
    app_name: str
    user_dir: Path

    @property
    def app_settings_dir(self) -> Path:
        """Directory containing default application settings."""
        return self.app_dir / "settings"

    @property
    def user_settings_dir(self) -> Path:
        """Directory containing user-specific settings."""
        return self.user_dir / "settings"

    @property
    def state_dir(self) -> Path:
        """Directory for persistent application state."""
        return self.user_settings_dir / "state"

    @property
    def session_dir(self) -> Path:
        """Directory for Telethon session files."""
        return self.user_settings_dir / "sessions"

    @property
    def log_dir(self) -> Path:
        """Directory for log files."""
        return self.user_dir / "logs"

    @property
    def config_file(self) -> Path:
        """Path to the main configuration file."""
        return self.user_settings_dir / "config.yaml"

    @property
    def telethon_config_file(self) -> Path:
        """Path to the Telethon configuration file."""
        return self.user_settings_dir / "telethon_config.yaml"

    @property
    def log_config_file(self) -> Path:
        """Path to the logging configuration file."""
        return self.user_settings_dir / "log_config.yaml"


APP_PATHS: AppPaths = AppPaths(
    app_dir=APP_DIR,
    app_name=APP_NAME,
    user_dir=USER_DIR,
)
