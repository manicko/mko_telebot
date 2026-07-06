"""Core package for mko_telebot.

Provides configuration models, path management, config reader, errors,
task model, and search matching utilities.
"""

from .chats_config import ChannelConfig, ChannelDefaults, ChatsConfig, LogLevel
from .config_reader import TelepostConfigReader, resolve_path
from .errors import ConfigError, MkoTelebotError
from .models import TelepostSettings
from .parser import search_match
from .paths import APP_PATHS
from .task import Task

__all__ = [
    "APP_PATHS",
    "ChannelConfig",
    "ChannelDefaults",
    "ChatsConfig",
    "ConfigError",
    "LogLevel",
    "MkoTelebotError",
    "resolve_path",
    "search_match",
    "Task",
    "TelepostConfigReader",
    "TelepostSettings",
]