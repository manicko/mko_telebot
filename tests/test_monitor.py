"""Tests for the monitor module — Telegram client creation, auth, message forwarding, and keyword processing."""

from __future__ import annotations

import itertools
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mko_telebot.core.errors import TelegramAuthError, TelegramServiceError
from mko_telebot.monitor import (
    build_message_link,
    build_sender_tag,
    create_client,
    forward_to_users,
    process_messages,
    start_client,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_msg_stub(
    msg_id: int, text: str = "", grouped_id: int | None = None, has_media: bool = False
) -> MagicMock:
    """Create a mock Telethon message with given attributes and async get_sender."""
    msg = MagicMock()
    msg.id = msg_id
    msg.message = text
    msg.grouped_id = grouped_id
    msg.get_sender = AsyncMock(return_value=None)
    if has_media:
        media = MagicMock()
        media.caption = None
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
    settings.telethon.max_retries = 3
    settings.telethon.client.model_dump.return_value = {
        "api_id": 123456,
        "api_hash": "test_hash_abcdef123456",
        "session": "test_session",
    }
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
            patch("mko_telebot.monitor.APP_PATHS") as mock_paths,
            patch("mko_telebot.monitor.TelegramClient") as mock_tc,
        ):
            mock_paths.session_dir = session_dir
            settings = MagicMock()
            settings.telethon.client.model_dump.return_value = {
                "api_id": 123456,
                "api_hash": "hash",
                "session": "my_session",
            }
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
            patch("mko_telebot.monitor.APP_PATHS") as mock_paths,
            patch("mko_telebot.monitor.TelegramClient") as mock_tc,
        ):
            mock_paths.session_dir = session_dir
            settings = MagicMock()
            settings.telethon.client.model_dump.return_value = {
                "api_id": 123456,
                "api_hash": "hash",
                "session": "custom.session",
            }
            create_client(settings)

        expected_path = str(session_dir / "custom.session")
        mock_tc.assert_called_once()
        _, kwargs = mock_tc.call_args
        assert kwargs["session"] == expected_path

    def test_passes_config_through(self) -> None:
        """create_client() should pass all client config to TelegramClient."""
        with (
            patch("mko_telebot.monitor.APP_PATHS") as mock_paths,
            patch("mko_telebot.monitor.TelegramClient") as mock_tc,
        ):
            mock_paths.session_dir = Path("/tmp/sessions")
            settings = MagicMock()
            settings.telethon.client.model_dump.return_value = {
                "api_id": 999888,
                "api_hash": "test_hash_value",
                "session": "s1",
                "app_version": "1.0.0",
            }
            create_client(settings)

        mock_tc.assert_called_once()
        _, kwargs = mock_tc.call_args
        assert kwargs["api_id"] == 999888
        assert kwargs["api_hash"] == "test_hash_value"


# ---------------------------------------------------------------------------
# start_client
# ---------------------------------------------------------------------------


