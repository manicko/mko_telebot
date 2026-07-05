"""
Pydantic models for mko_telepost configuration.
Provides validated configuration models for:
- Google Sheets integration
- Telegram client (Telethon)
- Chat configurations
- Humanization delays
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mko_telepost.core.chat_models import ChatConfig, ChatDefaults, ChatsConfig, HumanizationConfig
from mko_telepost.core.google_sheets_models import GoogleSheetsConfig
from mko_telepost.core.telethon_models import TelethonConfig
from mko_telepost.core.telethon_models import ClientConfig

# Re-export for backward compatibility
__all__ = [
    "TelepostSettings",
    "GoogleSheetsConfig",
    "TelethonConfig",
    "ClientConfig",
    "ChatConfig",
    "ChatDefaults",
    "ChatsConfig",
    "HumanizationConfig",
]


# =============================================================================
# Root Configuration
# =============================================================================
class TelepostSettings(BaseModel):
    """
    Root configuration for mko_telepost.

    Combines all configuration sections into a single validated model.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )
    google_sheets: GoogleSheetsConfig
    telethon: TelethonConfig
    chats: ChatsConfig = Field(
        ...,  # Required - no placeholder default
        description="Chat configuration with global defaults and per-chat overrides",
    )
    content_dir: Path | None = Field(
        default=None,
        description="Base directory for photo content (defaults to user config directory)",
    )
    allow_absolute_paths: bool = Field(
        default=False,
        description="Allow absolute photo paths from Google Sheets (security risk)",
    )
    humanization: HumanizationConfig = Field(
        default_factory=HumanizationConfig,
        description="Human-like delay configuration",
    )

    @model_validator(mode="after")
    def resolve_chat_defaults(self) -> TelepostSettings:
        """
        Fill None fields in each chat from global defaults.

        Resolves each chat's None fields from chats.defaults.

        Post-condition: every ChatConfig in chats.chats has concrete (non-None) values for
        min_delay_minutes, delay_jitter_percent, max_photos, max_width, max_height.
        Downstream consumers MUST read these fields directly and MUST NOT re-check for None.
        """
        for chat in self.chats.chats:
            if chat.min_delay_minutes is None:
                chat.min_delay_minutes = self.chats.defaults.min_delay_minutes
            if chat.delay_jitter_percent is None:
                chat.delay_jitter_percent = self.chats.defaults.delay_jitter_percent
            if chat.max_photos is None:
                chat.max_photos = self.chats.defaults.max_photos
            if chat.max_width is None:
                chat.max_width = self.chats.defaults.max_width
            if chat.max_height is None:
                chat.max_height = self.chats.defaults.max_height
        return self

    def get_all_range_names(self) -> set[str]:
        """Collect all unique range names from all chats."""
        ranges: set[str] = set()
        for chat in self.chats.chats:
            ranges.update(chat.range_names)
        return ranges
