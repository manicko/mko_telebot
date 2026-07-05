"""
Paths management for mko_telepost.

Provides:
- APP_DIR: Package installation directory (contains default settings/templates)
- USER_DIR: User config directory (~/.config/mko_telepost/ or equivalent)
- PathResolver: Utility for resolving relative paths against base directories
"""

from pathlib import Path

from platformdirs import user_config_dir
from pydantic import BaseModel

# Package name derived from package hierarchy
APP_NAME: str = (__package__ or "").split(".")[0]

# Absolute path to package source directory
APP_DIR: Path = Path(__file__).resolve().parent.parent

# User-specific config directory (cross-platform via platformdirs)
# Windows: %APPDATA%/mko_telepost
# Linux: ~/.config/mko_telepost
# macOS: ~/Library/Application Support/mko_telepost
USER_DIR: Path = Path(user_config_dir(APP_NAME))


class PathResolver:
    """Utility for resolving relative paths against base directories."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize path resolver with base directory.

        Args:
            base_dir: Base directory for path resolution.
        """
        self.base_dir = base_dir

    def resolve(self, path: Path | str) -> Path:
        """Resolve a path relative to the base directory.

        Args:
            path: Path to resolve (can be relative or absolute).

        Returns:
            Resolved absolute path.
        """
        path = Path(path).expanduser()
        if not path.is_absolute():
            path = self.base_dir / path
        return path.resolve()

    @staticmethod
    def ensure_dir(path: Path) -> Path:
        """[PLANNED UTILITY — not consumed by production code; retained for
        future init commands. Do not remove.]

        Ensure directory exists, creating it if necessary.

        This is a utility helper for operations that require directory creation.
        Intended for future use by commands like 'mko-telepost init' to set up config
        directories, cache directories, and other storage locations.

        Args:
            path: Directory path to ensure.

        Returns:
            The same path, now guaranteed to exist.
        """
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def ensure_file_parent(path: Path) -> Path:
        """[PLANNED UTILITY — not consumed by production code; retained for
        future file-output commands. Do not remove.]

        Ensure parent directory of a file exists, creating it if necessary.

        This is a utility helper for file operations that require parent directory creation.
        Intended for future use when writing output files, logs, or cache files to
        ensure the target directory structure exists before file operations.

        Args:
            path: File path whose parent directory should be ensured.

        Returns:
            The same path, with parent directory guaranteed to exist.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class AppPaths(BaseModel):
    app_dir: Path
    app_name: str
    user_dir: Path

    @property
    def user_settings_dir(self) -> Path:
        return Path(self.user_dir / "settings")

    @property
    def app_settings_dir(self) -> Path:
        return Path(self.app_dir / "settings")

    @property
    def app_config(self) -> Path:
        return Path(self.user_settings_dir, "app_config.yaml")

    @property
    def log_config(self) -> Path:
        return Path(self.user_settings_dir, "log_config.yaml")


APP_PATHS = AppPaths(app_dir=APP_DIR, app_name=APP_NAME, user_dir=USER_DIR)