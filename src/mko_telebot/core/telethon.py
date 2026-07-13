"""Telethon client configuration models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from typing import ClassVar


class ProxyConfig(BaseModel):
    """Proxy configuration for Telethon SOCKS5/SOCKS4/HTTP proxy.

    Uses SecretStr for username and password to prevent credential exposure
    in logs and serialization.

    Attributes:
        proxy_type: Proxy type ('socks5', 'socks4', or 'http').
        addr: Proxy server address/hostname.
        port: Proxy server port (1-65535).
        rdns: Remote DNS resolution (SOCKS5 only).
        username: Proxy authentication username.
        password: Proxy authentication password.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    proxy_type: str = Field(..., description="Proxy type")
    addr: str = Field(..., description="Proxy server address")
    port: int = Field(..., ge=1, le=65535, description="Proxy server port")
    rdns: bool | None = Field(default=None, description="Remote DNS resolution")
    username: SecretStr | None = Field(default=None, description="Proxy username")
    password: SecretStr | None = Field(default=None, description="Proxy password")

    @field_validator("addr")
    @classmethod
    def validate_addr(cls, v: str) -> str:
        """Validate addr is non-empty."""
        if not v:
            raise ValueError("proxy must contain non-empty 'addr' field")
        return v

    @field_validator("proxy_type")
    @classmethod
    def validate_proxy_type(cls, v: str) -> str:
        """Validate proxy_type is one of the allowed values."""
        valid_types = {"socks5", "socks4", "http"}
        if v not in valid_types:
            raise ValueError(
                f"proxy_type must be one of {valid_types}, got '{v}'"
            )
        return v

    @field_validator("username", "password")
    @classmethod
    def validate_not_placeholder(cls, v: SecretStr | None) -> SecretStr | None:
        """Reject placeholder values for proxy credentials."""
        if v is not None:
            value = v.get_secret_value()
            if value.startswith("YOUR_") or value.startswith("PLACEHOLDER_"):
                raise ValueError(
                    f"{v} appears to be a placeholder value. "
                    "Replace with your actual value."
                )
        return v

    def to_dict(self) -> dict[str, str | int | bool]:
        """Convert to Telethon-compatible dict format.

        Returns:
            Dict with plain string values for username and password.
        """
        result: dict[str, str | int | bool] = {
            "proxy_type": self.proxy_type,
            "addr": self.addr,
            "port": self.port,
        }
        if self.rdns is not None:
            result["rdns"] = self.rdns
        if self.username is not None:
            result["username"] = self.username.get_secret_value()
        if self.password is not None:
            result["password"] = self.password.get_secret_value()
        return result


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

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
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
    proxy: ProxyConfig | None = Field(
        default=None,
        description="Proxy configuration for Telethon. Use ProxyConfig model.",
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

    @field_validator("session")
    @classmethod
    def validate_session(cls, v: str | None) -> str | None:
        """Reject placeholder and path traversal values for session field."""
        if v is None:
            return v
        if v.startswith("YOUR_") or v.startswith("PLACEHOLDER_"):
            raise ValueError(
                f"{v} appears to be a placeholder value. Replace with your actual value."
            )
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError(
                "session must not contain path traversal characters"
            )
        return v

    @field_validator("app_version", "device_model", "system_version")
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


class TelethonConfig(BaseModel):
    """
    Configuration for Telegram client (Telethon).

    Attributes:
        is_user: True for user account (phone auth), False for bot
        phone_or_token: Phone number (user) or bot token
        max_retries: Number of times to retry posting on failure
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
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


__all__ = ["ProxyConfig", "ClientConfig", "TelethonConfig"]
