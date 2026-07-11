"""Telethon client configuration models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ClientConfig(BaseModel):
    """
    Configuration for Telegram client (Telethon).

    Attributes:
        api_id: Telegram API ID (from my.telegram.org)
        api_hash: Telegram API hash (from my.telegram.org)
        session: Session name or path
        app_version: Application version string
        device_model: Device model string
        system_version: System version string
        system_lang_code: System language code
        lang_code: Interface language code
        proxy: Optional SOCKS5 proxy configuration for Telethon
    """

    model_config = ConfigDict(extra="forbid")
    api_id: int = Field(..., gt=0, description="Telegram API ID")
    api_hash: SecretStr = Field(
        ..., min_length=32, max_length=64, description="Telegram API hash"
    )
    session: str = Field(default="first_session", description="Session name or path")
    app_version: str | None = Field(default=None, description="Application version")
    device_model: str | None = Field(default=None, description="Device model")
    system_version: str | None = Field(default=None, description="System version")
    system_lang_code: str | None = Field(
        default=None, description="System language code"
    )
    lang_code: str | None = Field(default=None, description="Interface language code")
    proxy: dict[str, object] | None = Field(
        default=None,
        description="Proxy configuration for Telethon. SOCKS5 format: "
        "{'proxy_type': 'socks5', 'addr': '...', 'port': int, "
        "'username': str | None, 'password': str | None}",
    )

    @field_validator("api_hash")
    @classmethod
    def validate_api_hash(cls, v: SecretStr) -> SecretStr:
        """Reject placeholder values for api_hash."""
        value = v.get_secret_value()
        if value.startswith("YOUR_") or value.startswith("PLACEHOLDER_"):
            raise ValueError(
                "api_hash appears to be a placeholder value. Replace with your actual value."
            )
        return v

    @field_validator("session", "app_version", "device_model", "system_version")
    @classmethod
    def validate_not_placeholder(cls, v: str | None) -> str | None:
        """Reject placeholder values for credential fields."""
        if v is not None and (v.startswith("YOUR_") or v.startswith("PLACEHOLDER_")):
            raise ValueError(
                f"{v} appears to be a placeholder value. Replace with your actual value."
            )
        return v

    @field_validator("api_id")
    @classmethod
    def validate_api_id(cls, v: int) -> int:
        """Reject the template sentinel value 12345 for api_id."""
        if v == 12345:
            raise ValueError(
                "api_id value 12345 is a template placeholder. "
                "Replace with your actual API ID from https://my.telegram.org/apps."
            )
        return v

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, v: dict[str, object] | None) -> dict[str, object] | None:
        """Validate proxy configuration for Telethon SOCKS5 proxy.

        Validates that the proxy dict contains required fields and valid values.
        Telethon requires python-socks[asyncio] for proxy support.

        Args:
            v: Proxy configuration dict or None.

        Returns:
            The validated proxy dict or None.

        Raises:
            ValueError: If proxy configuration is invalid.
        """
        if v is None:
            return v

        valid_types = {"socks5", "socks4", "http"}
        proxy_type = v.get("proxy_type")
        if proxy_type not in valid_types:
            raise ValueError(
                f"proxy_type must be one of {valid_types}, got '{proxy_type}'"
            )

        if "addr" not in v or not isinstance(v.get("addr"), str) or not v.get("addr"):
            raise ValueError("proxy must contain non-empty 'addr' field")

        port = v.get("port")
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise ValueError("proxy 'port' must be integer 1-65535")

        return v


class TelethonConfig(BaseModel):
    """
    Configuration for Telegram client (Telethon).

    Attributes:
        is_user: True for user account (phone auth), False for bot
        phone_or_token: Phone number (user) or bot token
        max_retries: Number of times to retry posting on failure
    """

    model_config = ConfigDict(extra="forbid")
    is_user: bool = Field(default=True, description="True for user, False for bot")
    phone_or_token: SecretStr = Field(
        ..., min_length=5, description="Phone number or bot token"
    )
    max_retries: int = Field(
        default=5, ge=1, le=20, description="Max retry attempts for sending messages"
    )
    client: ClientConfig

    @field_validator("phone_or_token")
    @classmethod
    def validate_phone_or_token(cls, v: SecretStr) -> SecretStr:
        """Reject placeholder values for phone_or_token."""
        value = v.get_secret_value()
        if value.startswith("YOUR_") or value.startswith("PLACEHOLDER_"):
            raise ValueError(
                "phone_or_token appears to be a placeholder value. "
                "Replace with your phone number or bot token."
            )
        return v


__all__ = ["ClientConfig", "TelethonConfig"]
