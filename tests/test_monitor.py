"""Tests for the monitor module — Telegram client creation, auth, message forwarding, and keyword processing."""

from __future__ import annotations

import asyncio
import itertools
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mko_telebot.core.errors import StateError, TelegramServiceError
from mko_telebot.monitor_client import (
    build_message_link,
    build_sender_tag,
    create_client,
    start_client,
)
from mko_telebot.monitor_forward import forward_to_users, process_messages
from mko_telebot.monitor import process_and_reschedule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_msg_stub(
    msg_id: int,
    text: str = "",
    grouped_id: int | None = None,
    has_media: bool = False,
    media_caption: str | None = None,
) -> MagicMock:
    """Create a mock Telethon message with given attributes and async get_sender."""
    msg = MagicMock()
    msg.id = msg_id
    msg.message = text
    msg.grouped_id = grouped_id
    msg.get_sender = AsyncMock(return_value=None)
    if has_media:
        media = MagicMock()
        media.caption = media_caption
        msg.media = media
    else:
        msg.media = None
    return msg


def _make_msg_with_link(msg_id: int, username: str) -> MagicMock:
    """Create a mock message with a chat username (for link building)."""
    msg = _make_msg_stub(msg_id)
    msg.chat.username = username
    return msg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock Telethon client with async method stubs."""
    client = MagicMock()
    client.start = AsyncMock()
    client.send_message = AsyncMock()
    client.send_file = AsyncMock()
    client.get_entity = AsyncMock()
    client.iter_messages = MagicMock()
    return client


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock TelepostSettings with default telethon config."""
    settings = MagicMock()
    settings.telethon.is_user = True
    settings.telethon.phone_or_token.get_secret_value.return_value = "+1234567890"
    settings.telethon.password = None
    settings.telethon.max_retries = 3

    # Set up client attributes for create_client
    settings.telethon.client.api_id = 123456
    settings.telethon.client.api_hash.get_secret_value.return_value = (
        "test_hash_abcdef123456"
    )
    settings.telethon.client.session = "test_session"
    settings.telethon.client.proxy = None
    settings.telethon.client.app_version = "1.0.0"
    settings.telethon.client.device_model = None
    settings.telethon.client.system_version = None
    settings.telethon.client.lang_code = "en"
    settings.telethon.client.system_lang_code = "en"
    return settings


@pytest.fixture
def mock_task() -> MagicMock:
    """Create a mock Task with forwarding targets and keywords."""
    task = MagicMock()
    task.channel_name = "@test_channel"
    task.forward_to_entities = [MagicMock(), MagicMock()]
    task.keywords = ['"test"', '"keyword"']
    task.last_msg_id = 0
    task.overlap = 5
    task.offset_date = None
    task.history_limit = 50
    return task


# ---------------------------------------------------------------------------
# create_client
# ---------------------------------------------------------------------------


