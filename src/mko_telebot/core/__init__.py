"""Core package for mko_telebot.

Provides configuration models, path management, config reader, errors,
task model, and search matching utilities.
"""

from .channels import ChannelConfig, ChannelDefaults, ChannelsConfig
from .config import TelepostConfigReader, resolve_path
from .errors import ConfigError, MkoTelebotError
from .matcher import search_match
from .models import TelepostSettings
from .paths import APP_PATHS
from .telethon import ProxyType, ProxyConfig
from .task import Task

__all__ = [
    "APP_PATHS",
    "ChannelConfig",
    "ChannelDefaults",
    "ChannelsConfig",
    "ConfigError",
    "MkoTelebotError",
    "ProxyType",
    "ProxyConfig",
    "resolve_path",
    "search_match",
    "Task",
    "TelepostConfigReader",
    "TelepostSettings",
]