class TestStartClient:
    """Tests for start_client()."""

    async def test_auth_success_user(self, mock_client: MagicMock, mock_settings: MagicMock) -> None:
        """start_client() should start with phone for user accounts."""
        mock_settings.telethon.is_user = True
        result = await start_client(mock_client, mock_settings)
        assert result is True
        mock_client.start.assert_awaited_once_with(
            phone=mock_settings.telethon.phone_or_token.get_secret_value()
        )

    async def test_auth_success_bot(self, mock_client: MagicMock, mock_settings: MagicMock) -> None:
        """start_client() should start with bot_token for bot accounts."""
        mock_settings.telethon.is_user = False
        result = await start_client(mock_client, mock_settings)
        assert result is True
        mock_client.start.assert_awaited_once_with(
            bot_token=mock_settings.telethon.phone_or_token.get_secret_value()
        )

    async def test_auth_failure_telegram_auth_error(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should return False on TelegramAuthError."""
        mock_client.start.side_effect = TelegramAuthError("Auth failed")
        result = await start_client(mock_client, mock_settings)
        assert result is False

    async def test_auth_failure_telegram_service_error(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        """start_client() should return False on TelegramServiceError."""
        mock_client.start.side_effect = TelegramServiceError("Service error")
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

    async def test_returns_empty_on_service_error(self) -> None:
        """build_sender_tag() should return '' when TelegramServiceError occurs."""
        msg = MagicMock()
        msg.get_sender = AsyncMock(side_effect=TelegramServiceError("Error"))
        result = await build_sender_tag(msg)
        assert result == ""


# ---------------------------------------------------------------------------
# forward_to_users
# ---------------------------------------------------------------------------


class TestForwardToUsers:
    """Tests for forward_to_users()."""

    @patch("asyncio.sleep", return_value=None)
    async def test_sends_text_message(
        self, mock_sleep: AsyncMock, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """forward_to_users() should send text-only message via client.send_message."""
        msg = _make_msg_with_link(1, "test_channel")
        await forward_to_users(msg, "Hello world", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count == len(mock_task.forward_to_entities)

    @patch("asyncio.sleep", return_value=None)
    async def test_sends_media_message(
        self, mock_sleep: AsyncMock, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """forward_to_users() should send media via client.send_file."""
        msg = _make_msg_with_link(2, "test_channel")
        media = [MagicMock()]
        await forward_to_users(msg, "Photo caption", media, mock_task, mock_client, mock_settings)
        assert mock_client.send_file.await_count == len(mock_task.forward_to_entities)

    @patch("asyncio.sleep", return_value=None)
    async def test_includes_link_in_caption(
        self, mock_sleep: AsyncMock, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
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
        self, mock_sleep: AsyncMock, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """forward_to_users() should retry on FloodWaitError."""
        from telethon.errors import FloodWaitError

        msg = _make_msg_with_link(3, "test_channel")
        # Cycle: error then success, repeated enough for all targets × retries
        mock_client.send_message.side_effect = itertools.cycle([
            FloodWaitError(request=None),
            None,
        ])

        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count >= 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_rpc_error(
        self, mock_sleep: AsyncMock, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """forward_to_users() should retry on RPCError."""
        from telethon.errors import RPCError

        msg = _make_msg_with_link(4, "test_channel")
        mock_client.send_message.side_effect = itertools.cycle([
            RPCError(request=None, message="Test RPC error"),
            None,
        ])

        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count >= 2

    @patch("asyncio.sleep", return_value=None)
    async def test_exhausts_retries(
        self, mock_sleep: AsyncMock, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """forward_to_users() should exhaust all retries and not raise."""
        from telethon.errors import FloodWaitError

        msg = _make_msg_with_link(5, "test_channel")
        mock_settings.telethon.max_retries = 2
        mock_client.send_message.side_effect = FloodWaitError(request=None)

        await forward_to_users(msg, "Hello", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count >= 2 * len(mock_task.forward_to_entities)

    @patch("asyncio.sleep", return_value=None)
    async def test_handles_empty_text_and_no_media(
        self, mock_sleep: AsyncMock, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """forward_to_users() should handle empty text with no media gracefully."""
        msg = _make_msg_with_link(6, "test_channel")
        await forward_to_users(msg, "", [], mock_task, mock_client, mock_settings)
        assert mock_client.send_message.await_count == len(mock_task.forward_to_entities)


# ---------------------------------------------------------------------------
# process_messages
# ---------------------------------------------------------------------------


class TestProcessMessages:
    """Tests for process_messages()."""

    async def test_forward_on_keyword_match(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_messages() should forward messages matching keywords."""
        messages = [_make_msg_stub(1, "this is a test message")]
        with patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock) as mock_forward:
            await process_messages(messages, mock_task, mock_client, mock_settings)
            mock_forward.assert_awaited_once()

    async def test_does_not_forward_on_no_match(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_messages() should skip messages not matching keywords."""
        messages = [_make_msg_stub(2, "unrelated content here")]
        with patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock) as mock_forward:
            await process_messages(messages, mock_task, mock_client, mock_settings)
            mock_forward.assert_not_called()

    async def test_groups_album_messages(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_messages() should group messages with same grouped_id into one album."""
        group_id = 100
        messages = [
            _make_msg_stub(10, "test photo one", grouped_id=group_id, has_media=True),
            _make_msg_stub(11, "test photo two", grouped_id=group_id, has_media=True),
        ]
        with patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock) as mock_forward:
            await process_messages(messages, mock_task, mock_client, mock_settings)
            mock_forward.assert_awaited_once()
            call_args = mock_forward.call_args
            msg_text = call_args[0][1]
            assert "test photo one" in msg_text
            assert "test photo two" in msg_text

    async def test_does_not_forward_album_without_keyword_match(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_messages() should not forward grouped album with no keyword match."""
        group_id = 200
        messages = [
            _make_msg_stub(20, "random a", grouped_id=group_id, has_media=True),
            _make_msg_stub(21, "random b", grouped_id=group_id, has_media=True),
        ]
        with patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock) as mock_forward:
            await process_messages(messages, mock_task, mock_client, mock_settings)
            mock_forward.assert_not_called()

    async def test_handles_empty_message_list(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_messages() should handle empty message list without error."""
        with patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock) as mock_forward:
            await process_messages([], mock_task, mock_client, mock_settings)
            mock_forward.assert_not_called()

    async def test_processes_individual_messages_separately(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_messages() should process individual messages separately."""
        messages = [
            _make_msg_stub(30, "test one"),
            _make_msg_stub(31, "test two"),
        ]
        with patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock) as mock_forward:
            await process_messages(messages, mock_task, mock_client, mock_settings)
            assert mock_forward.await_count == 2

    async def test_skips_messages_without_text(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_messages() should skip messages with no text content."""
        messages = [_make_msg_stub(40, text="")]
        with patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock) as mock_forward:
            await process_messages(messages, mock_task, mock_client, mock_settings)
            mock_forward.assert_not_called()