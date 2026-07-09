"""Tests for the TelepostConfigReader configuration reader.

Tests cover construction, file validation, loading of YAML config files,
logging config loading, and merging of config.yaml + secrets.yaml.
"""

from pathlib import Path

import pytest
import yaml

from mko_telebot.core.config import TelepostConfigReader
from mko_telebot.core.errors import ConfigError
from mko_telebot.core.models import TelepostSettings
from mko_telebot.core.channels import ChannelConfig, ChannelsConfig
from mko_telebot.core.telethon import ClientConfig, TelethonConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_config_yaml() -> dict[str, object]:
    """Return a minimal valid CHANNELS config dict."""
    return {
        "CHANNELS": {
            "channels": {
                "test_channel": {
                    "name": "@test_channel",
                },
            },
        },
    }


def _valid_secrets_yaml() -> dict[str, object]:
    """Return a minimal valid TELETHON_API secrets dict."""
    return {
        "TELETHON_API": {
            "is_user": True,
            "phone_or_token": "+79123456789",
            "client": {
                "api_id": 123456,
                "api_hash": "a" * 32,
            },
        },
    }


def _valid_logging_yaml() -> dict[str, object]:
    """Return a minimal valid logging config dict."""
    return {
        "LOGGING": {
            "version": 1,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                },
            },
            "root": {
                "level": "INFO",
            },
        },
    }