class TestCreateClient:
    """Tests for create_client()."""

    def test_resolves_session_path_without_suffix(self, tmp_path: Path) -> None:
        """create_client() should append .session suffix and resolve under session_dir."""
        session_dir = tmp_path / "sessions"
        with (
            patch("mko_telebot.monitor_client.APP_PATHS") as mock_paths,
            patch("mko_telebot.monitor_client.TelegramClient") as mock_tc,
        ):
            mock_paths.session_dir = session_dir
            settings = MagicMock()
            settings.telethon.client.api_id = 123456
            settings.telethon.client.api_hash.get_secret_value.return_value = "hash"
            settings.telethon.client.session = "my_session"
            settings.telethon.client.proxy = None
            settings.telethon.client.app_version = None
            settings.telethon.client.device_model = None
            settings.telethon.client.system_version = None
            settings.telethon.client.lang_code = None
            settings.telethon.client.system_lang_code = None
            create_client(settings)

        expected_path = str(session_dir / "my_session.session")
        mock_tc.assert_called_once()
        _, kwargs = mock_tc.call_args
        assert kwargs["session"] == expected_path
        assert session_dir.exists()

    def test_resolves_session_path_with_suffix(self, tmp_path: Path) -> None:
        """create_client() should keep existing .session suffix."""
        session_dir = tmp_path / "sessions"
        with (
            patch("mko_telebot.monitor_client.APP_PATHS") as mock_paths,
            patch("mko_telebot.monitor_client.TelegramClient") as mock_tc,
        ):
            mock_paths.session_dir = session_dir
            settings = MagicMock()
            settings.telethon.client.api_id = 123456
            settings.telethon.client.api_hash.get_secret_value.return_value = "hash"
            settings.telethon.client.session = "custom.session"
            settings.telethon.client.proxy = None
            settings.telethon.client.app_version = None
            settings.telethon.client.device_model = None
            settings.telethon.client.system_version = None
            settings.telethon.client.lang_code = None
            settings.telethon.client.system_lang_code = None
            create_client(settings)

        expected_path = str(session_dir / "custom.session")
        mock_tc.assert_called_once()
        _, kwargs = mock_tc.call_args
        assert kwargs["session"] == expected_path

    def test_passes_config_through(self) -> None:
        """create_client() should pass all client config to TelegramClient."""
        with (
            patch("mko_telebot.monitor_client.APP_PATHS") as mock_paths,
            patch("mko_telebot.monitor_client.TelegramClient") as mock_tc,
        ):
            mock_paths.session_dir = Path("/tmp/sessions")
            settings = MagicMock()
            settings.telethon.client.api_id = 999888
            settings.telethon.client.api_hash.get_secret_value.return_value = (
                "test_hash_value"
            )
            settings.telethon.client.session = "s1"
            settings.telethon.client.app_version = "1.0.0"
            settings.telethon.client.device_model = "TestDevice"
            settings.telethon.client.system_version = "TestOS"
            settings.telethon.client.lang_code = "en"
            settings.telethon.client.system_lang_code = "en"
            settings.telethon.client.proxy = None
            create_client(settings)

        mock_tc.assert_called_once()
        _, kwargs = mock_tc.call_args
        assert kwargs["api_id"] == 999888
        assert kwargs["api_hash"] == "test_hash_value"
        assert kwargs["app_version"] == "1.0.0"

    def test_unwraps_secretstr_api_hash(self) -> None:
        """create_client() should unwrap SecretStr api_hash."""
        with (
            patch("mko_telebot.monitor_client.APP_PATHS") as mock_paths,
            patch("mko_telebot.monitor_client.TelegramClient") as mock_tc,
        ):
            mock_paths.session_dir = Path("/tmp/sessions")
            settings = MagicMock()
            settings.telethon.client.api_id = 111222
            settings.telethon.client.api_hash.get_secret_value.return_value = (
                "real_secret_hash_value"
            )
            settings.telethon.client.session = "secret_session"
            settings.telethon.client.proxy = None
            settings.telethon.client.app_version = None
            settings.telethon.client.device_model = None
            settings.telethon.client.system_version = None
            settings.telethon.client.lang_code = None
            settings.telethon.client.system_lang_code = None
            create_client(settings)

        mock_tc.assert_called_once()
        _, kwargs = mock_tc.call_args
        # api_hash should be a plain string, not a SecretStr object
        assert kwargs["api_hash"] == "real_secret_hash_value"
        assert isinstance(kwargs["api_hash"], str)

    def test_handles_proxy_config(self) -> None:
        """create_client() should convert ProxyConfig to dict for Telethon."""
        with (
            patch("mko_telebot.monitor_client.APP_PATHS") as mock_paths,
            patch("mko_telebot.monitor_client.TelegramClient") as mock_tc,
        ):
            mock_paths.session_dir = Path("/tmp/sessions")
            settings = MagicMock()
            settings.telethon.client.api_id = 123456
            settings.telethon.client.api_hash.get_secret_value.return_value = "hash"
            settings.telethon.client.session = "test_session"
            settings.telethon.client.app_version = None
            settings.telethon.client.device_model = None
            settings.telethon.client.system_version = None
            settings.telethon.client.lang_code = None
            settings.telethon.client.system_lang_code = None

            # Create mock ProxyConfig with to_dict method
            mock_proxy = MagicMock()
            mock_proxy.to_dict.return_value = {
                "proxy_type": "socks5",
                "addr": "proxy.example.com",
                "port": 1080,
                "username": "user",
                "password": "pass",
            }
            settings.telethon.client.proxy = mock_proxy
            create_client(settings)

        mock_tc.assert_called_once()
        _, kwargs = mock_tc.call_args
        assert kwargs["proxy"]["proxy_type"] == "socks5"
        assert kwargs["proxy"]["addr"] == "proxy.example.com"
        mock_proxy.to_dict.assert_called_once()


# ---------------------------------------------------------------------------
# start_client
# ---------------------------------------------------------------------------


