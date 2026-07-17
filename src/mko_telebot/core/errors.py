"""
Exception hierarchy for mko_telebot.

All custom exceptions inherit from MkoTelebotError.
"""

from __future__ import annotations

from pathlib import Path


class MkoTelebotError(Exception):
    """Base exception for all mko_telebot errors."""

    pass


class ConfigError(MkoTelebotError):
    """Raised when configuration is invalid or cannot be loaded."""

    def __init__(self, message: str = "", path: Path | None = None) -> None:
        """Initialize ConfigError with an optional message and path."""
        self.path = path
        if path is not None:
            super().__init__(f"{message} (path: {path})")
        else:
            super().__init__(message)


class TelegramAuthError(MkoTelebotError):
    """Raised when Telegram authentication fails."""

    pass


class TelegramServiceError(MkoTelebotError):
    """Raised when the Telegram service operation fails."""

    pass


class StateError(MkoTelebotError):
    """Raised when an operation is invalid for the current state."""

    pass