def _write_yaml(path: Path, data: dict[str, object]) -> Path:
    """Write a YAML file and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# TelepostConfigReader â€” from_user_dir
# ---------------------------------------------------------------------------


class TestFromUserDir:
    """Tests for TelepostConfigReader.from_user_dir()."""

    def test_from_user_dir_creates_reader_with_default_paths(self, tmp_path: Path):
        """from_user_dir() should create a reader with paths under user_dir."""
        reader = TelepostConfigReader.from_user_dir(tmp_path)
        assert isinstance(reader, TelepostConfigReader)
        assert reader.config_path == tmp_path / "config.yaml"
        assert reader.secrets_path == tmp_path / "secrets.yaml"
        assert reader.log_config_path == tmp_path / "log_config.yaml"

    def test_from_user_dir_defaults_to_app_paths(self):
        """from_user_dir() without argument should use APP_PATHS user_settings_dir."""
        from mko_telebot.core.paths import APP_PATHS

        reader = TelepostConfigReader.from_user_dir()
        expected = APP_PATHS.user_settings_dir
        assert reader.config_path == expected / "config.yaml"
        assert reader.secrets_path == expected / "secrets.yaml"
        assert reader.log_config_path == expected / "log_config.yaml"


# ---------------------------------------------------------------------------
# TelepostConfigReader â€” validate_files
# ---------------------------------------------------------------------------


class TestValidateFiles:
    """Tests for TelepostConfigReader.validate_files()."""

    def test_validate_files_raises_error_when_config_missing(self, tmp_path: Path):
        """validate_files() should raise ConfigError if config.yaml is missing."""
        _write_yaml(tmp_path / "secrets.yaml", _valid_secrets_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        with pytest.raises(ConfigError, match="Required config file not found"):
            reader.validate_files()

    def test_validate_files_raises_error_when_secrets_missing(self, tmp_path: Path):
        """validate_files() should raise ConfigError if secrets.yaml is missing."""
        _write_yaml(tmp_path / "config.yaml", _valid_config_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        with pytest.raises(ConfigError, match="Required secrets file not found"):
            reader.validate_files()

    def test_validate_files_passes_when_all_files_exist(self, tmp_path: Path):
        """validate_files() should not raise when both files exist."""
        _write_yaml(tmp_path / "config.yaml", _valid_config_yaml())
        _write_yaml(tmp_path / "secrets.yaml", _valid_secrets_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        # Should not raise
        reader.validate_files()


# ---------------------------------------------------------------------------
# TelepostConfigReader â€” load
# ---------------------------------------------------------------------------


class TestLoad:
    """Tests for TelepostConfigReader.load()."""

    def test_load_raises_config_error_when_config_missing(self, tmp_path: Path):
        """load() should raise ConfigError when config.yaml is missing."""
        _write_yaml(tmp_path / "secrets.yaml", _valid_secrets_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        with pytest.raises(ConfigError, match="Required config file not found"):
            reader.load()

    def test_load_raises_config_error_when_secrets_missing(self, tmp_path: Path):
        """load() should raise ConfigError when secrets.yaml is missing."""
        _write_yaml(tmp_path / "config.yaml", _valid_config_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        with pytest.raises(ConfigError, match="Required secrets file not found"):
            reader.load()

    def test_load_raises_config_error_on_malformed_yaml(self, tmp_path: Path):
        """load() should raise ConfigError when a YAML file is malformed."""
        (tmp_path / "config.yaml").write_text("{invalid: yaml: broken", encoding="utf-8")
        _write_yaml(tmp_path / "secrets.yaml", _valid_secrets_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        with pytest.raises(ConfigError, match="Malformed YAML"):
            reader.load()

    def test_load_returns_telepost_settings(self, tmp_path: Path):
        """load() should return a TelepostSettings instance with valid files."""
        _write_yaml(tmp_path / "config.yaml", _valid_config_yaml())
        _write_yaml(tmp_path / "secrets.yaml", _valid_secrets_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        settings = reader.load()
        assert isinstance(settings, TelepostSettings)
        assert settings.channels.channels["test_channel"].name == "@test_channel"

    def test_load_populates_settings_property(self, tmp_path: Path):
        """load() should populate the settings property after loading."""
        _write_yaml(tmp_path / "config.yaml", _valid_config_yaml())
        _write_yaml(tmp_path / "secrets.yaml", _valid_secrets_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        reader.load()
        assert isinstance(reader.settings, TelepostSettings)

    def test_settings_property_raises_before_load(self, tmp_path: Path):
        """settings property should raise ConfigError before load() is called."""
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        with pytest.raises(ConfigError, match="Settings not loaded"):
            _ = reader.settings


# ---------------------------------------------------------------------------
# TelepostConfigReader â€” merged config
# ---------------------------------------------------------------------------


class TestMergedConfig:
    """Tests for merging config.yaml + secrets.yaml."""

    def test_merged_config_contains_both_sections(self, tmp_path: Path):
        """Merged config should contain both CHANNELS and TELETHON_API data."""
        _write_yaml(tmp_path / "config.yaml", _valid_config_yaml())
        _write_yaml(tmp_path / "secrets.yaml", _valid_secrets_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        settings = reader.load()
        # CHANNELS section
        assert settings.channels.channels["test_channel"].name == "@test_channel"
        # TELETHON_API section
        assert settings.telethon.is_user is True
        assert settings.telethon.client.api_id == 123456

    def test_secrets_overlay_config_defaults(self, tmp_path: Path):
        """Secrets values should overlay config values when keys overlap."""
        config_data: dict[str, object] = {
            "CHANNELS": {
                "channels": {
                    "test_channel": {
                        "name": "@test_channel",
                    },
                },
            },
        }
        secrets_data: dict[str, object] = {
            "CHANNELS": {
                "channels_delay": 60,
            },
            "TELETHON_API": {
                "is_user": False,
                "phone_or_token": "123456:ABCdef",
                "client": {
                    "api_id": 123456,
                    "api_hash": "b" * 32,
                },
            },
        }
        _write_yaml(tmp_path / "config.yaml", config_data)
        _write_yaml(tmp_path / "secrets.yaml", secrets_data)
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        settings = reader.load()
        # Overlay value from secrets
        assert settings.channels.channels_delay == 60
        # Original value from config still present
        assert settings.channels.channels["test_channel"].name == "@test_channel"
        # Bot token from secrets
        assert settings.telethon.is_user is False


# ---------------------------------------------------------------------------
# TelepostConfigReader â€” load_logging_config
# ---------------------------------------------------------------------------


class TestLoadLoggingConfig:
    """Tests for TelepostConfigReader.load_logging_config()."""

    def test_load_logging_config_raises_error_when_missing(self, tmp_path: Path):
        """load_logging_config() should raise ConfigError when file is missing."""
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
            log_config_path=tmp_path / "log_config.yaml",
        )
        with pytest.raises(
            ConfigError, match="Logging configuration file not found"
        ):
            reader.load_logging_config()

    def test_load_logging_config_returns_dict(self, tmp_path: Path):
        """load_logging_config() should return a logging config dict."""
        _write_yaml(tmp_path / "log_config.yaml", _valid_logging_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
            log_config_path=tmp_path / "log_config.yaml",
        )
        log_config = reader.load_logging_config()
        assert isinstance(log_config, dict)
        assert log_config["version"] == 1

    def test_load_logging_config_strips_logging_wrapper(self, tmp_path: Path):
        """load_logging_config() should strip the LOGGING wrapper key."""
        _write_yaml(tmp_path / "log_config.yaml", _valid_logging_yaml())
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
            log_config_path=tmp_path / "log_config.yaml",
        )
        log_config = reader.load_logging_config()
        # The LOGGING key should be stripped; root handler should be top-level
        assert "LOGGING" not in log_config
        assert "root" in log_config

    def test_load_logging_config_without_logging_wrapper(self, tmp_path: Path):
        """load_logging_config() should work without the LOGGING wrapper."""
        data: dict[str, object] = {
            "version": 1,
            "root": {"level": "DEBUG"},
        }
        _write_yaml(tmp_path / "log_config.yaml", data)
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
            log_config_path=tmp_path / "log_config.yaml",
        )
        log_config = reader.load_logging_config()
        assert log_config["version"] == 1
        assert log_config["root"]["level"] == "DEBUG"

    def test_load_logging_config_resolves_relative_paths(self, tmp_path: Path):
        """load_logging_config() should resolve relative log file paths."""
        data: dict[str, object] = {
            "LOGGING": {
                "version": 1,
                "handlers": {
                    "file": {
                        "class": "logging.FileHandler",
                        "filename": "mko_telebot.log",
                        "formatter": "default",
                    },
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["file"],
                },
            },
        }
        _write_yaml(tmp_path / "log_config.yaml", data)
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
            log_config_path=tmp_path / "log_config.yaml",
        )
        log_config = reader.load_logging_config()
        file_handler = log_config["handlers"]["file"]
        resolved = Path(file_handler["filename"])
        assert resolved.is_absolute()
        assert resolved.name == "mko_telebot.log"


# ---------------------------------------------------------------------------
# TelepostConfigReader â€” malformed / edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for TelepostConfigReader."""

    def test_load_raises_on_empty_yaml(self, tmp_path: Path):
        """load() should raise ConfigError when a YAML file is empty."""
        _write_yaml(tmp_path / "config.yaml", _valid_config_yaml())
        (tmp_path / "secrets.yaml").write_text("", encoding="utf-8")
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        with pytest.raises(
            ConfigError, match="Expected a top-level mapping in YAML file"
        ):
            reader.load()

    def test_load_raises_on_invalid_yaml_type(self, tmp_path: Path):
        """load() should raise ConfigError when YAML is not a dict."""
        _write_yaml(tmp_path / "config.yaml", _valid_config_yaml())
        (tmp_path / "secrets.yaml").write_text("[1, 2, 3]", encoding="utf-8")
        reader = TelepostConfigReader(
            config_path=tmp_path / "config.yaml",
            secrets_path=tmp_path / "secrets.yaml",
        )
        with pytest.raises(
            ConfigError, match="Expected a top-level mapping in YAML file"
        ):
            reader.load()