class TestStartClient:
    """Tests for start_client()."""

    async def test_auth_success_user(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should start with phone for user accounts."""
        mock_settings.telethon.is_user = True
        result = await start_client(mock_client, mock_settings)
        assert result is True
        mock_client.start.assert_awaited_once_with(
            phone=mock_settings.telethon.phone_or_token.get_secret_value(),
            password="",
        )

    async def test_auth_success_user_with_password(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should pass password when configured for user accounts."""
        from pydantic import SecretStr

        mock_settings.telethon.is_user = True
        mock_settings.telethon.password = SecretStr("my_2fa_password")
        result = await start_client(mock_client, mock_settings)
        assert result is True
        mock_client.start.assert_awaited_once_with(
            phone=mock_settings.telethon.phone_or_token.get_secret_value(),
            password="my_2fa_password",
        )

    async def test_auth_success_bot(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should start with bot_token for bot accounts."""
        mock_settings.telethon.is_user = False
        result = await start_client(mock_client, mock_settings)
        assert result is True
        mock_client.start.assert_awaited_once_with(
            bot_token=mock_settings.telethon.phone_or_token.get_secret_value()
        )

    async def test_auth_failure_telethon_auth_error(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should return False on Telethon auth errors."""
        from telethon.errors import AuthKeyUnregisteredError

        mock_client.start.side_effect = AuthKeyUnregisteredError("Auth failed")
        result = await start_client(mock_client, mock_settings)
        assert result is False

    async def test_auth_failure_2fa_error(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should raise TelegramAuthError on 2FA errors."""
        from mko_telebot.core.errors import TelegramAuthError
        from telethon.errors import SessionPasswordNeededError

        mock_client.start.side_effect = SessionPasswordNeededError("2FA required")
        with pytest.raises(TelegramAuthError, match="2FA password required"):
            await start_client(mock_client, mock_settings)

    async def test_auth_failure_rpc_error(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should return False on RPC errors."""
        from telethon.errors import RPCError

        mock_client.start.side_effect = RPCError(
            request="TestRequest", message="RPC error"
        )
        result = await start_client(mock_client, mock_settings)
        assert result is False

    async def test_auth_failure_connection_error(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should return False on connection errors."""
        mock_client.start.side_effect = ConnectionError("Connection failed")
        result = await start_client(mock_client, mock_settings)
        assert result is False


# ---------------------------------------------------------------------------
# build_message_link
# ---------------------------------------------------------------------------


class TestBuildMessageLink:
    """Tests for build_message_link()."""

    def test_returns_link_when_chat_has_username(self) -> None:
        """build_message_link() should return t.me link when chat has username."""
        msg = MagicMock()
        msg.id = 42
        msg.chat.username = "test_channel"
        result = build_message_link(msg)
        assert result == "https://t.me/test_channel/42"

    def test_returns_none_when_chat_has_no_username(self) -> None:
        """build_message_link() should return None when chat has no username."""
        msg = MagicMock()
        msg.id = 42
        msg.chat.username = None
        result = build_message_link(msg)
        assert result is None

    def test_returns_none_when_chat_is_none(self) -> None:
        """build_message_link() should return None when chat attribute is None."""
        msg = MagicMock()
        msg.chat = None
        result = build_message_link(msg)
        assert result is None

    def test_returns_none_when_chat_not_present(self) -> None:
        """build_message_link() should return None when chat attribute is absent."""
        msg = MagicMock(spec=[])  # has no chat attribute at all
        result = build_message_link(msg)
        assert result is None


# ---------------------------------------------------------------------------
# build_sender_tag
# ---------------------------------------------------------------------------


class TestBuildSenderTag:
    """Tests for build_sender_tag()."""

    async def test_returns_username_when_available(self) -> None:
        """build_sender_tag() should return @username when sender has username."""
        msg = MagicMock()
        sender = MagicMock()
        sender.username = "john_doe"
        msg.get_sender = AsyncMock(return_value=sender)
        result = await build_sender_tag(msg)
        assert result == "@john_doe"

    async def test_returns_full_name_when_no_username(self) -> None:
        """build_sender_tag() should return 'First Last' when no username."""
        msg = MagicMock()
        sender = MagicMock()
        sender.username = None
        sender.first_name = "John"
        sender.last_name = "Doe"
        msg.get_sender = AsyncMock(return_value=sender)
        result = await build_sender_tag(msg)
        assert result == "John Doe"

    async def test_returns_first_name_only_when_no_last_name(self) -> None:
        """build_sender_tag() should return only first_name when last_name is None."""
        msg = MagicMock()
        sender = MagicMock()
        sender.username = None
        sender.first_name = "John"
        sender.last_name = None
        msg.get_sender = AsyncMock(return_value=sender)
        result = await build_sender_tag(msg)
        assert result == "John"

    async def test_returns_empty_string_when_sender_is_none(self) -> None:
        """build_sender_tag() should return '' when get_sender returns None."""
        msg = MagicMock()
        msg.get_sender = AsyncMock(return_value=None)
        result = await build_sender_tag(msg)
        assert result == ""

    async def test_returns_empty_on_rpc_error(self) -> None:
        """build_sender_tag() should return '' when RPCError occurs."""
        from telethon.errors import RPCError

        msg = MagicMock()
        msg.get_sender = AsyncMock(side_effect=RPCError(MagicMock(), "Error"))
        result = await build_sender_tag(msg)
        assert result == ""

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_timed_out_error(self, mock_sleep: AsyncMock) -> None:
        """build_sender_tag() should retry on TimedOutError and succeed on second attempt."""
        from telethon.errors import TimedOutError

        msg = MagicMock()
        sender = MagicMock()
        sender.username = "retry_user"
        msg.get_sender = AsyncMock(
            side_effect=itertools.cycle(
                [TimedOutError(request=None, message="Timed out"), sender]
            )
        )
        msg.id = 123
        result = await build_sender_tag(msg)
        assert result == "@retry_user"
        # Should be called twice (first attempt fails, second succeeds)
        assert msg.get_sender.await_count == 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_server_error(self, mock_sleep: AsyncMock) -> None:
        """build_sender_tag() should retry on ServerError and succeed on second attempt."""
        from telethon.errors import ServerError

        msg = MagicMock()
        sender = MagicMock()
        sender.username = "server_user"
        msg.get_sender = AsyncMock(
            side_effect=itertools.cycle(
                [ServerError(request=None, message="Server error"), sender]
            )
        )
        msg.id = 456
        result = await build_sender_tag(msg)
        assert result == "@server_user"
        assert msg.get_sender.await_count == 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_connection_error(self, mock_sleep: AsyncMock) -> None:
        """build_sender_tag() should retry on ConnectionError and succeed on second attempt."""
        msg = MagicMock()
        sender = MagicMock()
        sender.username = "conn_user"
        msg.get_sender = AsyncMock(
            side_effect=itertools.cycle([ConnectionError(), sender])
        )
        msg.id = 789
        result = await build_sender_tag(msg)
        assert result == "@conn_user"
        assert msg.get_sender.await_count == 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_timeout_error(self, mock_sleep: AsyncMock) -> None:
        """build_sender_tag() should retry on TimeoutError and succeed on second attempt."""
        msg = MagicMock()
        sender = MagicMock()
        sender.username = "timeout_user"
        msg.get_sender = AsyncMock(
            side_effect=itertools.cycle([TimeoutError(), sender])
        )
        msg.id = 111
        result = await build_sender_tag(msg)
        assert result == "@timeout_user"
        assert msg.get_sender.await_count == 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_os_error(self, mock_sleep: AsyncMock) -> None:
        """build_sender_tag() should retry on OSError and succeed on second attempt."""
        msg = MagicMock()
        sender = MagicMock()
        sender.username = "os_user"
        msg.get_sender = AsyncMock(side_effect=itertools.cycle([OSError(), sender]))
        msg.id = 222
        result = await build_sender_tag(msg)
        assert result == "@os_user"
        assert msg.get_sender.await_count == 2

    @patch("asyncio.sleep", return_value=None)
    async def test_exhausts_retries_on_transient_error(
        self, mock_sleep: AsyncMock
    ) -> None:
        """build_sender_tag() should log warning after exhausting retries on transient errors."""
        from telethon.errors import TimedOutError

        msg = MagicMock()
        msg.id = 999
        msg.get_sender = AsyncMock(
            side_effect=TimedOutError(request=None, message="Timed out")
        )
        with patch("mko_telebot.monitor_client.logger") as mock_logger:
            result = await build_sender_tag(msg)
            assert result == ""
            # Verify warning logged on final failure
            mock_logger.warning.assert_called_once()
            assert "Sender resolution failed" in mock_logger.warning.call_args[0][0]
        # Should be called twice (max attempts)
        assert msg.get_sender.await_count == 2


class TestForwardToUsers:
    """Tests for forward_to_users()."""

    @patch("asyncio.sleep", return_value=None)
    async def test_sends_text_message(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should send text-only message via client.send_message."""
        msg = _make_msg_with_link(1, "test_channel")
        await forward_to_users(
            msg, "Hello world", [], mock_task, mock_client, mock_settings
        )
        assert mock_client.send_message.await_count == len(
            mock_task.forward_to_entities
        )

    @patch("asyncio.sleep", return_value=None)
    async def test_sends_media_message(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should send media via client.send_file."""
        msg = _make_msg_with_link(2, "test_channel")
        media = [MagicMock()]
        await forward_to_users(
            msg, "Photo caption", media, mock_task, mock_client, mock_settings
        )
        assert mock_client.send_file.await_count == len(mock_task.forward_to_entities)

    @patch("asyncio.sleep", return_value=None)
    async def test_includes_link_in_caption(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should include source link in caption."""
        msg = _make_msg_with_link(10, "test_channel")
        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        # caption is the second positional argument (args[1])
        args, _ = mock_client.send_message.call_args
        caption = args[1] if len(args) > 1 else ""
        assert "Source: https://t.me/test_channel/10" in caption

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_flood_wait(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should retry on FloodWaitError."""
        from telethon.errors import FloodWaitError

        msg = _make_msg_with_link(3, "test_channel")
        # Cycle: error then success, repeated enough for all targets × retries
        mock_client.send_message.side_effect = itertools.cycle(
            [
                FloodWaitError(request=None, capture=30),
                None,
            ]
        )

        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count >= 2

    @patch("asyncio.sleep", return_value=None)
    async def test_permanent_rpc_error_fails_fast(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should fail fast on permanent RPCError subclasses."""
        from telethon.errors import AuthKeyUnregisteredError

        msg = _make_msg_with_link(4, "test_channel")
        mock_client.send_message.side_effect = AuthKeyUnregisteredError(request=None)

        with pytest.raises(TelegramServiceError):
            await forward_to_users(
                msg, "Hello", [], mock_task, mock_client, mock_settings
            )
        # Should only be called once (no retries)
        assert mock_client.send_message.await_count == 1

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_rpc_error(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should retry on ServerError (transient RPCError)."""
        from telethon.errors import ServerError

        msg = _make_msg_with_link(4, "test_channel")
        mock_client.send_message.side_effect = itertools.cycle(
            [
                ServerError(request=None, message="Test ServerError"),
                None,
            ]
        )

        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count >= 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_timed_out_error(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should retry on TimedOutError (transient RPCError)."""
        from telethon.errors import TimedOutError

        msg = _make_msg_with_link(8, "test_channel")
        mock_client.send_message.side_effect = itertools.cycle(
            [
                TimedOutError(request=None, message="Timed out"),
                None,
            ]
        )

        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count >= 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_worker_busy_retry(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should retry on WorkerBusyTooLongRetryError."""
        from telethon.errors import WorkerBusyTooLongRetryError

        msg = _make_msg_with_link(7, "test_channel")
        mock_client.send_message.side_effect = itertools.cycle(
            [
                WorkerBusyTooLongRetryError(request=None),
                None,
            ]
        )

        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count >= 2

    @patch("asyncio.sleep", return_value=None)
    async def test_exhausts_retries(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should exhaust all retries and not raise."""
        from telethon.errors import FloodWaitError

        msg = _make_msg_with_link(5, "test_channel")
        mock_settings.telethon.max_retries = 2
        mock_client.send_message.side_effect = FloodWaitError(request=None, capture=30)

        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count >= 2 * len(
            mock_task.forward_to_entities
        )

    @patch("asyncio.sleep", return_value=None)
    async def test_handles_empty_text_and_no_media(
        self,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """forward_to_users() should handle empty text with no media gracefully."""
        msg = _make_msg_with_link(6, "test_channel")
        await forward_to_users(msg, "", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count == len(
            mock_task.forward_to_entities
        )


# ---------------------------------------------------------------------------
# process_messages
# ---------------------------------------------------------------------------


class TestProcessMessages:
    """Tests for process_messages().

    Tests verify actual behavior by checking client.send_message/send_file calls
    instead of mocking internal forward_to_users function.
    """

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/1",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_forward_on_keyword_match(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should forward messages matching keywords via send_message."""
        messages = [_make_msg_stub(1, "this is a test message")]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count == len(
            mock_task.forward_to_entities
        )
        args, _ = mock_client.send_message.call_args
        assert "test" in args[1]

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/2",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_does_not_forward_on_no_match(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should skip messages not matching keywords."""
        messages = [_make_msg_stub(2, "unrelated content here")]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        mock_client.send_message.assert_not_called()
        mock_client.send_file.assert_not_called()

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/10",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_groups_album_messages(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should group messages with same grouped_id into one album via send_file."""
        group_id = 100
        messages = [
            _make_msg_stub(10, "test photo one", grouped_id=group_id, has_media=True),
            _make_msg_stub(11, "test photo two", grouped_id=group_id, has_media=True),
        ]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        # Album messages should be sent via send_file (has media)
        assert mock_client.send_file.await_count == len(mock_task.forward_to_entities)
        args, kwargs = mock_client.send_file.call_args
        # Verify both texts are combined in caption
        caption = kwargs.get("caption", "")
        assert "test photo one" in caption
        assert "test photo two" in caption

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/20",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_does_not_forward_album_without_keyword_match(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should not forward grouped album with no keyword match."""
        group_id = 200
        messages = [
            _make_msg_stub(20, "random a", grouped_id=group_id, has_media=True),
            _make_msg_stub(21, "random b", grouped_id=group_id, has_media=True),
        ]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        mock_client.send_message.assert_not_called()
        mock_client.send_file.assert_not_called()

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/30",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_processes_individual_messages_separately(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should process individual messages separately."""
        messages = [
            _make_msg_stub(30, "test one"),
            _make_msg_stub(31, "test two"),
        ]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        # 2 messages × 2 forward targets = 4 calls
        assert mock_client.send_message.await_count == 4

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/70",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_groups_by_grouped_id_correctly(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should correctly group messages by grouped_id."""
        # Two separate groups, both containing "test" keyword
        messages = [
            _make_msg_stub(100, "test group one", grouped_id=100, has_media=True),
            _make_msg_stub(101, "test group one more", grouped_id=100, has_media=True),
            _make_msg_stub(200, "test group two", grouped_id=200, has_media=True),
            _make_msg_stub(
                300, "standalone test", grouped_id=None, has_media=False
            ),  # standalone
        ]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        # 2 albums (each to 2 targets) + 1 text (to 2 targets) = 6 total calls
        assert mock_client.send_file.await_count == 4  # 2 albums (2 targets each)
        assert (
            mock_client.send_message.await_count == 2
        )  # 1 standalone text (2 targets)

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch("mko_telebot.monitor_forward.build_message_link", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_uses_msg_id_when_no_grouped_id(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should use message id as group key when grouped_id is None."""
        # Each message should be processed individually
        messages = [
            _make_msg_stub(1, "test unique one"),
            _make_msg_stub(2, "test unique two"),
        ]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        # Both messages should trigger forward (different grouped_id means different groups)
        # 2 messages × 2 forward targets = 4 calls
        assert mock_client.send_message.await_count == 4

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch("mko_telebot.monitor_forward.build_message_link", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_skips_messages_without_text(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should skip messages with no text content."""
        messages = [_make_msg_stub(40, text="")]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        mock_client.send_message.assert_not_called()
        mock_client.send_file.assert_not_called()

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/50",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="@testuser",
    )
    async def test_includes_sender_tag_in_caption(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should include sender tag in forwarded message caption."""
        messages = [_make_msg_stub(50, "test message")]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        args, _ = mock_client.send_message.call_args
        caption = args[1]
        assert "Author: @testuser" in caption

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/60",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_includes_source_link_in_caption(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should include source link in forwarded message caption."""
        messages = [_make_msg_stub(60, "test message")]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        args, _ = mock_client.send_message.call_args
        caption = args[1]
        assert "Source: https://t.me/test/60" in caption

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/45",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_forwards_all_messages_when_keywords_empty(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should forward all messages when keywords list is empty."""
        mock_task.keywords = []  # Empty keywords = forward all
        messages = [
            _make_msg_stub(45, "any random content"),
            _make_msg_stub(46, "another unrelated message"),
        ]
        await process_messages(messages, mock_task, mock_client, mock_settings)
        # Both messages should be forwarded (2 messages × 2 targets = 4 calls)
        assert mock_client.send_message.await_count == 4

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/47",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_forwards_captionless_media_without_keywords(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should forward media without caption when keywords is empty."""
        mock_task.keywords = []  # Empty keywords = forward all
        # Media without caption (text="")
        msg = _make_msg_stub(47, text="", has_media=True, media_caption=None)
        msg.chat.username = "test_channel"
        await process_messages([msg], mock_task, mock_client, mock_settings)
        assert mock_client.send_file.await_count == len(mock_task.forward_to_entities)

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/80",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_forwards_media_with_matching_caption(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should forward media when caption matches keywords."""
        msg = _make_msg_stub(80, "", has_media=True, media_caption="test photo caption")
        msg.chat.username = "test_channel"
        await process_messages([msg], mock_task, mock_client, mock_settings)
        assert mock_client.send_file.await_count == len(mock_task.forward_to_entities)

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/81",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_does_not_forward_media_with_non_matching_caption(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should not forward media when caption has no keyword match."""
        msg = _make_msg_stub(81, "", has_media=True, media_caption="random caption")
        msg.chat.username = "test_channel"
        await process_messages([msg], mock_task, mock_client, mock_settings)
        mock_client.send_message.assert_not_called()
        mock_client.send_file.assert_not_called()

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/90",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_does_not_forward_captionless_media_with_keywords(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should not forward captionless media when keywords exist and no match."""
        # mock_task.keywords already has '"test"' from fixture
        msg = _make_msg_stub(90, text="", has_media=True, media_caption=None)
        msg.chat.username = "test_channel"
        await process_messages([msg], mock_task, mock_client, mock_settings)
        mock_client.send_message.assert_not_called()
        mock_client.send_file.assert_not_called()

    @patch("mko_telebot.monitor_forward.asyncio.sleep", return_value=None)
    @patch(
        "mko_telebot.monitor_forward.build_message_link",
        return_value="https://t.me/test/82",
    )
    @patch(
        "mko_telebot.monitor_forward.build_sender_tag",
        new_callable=AsyncMock,
        return_value="",
    )
    async def test_includes_caption_in_forwarded_text(
        self,
        mock_sender_tag: AsyncMock,
        mock_message_link: MagicMock,
        mock_sleep: AsyncMock,
        mock_client: MagicMock,
        mock_settings: MagicMock,
        mock_task: MagicMock,
    ) -> None:
        """process_messages() should include media caption in forwarded message text."""
        msg = _make_msg_stub(
            82, "test", has_media=True, media_caption="photo test caption"
        )
        msg.chat.username = "test_channel"
        await process_messages([msg], mock_task, mock_client, mock_settings)
        args, kwargs = mock_client.send_file.call_args
        caption = kwargs.get("caption", "")
        assert "test" in caption
        assert "photo" in caption


# ---------------------------------------------------------------------------
# process_and_reschedule
# ---------------------------------------------------------------------------


class TestProcessAndReschedule:
    """Tests for process_and_reschedule()."""

    async def test_calls_save_state_on_success(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_and_reschedule() should call save_state after processing."""
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()
        mock_task.save_state = AsyncMock()

        with patch("mko_telebot.monitor.process_task", new_callable=AsyncMock):
            await process_and_reschedule(
                mock_task, mock_client, queue, lock, mock_settings
            )
            mock_task.save_state.assert_awaited_once()

    async def test_continues_after_save_state_error(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_and_reschedule() should log error and continue when save_state raises StateError."""
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()
        mock_task.save_state = AsyncMock(side_effect=StateError("Disk error"))

        with (
            patch("mko_telebot.monitor.process_task", new_callable=AsyncMock),
            patch("mko_telebot.monitor.logger") as mock_logger,
        ):
            await process_and_reschedule(
                mock_task, mock_client, queue, lock, mock_settings
            )
            mock_logger.error.assert_called_once()
            # Verify that state save error was logged
            assert "Failed to save task state" in mock_logger.error.call_args[0][0]

    async def test_telegram_service_error_still_reschedules(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_and_reschedule() should catch TelegramServiceError and still reschedule channel."""
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()
        mock_task.save_state = AsyncMock()

        with (
            patch(
                "mko_telebot.monitor.process_task",
                new_callable=AsyncMock,
                side_effect=TelegramServiceError("RPC error"),
            ),
            patch(
                "mko_telebot.monitor.reschedule_task", new_callable=AsyncMock
            ) as mock_reschedule,
            patch("mko_telebot.monitor.logger") as mock_logger,
        ):
            # Should NOT raise - error is caught
            await process_and_reschedule(
                mock_task, mock_client, queue, lock, mock_settings
            )

            # Verify error was logged
            mock_logger.error.assert_called()
            assert "Error processing channel" in mock_logger.error.call_args[0][0]

            # Verify reschedule was still called (in finally block)
            mock_reschedule.assert_called_once_with(mock_task, queue)

    async def test_still_raises_for_other_exceptions(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_and_reschedule() should let non-StateError exceptions propagate."""
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()
        mock_task.save_state = AsyncMock(side_effect=ValueError("Unexpected error"))

        with patch("mko_telebot.monitor.process_task", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="Unexpected error"):
                await process_and_reschedule(
                    mock_task, mock_client, queue, lock, mock_settings
                )


# ---------------------------------------------------------------------------
# TestRunMonitor
# ---------------------------------------------------------------------------


class TestRunMonitor:
    """Tests for run_monitor()."""

    async def test_starts_client_and_runs_loop(self) -> None:
        """run_monitor() should start client and enter main loop on success."""
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()

        mock_settings = MagicMock()

        with patch(
            "mko_telebot.monitor.start_client",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # Import after patching to get the mocked version
            from mko_telebot import monitor

            with patch.object(
                monitor, "main_loop", new_callable=AsyncMock
            ) as mock_loop:
                # Set side_effect to raise KeyboardInterrupt from inside the mocked coroutine
                mock_loop.side_effect = KeyboardInterrupt("test exit")

                with pytest.raises(KeyboardInterrupt):
                    await monitor.run_monitor(mock_settings, mock_client)

                mock_loop.assert_awaited_once()
                mock_client.disconnect.assert_awaited_once()

    async def test_does_not_run_loop_on_auth_failure(self) -> None:
        """run_monitor() should not enter mainLoop if start_client fails."""
        from mko_telebot.core.errors import TelegramAuthError

        mock_client = MagicMock()
        mock_client.disconnect = Mock()

        mock_settings = MagicMock()

        with patch(
            "mko_telebot.monitor.start_client",
            new_callable=AsyncMock,
            return_value=False,
        ):
            from mko_telebot.monitor import run_monitor

            with pytest.raises(
                TelegramAuthError, match="Telegram authentication failed"
            ):
                await run_monitor(mock_settings, mock_client)
            mock_client.disconnect.assert_not_called()


# ---------------------------------------------------------------------------
# TestMainLoop
# ---------------------------------------------------------------------------


class TestMainLoop:
    """Tests for main_loop() orchestration."""

    async def test_creates_task_for_each_channel(self) -> None:
        """main_loop() should create Task for each channel in config."""
        from mko_telebot.monitor import main_loop

        mock_settings = MagicMock()
        mock_settings.channels.channels_delay = 30
        mock_settings.channels.stagger_start_seconds = 5

        mock_channel_config = MagicMock()
        mock_channel_config.name = "test_channel"
        mock_channel_config.scan_interval = 420
        mock_channel_config.history_limit = 50
        mock_channel_config.overlap = 5
        mock_channel_config.forward_to = []
        mock_channel_config.keywords = []

        mock_settings.channels.channels = {"test_channel": mock_channel_config}

        mock_client = MagicMock()
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()

        with (
            patch("mko_telebot.monitor.Task") as mock_task_class,
            patch("mko_telebot.monitor.process_and_reschedule", new_callable=AsyncMock),
        ):
            mock_task_instance = MagicMock()
            mock_task_instance.resolve_channel_entity = AsyncMock()
            mock_task_instance.resolve_state_file = Mock()
            mock_task_instance.load_state = AsyncMock()
            mock_task_instance.resolve_targets_entities = AsyncMock()
            mock_task_class.return_value = mock_task_instance

            # Patch queue.get to return immediately to break the loop
            get_count = 0

            async def mock_get():
                nonlocal get_count
                get_count += 1
                if get_count > 1:
                    raise KeyboardInterrupt()
                return MagicMock()

            with patch.object(queue, "get", side_effect=mock_get):
                with patch("asyncio.sleep", return_value=None):
                    with pytest.raises(KeyboardInterrupt):
                        await main_loop(mock_settings, mock_client, queue, lock)

            mock_task_class.assert_called_once()

    async def test_resolves_channel_entity(self) -> None:
        """main_loop() should call resolve_channel_entity for each channel."""
        from mko_telebot.monitor import main_loop

        mock_settings = MagicMock()
        mock_settings.channels.channels_delay = 30
        mock_settings.channels.stagger_start_seconds = 5

        mock_channel_config = MagicMock()
        mock_channel_config.name = "channel_a"
        mock_channel_config.scan_interval = 420
        mock_channel_config.history_limit = 50
        mock_channel_config.overlap = 5
        mock_channel_config.forward_to = []
        mock_channel_config.keywords = []

        mock_settings.channels.channels = {"channel_a": mock_channel_config}

        mock_client = MagicMock()
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()

        with (
            patch("mko_telebot.monitor.Task") as mock_task_class,
            patch("mko_telebot.monitor.process_and_reschedule", new_callable=AsyncMock),
        ):
            mock_task_instance = MagicMock()
            mock_task_instance.resolve_channel_entity = AsyncMock()
            mock_task_instance.resolve_state_file = Mock()
            mock_task_instance.load_state = AsyncMock()
            mock_task_instance.resolve_targets_entities = AsyncMock()
            mock_task_class.return_value = mock_task_instance

            get_count = 0

            async def mock_get():
                nonlocal get_count
                get_count += 1
                if get_count > 1:
                    raise KeyboardInterrupt()
                return MagicMock()

            with patch.object(queue, "get", side_effect=mock_get):
                with patch("asyncio.sleep", return_value=None):
                    with pytest.raises(KeyboardInterrupt):
                        await main_loop(mock_settings, mock_client, queue, lock)

            mock_task_instance.resolve_channel_entity.assert_awaited_once()

    async def test_loads_state(self) -> None:
        """main_loop() should call load_state for each channel."""
        from mko_telebot.monitor import main_loop

        mock_settings = MagicMock()
        mock_settings.channels.channels_delay = 30
        mock_settings.channels.stagger_start_seconds = 5

        mock_channel_config = MagicMock()
        mock_channel_config.name = "channel_b"
        mock_channel_config.scan_interval = 420
        mock_channel_config.history_limit = 50
        mock_channel_config.overlap = 5
        mock_channel_config.forward_to = []
        mock_channel_config.keywords = []

        mock_settings.channels.channels = {"channel_b": mock_channel_config}

        mock_client = MagicMock()
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()

        with (
            patch("mko_telebot.monitor.Task") as mock_task_class,
            patch("mko_telebot.monitor.process_and_reschedule", new_callable=AsyncMock),
        ):
            mock_task_instance = MagicMock()
            mock_task_instance.resolve_channel_entity = AsyncMock()
            mock_task_instance.resolve_state_file = Mock()
            mock_task_instance.load_state = AsyncMock()
            mock_task_instance.resolve_targets_entities = AsyncMock()
            mock_task_class.return_value = mock_task_instance

            get_count = 0

            async def mock_get():
                nonlocal get_count
                get_count += 1
                if get_count > 1:
                    raise KeyboardInterrupt()
                return MagicMock()

            with patch.object(queue, "get", side_effect=mock_get):
                with patch("asyncio.sleep", return_value=None):
                    with pytest.raises(KeyboardInterrupt):
                        await main_loop(mock_settings, mock_client, queue, lock)

            mock_task_instance.load_state.assert_awaited_once()

    async def test_puts_tasks_in_queue(self) -> None:
        """main_loop() should put tasks in the queue during initialization."""
        from mko_telebot.monitor import main_loop

        mock_settings = MagicMock()
        mock_settings.channels.channels_delay = 30
        mock_settings.channels.stagger_start_seconds = 5

        mock_channel_config = MagicMock()
        mock_channel_config.name = "channel_c"
        mock_channel_config.scan_interval = 420
        mock_channel_config.history_limit = 50
        mock_channel_config.overlap = 5
        mock_channel_config.forward_to = []
        mock_channel_config.keywords = []

        mock_settings.channels.channels = {"channel_c": mock_channel_config}

        mock_client = MagicMock()
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()

        with (
            patch("mko_telebot.monitor.Task") as mock_task_class,
            patch("mko_telebot.monitor.process_and_reschedule", new_callable=AsyncMock),
        ):
            mock_task_instance = MagicMock()
            mock_task_instance.resolve_channel_entity = AsyncMock()
            mock_task_instance.resolve_state_file = Mock()
            mock_task_instance.load_state = AsyncMock()
            mock_task_instance.resolve_targets_entities = AsyncMock()
            mock_task_class.return_value = mock_task_instance

            get_count = 0

            async def mock_get():
                nonlocal get_count
                get_count += 1
                if get_count > 1:
                    raise KeyboardInterrupt()
                return MagicMock()

            with patch.object(queue, "get", side_effect=mock_get):
                with patch("asyncio.sleep", return_value=None):
                    with pytest.raises(KeyboardInterrupt):
                        await main_loop(mock_settings, mock_client, queue, lock)

            # Task should have been put in queue during setup
            assert queue.qsize() == 1

    async def test_raises_error_on_empty_channels(self) -> None:
        """main_loop() should raise ConfigError when no channels configured."""
        from mko_telebot.core.errors import ConfigError
        from mko_telebot.monitor import main_loop

        mock_settings = MagicMock()
        mock_settings.channels.channels_delay = 30
        mock_settings.channels.stagger_start_seconds = 5
        mock_settings.channels.channels = {}  # Empty channels

        mock_client = MagicMock()
        queue: asyncio.Queue[MagicMock] = asyncio.Queue()
        lock = asyncio.Lock()

        with patch("mko_telebot.monitor.logger") as mock_logger:
            with pytest.raises(ConfigError, match="No channels configured"):
                await main_loop(mock_settings, mock_client, queue, lock)

            mock_logger.error.assert_called_once()
            assert "No channels configured" in mock_logger.error.call_args[0][0]


# ---------------------------------------------------------------------------
# TestRescheduleTask
# ---------------------------------------------------------------------------


class TestRescheduleTask:
    """Tests for reschedule_task()."""

    async def test_calculates_delay_and_puts_task_in_queue(self) -> None:
        """reschedule_task() should sleep for scan_interval + jitter then put task in queue."""
        from mko_telebot.monitor import reschedule_task

        mock_task = MagicMock()
        mock_task.channel_name = "test_channel"
        mock_task.scan_interval = 420

        queue: asyncio.Queue[MagicMock] = asyncio.Queue()

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("random.uniform", return_value=15.0),
        ):
            await reschedule_task(mock_task, queue)

            expected_delay = 420 + 15.0
            mock_sleep.assert_awaited_once_with(expected_delay)
            assert not queue.empty()

    async def test_puts_task_back_in_queue(self) -> None:
        """reschedule_task() should put the task back in the queue."""
        from mko_telebot.monitor import reschedule_task

        mock_task = MagicMock()
        mock_task.channel_name = "reschedule_test"
        mock_task.scan_interval = 60

        queue: asyncio.Queue[MagicMock] = asyncio.Queue()

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("random.uniform", return_value=20.0),
        ):
            await reschedule_task(mock_task, queue)
            queued_task = queue.get_nowait()
            assert queued_task is mock_task

    async def test_uses_random_jitter(self) -> None:
        """reschedule_task() should use random.uniform for jitter."""
        from mko_telebot.monitor import reschedule_task

        mock_task = MagicMock()
        mock_task.scan_interval = 300

        queue: asyncio.Queue[MagicMock] = asyncio.Queue()

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("random.uniform", return_value=22.5) as mock_random,
        ):
            await reschedule_task(mock_task, queue)
            mock_random.assert_called_once()
            args = mock_random.call_args[0]
            assert args[0] == 10
            assert args[1] == 30
