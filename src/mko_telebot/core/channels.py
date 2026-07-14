"""Pydantic models for per-channel monitoring configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from typing import Any, ClassVar


class ChannelConfig(BaseModel):
    """Configuration for a single monitored channel.

    Attributes:
        name: Channel identifier (@username or t.me/...).
        forward_to: Target entities to forward messages to.
        keywords: Keyword patterns for filtering messages.
        scan_interval: Interval between scans in seconds.
        history_limit: Maximum number of historical messages to fetch.
        history_days: Number of days of history to fetch (None for no limit).
        overlap: Number of overlapping messages between scans.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    name: str = Field(..., description="Channel identifier (@username or t.me/...)")
    forward_to: list[str] = Field(
        default_factory=list, description="Target entities to forward messages to"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Keyword patterns for filtering messages"
    )
    scan_interval: int = Field(
        default=420, ge=60, description="Interval between scans in seconds"
    )
    history_limit: int = Field(
        default=50, ge=1, description="Maximum number of historical messages to fetch"
    )
    history_days: int | None = Field(
        default=None, description="Number of days of history to fetch", gt=0
    )
    overlap: int = Field(
        default=5, ge=1, description="Number of overlapping messages between scans"
    )

    @field_validator("name")
    @classmethod
    def validate_channel_name(cls, v: str) -> str:
        """Validate channel name rejects path traversal characters."""
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError(
                "Invalid channel name: contains forbidden path character"
            )
        return v


class ChannelDefaults(BaseModel):
    """Default values applied to all channels.

    Same fields as ChannelConfig minus the name field.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    forward_to: list[str] = Field(
        default_factory=list, description="Target entities to forward messages to"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Keyword patterns for filtering messages"
    )
    scan_interval: int = Field(
        default=420, ge=60, description="Interval between scans in seconds"
    )
    history_limit: int = Field(
        default=50, ge=1, description="Maximum number of historical messages to fetch"
    )
    history_days: int | None = Field(
        default=None, description="Number of days of history to fetch", gt=0
    )
    overlap: int = Field(
        default=5, ge=1, description="Number of overlapping messages between scans"
    )


class ChannelsConfig(BaseModel):
    """Configuration for channel monitoring.

    Attributes:
        defaults: Default settings applied to all channels.
        channels: Dictionary of channel configs keyed by channel name.
        channels_delay: Delay between channel scans in seconds.
        stagger_start_seconds: Stagger offset for initial scan start.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    defaults: ChannelDefaults = Field(
        default_factory=ChannelDefaults,
        description="Default settings applied to all channels",
    )
    channels: dict[str, ChannelConfig] = Field(
        ..., description="Dictionary of channel configs keyed by channel name"
    )
    channels_delay: int = Field(
        default=30, ge=1, description="Delay between channel scans in seconds"
    )
    stagger_start_seconds: int = Field(
        default=5, ge=0, description="Stagger offset for initial scan start"
    )

    @model_validator(mode="after")
    def strip_defaults_from_channels(self) -> ChannelsConfig:
        """Remove 'DEFAULTS' key from channels dict if present."""
        _ = self.channels.pop("DEFAULTS", None)
        return self

    @model_validator(mode="after")
    def apply_defaults_to_channels(self) -> ChannelsConfig:
        """Merge defaults into each channel config where fields are at default values."""
        defaults_data: dict[str, Any] = self.defaults.model_dump(exclude_none=True)  # pyright: ignore[reportExplicitAny]
        for channel_key, channel in self.channels.items():
            # Build update data from field defaults
            update_data: dict[str, Any] = {}  # pyright: ignore[reportExplicitAny]
            for field_name, default_value in defaults_data.items():  # pyright: ignore[reportAny]
                current_val: Any = getattr(channel, field_name)  # pyright: ignore[reportExplicitAny,reportAny]
                # Get the model's default for this field
                field_info = ChannelConfig.model_fields[field_name]
                # Check if field uses default_factory or has a static default
                if field_info.default_factory is not None:
                    # For default_factory fields, current_val equals the default
                    # if it's an empty list (the default_factory returns [])
                    # We still want to apply defaults in this case for list fields
                    update_data[field_name] = default_value
                elif current_val is None or current_val == field_info.default:  # pyright: ignore[reportAny]
                    update_data[field_name] = default_value
            if update_data:
                # Merge channel's current values with defaults
                merged_data: dict[str, Any] = channel.model_dump()  # pyright: ignore[reportExplicitAny]
                merged_data.update(update_data)
                self.channels[channel_key] = ChannelConfig(**merged_data)  # pyright: ignore[reportAny]
        return self


__all__ = ["ChannelConfig", "ChannelDefaults", "ChannelsConfig"]