# ---------------------------------------------------------------------------
# Pydantic model validators
# ---------------------------------------------------------------------------


class TestValidators:
    """Tests for Pydantic model validators in telethon.py and channels.py."""

    @pytest.mark.parametrize(
        ("field_kwargs", "match_pattern"),
        [
            pytest.param(
                {"api_hash": "YOUR_API_HASH"},
                "placeholder",
                id="rejects_placeholder_api_hash",
            ),
            pytest.param(
                {"api_id": 12345},
                "template placeholder",
                id="rejects_template_api_id",
            ),
        ],
    )
    def test_rejects_invalid_api_credentials(
        self, field_kwargs: dict[str, object], match_pattern: str
    ) -> None:
        """ClientConfig should reject invalid credential values."""
        valid_fields: dict[str, object] = {
            "api_id": 123456,
            "api_hash": "a" * 32,
        }
        merged = {**valid_fields, **field_kwargs}
        with pytest.raises(ValueError, match=match_pattern):
            ClientConfig(**merged)

    def test_rejects_placeholder_phone_or_token(self) -> None:
        """TelethonConfig should reject placeholder phone_or_token."""
        valid_client = ClientConfig(api_id=123456, api_hash="a" * 32)
        with pytest.raises(ValueError, match="placeholder"):
            TelethonConfig(
                is_user=True,
                phone_or_token="YOUR_PHONE",
                client=valid_client,
            )

    def test_defaults_stripping(self) -> None:
        """ChannelsConfig should remove DEFAULTS key from channels dict."""
        channel = ChannelConfig(name="@test")
        config = ChannelsConfig(
            channels={
                "DEFAULTS": channel,
                "real_channel": channel,
            }
        )
        assert "DEFAULTS" not in config.channels
        assert "real_channel" in config.channels
