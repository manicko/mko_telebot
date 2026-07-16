# mko_telebot/core/utils.py
import logging
import os
import stat
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_posix() -> bool:
    """Check if the current platform supports POSIX permissions.

    Returns:
        True if running on a POSIX-compatible system (Linux, macOS, etc.).
    """
    return hasattr(os, "chmod")


def _secure_directory_permissions(dir_path: Path) -> None:
    """Set secure permissions (0700) on a directory for POSIX systems.

    Args:
        dir_path: Path to the directory to secure.
    """
    if not _is_posix():
        return  # Graceful no-op on non-POSIX systems

    try:
        os.chmod(dir_path, stat.S_IRWXU)  # 0o700: rwx for owner only
        logger.debug(f"Set secure directory permissions (0700) on {dir_path}")
    except OSError as e:
        logger.warning(f"Failed to set directory permissions on {dir_path}: {e}")


def _secure_file_permissions(file_path: Path) -> None:
    """Set secure permissions (0600) on a file for POSIX systems.

    Args:
        file_path: Path to the file to secure.
    """
    if not _is_posix():
        return  # Graceful no-op on non-POSIX systems

    try:
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600: rw for owner only
        logger.debug(f"Set secure file permissions (0600) on {file_path}")
    except OSError as e:
        logger.warning(f"Failed to set file permissions on {file_path}: {e}")


def ensure_path_exists(path: Path) -> None:
    """Ensure a path exists, creating directories with secure permissions.

    Creates parent directories with 0700 permissions and files with 0600
    permissions on POSIX systems. Silently degrades on non-POSIX systems.

    Args:
        path: Path to a file or directory.

    Raises:
        ValueError: If the path cannot be created.
    """
    try:
        if path.exists():
            return  # Path already exists, no action needed
        if path.suffix:  # If it's a file, create its parent directory
            path.parent.mkdir(parents=True, exist_ok=True)
            _secure_directory_permissions(path.parent)
        else:  # If it's a directory, create it
            path.mkdir(parents=True, exist_ok=True)
            _secure_directory_permissions(path)
    except OSError as e:
        raise ValueError(f"Failed to create path {path}: {e}") from e


__all__ = ["ensure_path_exists", "_secure_directory_permissions", "_secure_file_permissions"]