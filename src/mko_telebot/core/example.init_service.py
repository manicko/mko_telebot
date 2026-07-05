"""
Init service for mko_telepost.

Handles initialization of user configuration directory with default templates.
When user runs `mko-telepost init`, this module copies template files from package
settings directory to user's config directory.
"""

import logging
import shutil
from pathlib import Path

from mko_telepost.core.paths import APP_PATHS

logger = logging.getLogger(__name__)


def _copy_templates(destination: Path, force: bool = False) -> list[Path]:
    """
    Copy template files from package settings directory to user settings directory.

    Args:
        destination: Target directory path
        force: Overwrite existing files if True

    Returns:
        List of copied file paths
    """
    source_dir = APP_PATHS.app_settings_dir
    copied_files: list[Path] = []

    if not source_dir.exists():
        raise FileNotFoundError(
            f"Template directory not found: {source_dir}. Package may be corrupted."
        )

    destination.mkdir(parents=True, exist_ok=True)

    for item in source_dir.rglob("*"):
        if item.is_dir():
            continue

        relative_path = item.relative_to(source_dir)

        # Rename credentials.template.json to credentials.json at destination
        if item.name == "credentials.template.json":
            target_path = destination / "credentials.json"
        else:
            target_path = destination / relative_path

        if target_path.exists() and not force:
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target_path)
        copied_files.append(target_path)

    return copied_files


def init_project(force: bool = False) -> Path:
    """
    Initialize user configuration directory with default templates.

    Copies template files from package settings to user's config directory.
    Creates the following structure:
        ~/.config/mko_telepost/
        ├── settings/
        │   ├── app_config.yaml   (main configuration)
        │   ├── log_config.yaml   (logging configuration)
        │   └── credentials.json  (Google API credentials - from template)

    Args:
        force: Overwrite existing files if True

    Returns:
        Path to created user settings directory

    Example:
        >>> from mko_telepost.core.init_service import init_project
        >>> path = init_project()
        >>> print(f"Config initialized at: {path}")
    """
    destination = APP_PATHS.user_settings_dir
    copied = _copy_templates(destination, force)

    if copied:
        logger.info(f"Created {len(copied)} configuration file(s) in {destination}")
    else:
        logger.info(f"Configuration files already exist in {destination}")
        logger.info("Use --force to overwrite existing files")

    return destination