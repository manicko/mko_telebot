"""Root configuration model for mko_telebot."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .telethon import TelethonConfig
from .channels import ChannelsConfig


class TelepostSettings(BaseModel):
    """Root settings model for mko_telebot.

    Aggregates all configuration sections under a single model.
    Uses validation_alias for backward compatibility with uppercase YAML keys.

    Attributes:
        telethon: Telegram client configuration (Telethon).
        channels: Channel monitoring configuration.
    """

    model_config = ConfigDict(populate_by_name=True)

    telethon: TelethonConfig = Field(
        ...,
        validation_alias="TELETHON_API",
        description="Telegram client configuration",
    )
    channels: ChannelsConfig = Field(
        ...,
        validation_alias="CHANNELS",
        description="Channel monitoring configuration",
    )


__all__ = ["TelepostSettings"]
