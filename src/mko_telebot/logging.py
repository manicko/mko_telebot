"""Centralized logging setup for mko_telebot.

Provides setup_logging() that loads logging configuration from log_config.yaml
via TelepostConfigReader and applies it using logging.config.dictConfig().
Falls back to basicConfig if the config file is missing.
"""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any

from mko_telebot.core.config import TelepostConfigReader
from mko_telebot.core.errors import ConfigError
from mko_telebot.core.paths import APP_PATHS

logger = logging.getLogger(__name__)


def setup_logging(config_path: Path | None = None) -> None:
    """Configure logging from log_config.yaml or fall back to basicConfig.

    Loads the logging configuration YAML via TelepostConfigReader and applies
    it with logging.config.dictConfig(). If the config file is missing or
    cannot be loaded, falls back to logging.basicConfig(level=logging.INFO).

    Args:
        config_path: Optional explicit path to log_config.yaml.
            If None, uses the default from APP_PATHS.
    """
    reader = TelepostConfigReader(
        config_path=APP_PATHS.config_file,
        secrets_path=APP_PATHS.telethon_config_file,
        log_config_path=config_path,
    )
    try:
        logging_config: dict[str, Any] = reader.load_logging_config()
    except ConfigError:
        logging.basicConfig(level=logging.INFO)
        logger.info("No logging config file found; using basicConfig(level=INFO)")
        return

    logging.config.dictConfig(logging_config)
    logger.info("Logging configured from log_config.yaml")


__all__ = ["setup_logging"]