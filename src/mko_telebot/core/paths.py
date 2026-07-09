"""
Paths management for mko_telebot.

Provides:
- AppPaths: Pydantic model defining all application directory/file paths
- PathResolver: Utility class for resolving relative paths and ensuring directories
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


class PathResolver:
    """Utility for resolving relative paths and ensuring directories exist."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize with a base directory for relative path resolution.

        Args:
            base_dir: Base directory to resolve relative paths against.
        """
        self.base_dir = base_dir

    def resolve(self, path: Path | str) -> Path:
        """Resolve a path, handling relative paths and home-directory expansion.

        Args:
            path: Path to resolve.

        Returns:
            Resolved absolute Path.
        """
        path = Path(path).expanduser()
        if not path.is_absolute():
            path = self.base_dir / path
        return path.resolve()

    @staticmethod
    def ensure_dir(path: Path) -> Path:
        """Ensure a directory exists, creating parent directories as needed.

        Args:
            path: Directory path to ensure.

        Returns:
            The same path, now guaranteed to exist.
        """
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def ensure_file_parent(path: Path) -> Path:
        """Ensure the parent directory of a file exists.

        Args:
            path: File path whose parent directory should be ensured.

        Returns:
            The same path with parent directory guaranteed to exist.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


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
    def secrets_file(self) -> Path:
        """Path to the secrets configuration file."""
        return self.user_settings_dir / "secrets.yaml"

    @property
    def log_config_file(self) -> Path:
        """Path to the logging configuration file."""
        return self.user_settings_dir / "log_config.yaml"


APP_PATHS: AppPaths = AppPaths(
    app_dir=APP_DIR,
    app_name=APP_NAME,
    user_dir=USER_DIR,
)
