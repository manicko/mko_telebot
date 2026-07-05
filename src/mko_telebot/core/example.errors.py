"""
Exception classes for mko_telepost.
"""


class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""

    pass


class GoogleSheetsServiceError(Exception):
    """Raised when Google Sheets service fails to initialize or data retrieval fails."""

    pass
