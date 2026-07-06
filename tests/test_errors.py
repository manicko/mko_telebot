"""Tests for the mko_telebot exception hierarchy."""

from mko_telebot.core.errors import (
    ConfigError,
    MkoTelebotError,
    StateError,
    TelegramAuthError,
    TelegramServiceError,
)


class TestMkoTelebotErrorInheritance:
    """Test that MkoTelebotError and all subclasses inherit correctly."""

    def test_mko_telebot_error_is_exception_subclass(self):
        """MkoTelebotError should inherit from Exception."""
        assert issubclass(MkoTelebotError, Exception)

    def test_config_error_inherits_from_mko_telebot_error(self):
        """ConfigError should inherit from MkoTelebotError."""
        assert issubclass(ConfigError, MkoTelebotError)

    def test_telegram_auth_error_inherits_from_mko_telebot_error(self):
        """TelegramAuthError should inherit from MkoTelebotError."""
        assert issubclass(TelegramAuthError, MkoTelebotError)

    def test_telegram_service_error_inherits_from_mko_telebot_error(self):
        """TelegramServiceError should inherit from MkoTelebotError."""
        assert issubclass(TelegramServiceError, MkoTelebotError)

    def test_state_error_inherits_from_mko_telebot_error(self):
        """StateError should inherit from MkoTelebotError."""
        assert issubclass(StateError, MkoTelebotError)


class TestConfigErrorPath:
    """Test ConfigError with optional path parameter."""

    def test_config_error_default_no_path(self):
        """ConfigError should work without a path."""
        err = ConfigError("missing config")
        assert err.path is None
        assert str(err) == "missing config"

    def test_config_error_with_path(self):
        """ConfigError should include path in message when provided."""
        from pathlib import Path

        path = Path("/some/config.yaml")
        err = ConfigError("missing config", path=path)
        assert err.path == path
        assert str(path) in str(err)
        assert "missing config" in str(err)

    def test_config_error_empty_message_with_path(self):
        """ConfigError with empty message and a path should still show path."""
        from pathlib import Path

        path = Path("/etc/mko_telebot/config.yaml")
        err = ConfigError(path=path)
        assert err.path == path
        assert str(path) in str(err)


class TestExceptionPolymorphism:
    """Test that all custom exceptions can be caught as MkoTelebotError."""

    def test_config_error_caught_as_base(self):
        """ConfigError should be catchable as MkoTelebotError."""
        try:
            raise ConfigError("config problem")
        except MkoTelebotError as exc:
            assert isinstance(exc, ConfigError)
            assert str(exc) == "config problem"

    def test_telegram_auth_error_caught_as_base(self):
        """TelegramAuthError should be catchable as MkoTelebotError."""
        try:
            raise TelegramAuthError("auth failed")
        except MkoTelebotError as exc:
            assert isinstance(exc, TelegramAuthError)
            assert str(exc) == "auth failed"

    def test_telegram_service_error_caught_as_base(self):
        """TelegramServiceError should be catchable as MkoTelebotError."""
        try:
            raise TelegramServiceError("service error")
        except MkoTelebotError as exc:
            assert isinstance(exc, TelegramServiceError)
            assert str(exc) == "service error"

    def test_state_error_caught_as_base(self):
        """StateError should be catchable as MkoTelebotError."""
        try:
            raise StateError("invalid state")
        except MkoTelebotError as exc:
            assert isinstance(exc, StateError)
            assert str(exc) == "invalid state"


class TestExceptionMessagePreservation:
    """Test that exception messages are preserved correctly."""

    def test_message_preserved_for_mko_telebot_error(self):
        """MkoTelebotError should preserve the message passed to it."""
        err = MkoTelebotError("something went wrong")
        assert str(err) == "something went wrong"

    def test_message_preserved_for_config_error(self):
        """ConfigError should preserve the message passed to it."""
        err = ConfigError("config is invalid")
        assert str(err) == "config is invalid"

    def test_message_preserved_for_telegram_auth_error(self):
        """TelegramAuthError should preserve the message."""
        err = TelegramAuthError("API key invalid")
        assert str(err) == "API key invalid"

    def test_message_preserved_for_telegram_service_error(self):
        """TelegramServiceError should preserve the message."""
        err = TelegramServiceError("timeout connecting")
        assert str(err) == "timeout connecting"

    def test_message_preserved_for_state_error(self):
        """StateError should preserve the message."""
        err = StateError("cannot proceed")
        assert str(err) == "cannot proceed"

    def test_empty_message(self):
        """Exception with empty message should work."""
        err = MkoTelebotError()
        assert str(err) == ""