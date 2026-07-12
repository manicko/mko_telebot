"""Tests for monitor_forward module — process_task and _send_with_retry functions."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.errors import FloodWaitError, RPCError, WorkerBusyTooLongRetryError

from mko_telebot.core.errors import TelegramServiceError
from mko_telebot.monitor_forward import _send_with_retry, process_task


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock Telethon client with async method stubs."""
    client = MagicMock()
    client.iter_messages = MagicMock()
    client.send_message = AsyncMock()
    client.send_file = AsyncMock()
    return client


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock TelepostSettings with telethon config."""
    settings = MagicMock()
    settings.telethon.max_retries = 3
    return settings


@pytest.fixture
def mock_task() -> MagicMock:
    """Create a mock Task with channel configuration."""
    task = MagicMock()
    task.channel_name = "@test_channel"
    task.channel_entity = MagicMock()
    task.forward_to_entities = [MagicMock(), MagicMock()]
    task.keywords = ['"test"']
    task.last_msg_id = 0
    task.overlap = 5
    task.offset_date = None
    task.history_limit = 50
    return task


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


async def _async_iter(items: list[Any]) -> Any:
    """Create an async iterator from a list."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# TestProcessTask
# ---------------------------------------------------------------------------


class TestProcessTask:
    """Tests for process_task()."""

    async def test_fetches_messages_and_processes_matches(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_task() should fetch messages and process matches."""
        msg = MagicMock()
        msg.id = 100
        msg.message = "test message"
        msg.grouped_id = None
        msg.media = None

        mock_client.iter_messages.return_value = _async_iter([msg])

        with patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock) as mock_process:
            await process_task(mock_task, mock_client, mock_settings)
            mock_process.assert_awaited_once()
            call_args = mock_process.call_args[0]
            assert len(call_args[0]) == 1

    async def test_updates_last_msg_id_after_processing(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_task() should update last_msg_id after processing messages."""
        msg = MagicMock()
        msg.id = 200
        msg.message = "test"
        msg.grouped_id = None
        msg.media = None

        mock_client.iter_messages.return_value = _async_iter([msg])

        with patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock):
            await process_task(mock_task, mock_client, mock_settings)
            assert mock_task.last_msg_id == 200

    async def test_handles_flood_wait_error(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_task() should handle FloodWaitError with sleep and continue."""
        with (
            patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            async def gen():
                raise FloodWaitError(request=None)
                yield

            mock_client.iter_messages.return_value = gen()

            await process_task(mock_task, mock_client, mock_settings)
            assert mock_sleep.await_count >= 1

    async def test_handles_worker_busy_error(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_task() should handle WorkerBusyTooLongRetryError with sleep."""
        with (
            patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            async def gen():
                raise WorkerBusyTooLongRetryError(request=None)
                yield

            mock_client.iter_messages.return_value = gen()

            await process_task(mock_task, mock_client, mock_settings)
            assert mock_sleep.await_count >= 1

    async def test_handles_telegram_service_error(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_task() should return early on TelegramServiceError without raising."""
        with (
            patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("mko_telebot.monitor_forward.logger") as mock_logger,
        ):
            initial_last_msg = mock_task.last_msg_id

            async def gen():
                raise TelegramServiceError("Service error")
                yield

            mock_client.iter_messages.return_value = gen()

            await process_task(mock_task, mock_client, mock_settings)
            assert mock_task.last_msg_id == initial_last_msg
            mock_logger.error.assert_called()

    async def test_skips_already_processed_messages(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_task() should skip messages with id <= last_msg_id."""
        mock_task.last_msg_id = 150

        msg1 = MagicMock()
        msg1.id = 100
        msg1.message = "old test"
        msg1.grouped_id = None
        msg1.media = None

        msg2 = MagicMock()
        msg2.id = 160
        msg2.message = "new test"
        msg2.grouped_id = None
        msg2.media = None

        mock_client.iter_messages.return_value = _async_iter([msg1, msg2])

        with patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock) as mock_process:
            await process_task(mock_task, mock_client, mock_settings)
            call_args = mock_process.call_args[0]
            assert len(call_args[0]) == 1
            assert call_args[0][0].id == 160

    async def test_handles_empty_message_list(
        self, mock_client: MagicMock, mock_settings: MagicMock, mock_task: MagicMock
    ) -> None:
        """process_task() should handle empty message list gracefully."""
        mock_client.iter_messages.return_value = _async_iter([])

        with (
            patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock) as mock_process,
            patch("mko_telebot.monitor_forward.logger") as mock_logger,
        ):
            await process_task(mock_task, mock_client, mock_settings)
            mock_process.assert_not_called()
            mock_logger.info.assert_called()


# ---------------------------------------------------------------------------
# TestSendWithRetry
# ---------------------------------------------------------------------------


class TestSendWithRetry:
    """Tests for _send_with_retry() helper function."""

    @patch("asyncio.sleep", return_value=None)
    async def test_sends_text_message(
        self, mock_sleep: AsyncMock, mock_client: MagicMock
    ) -> None:
        """_send_with_retry() should send text message via send_message."""
        target = MagicMock()
        result = await _send_with_retry(
            mock_client, target, "Hello", None, max_tries=3, channel_name="test"
        )
        assert result is True
        mock_client.send_message.assert_awaited_once()

    @patch("asyncio.sleep", return_value=None)
    async def test_sends_media_message(
        self, mock_sleep: AsyncMock, mock_client: MagicMock
    ) -> None:
        """_send_with_retry() should send media via send_file."""
        target = MagicMock()
        media = [MagicMock()]
        result = await _send_with_retry(
            mock_client, target, "Caption", media, max_tries=3, channel_name="test"
        )
        assert result is True
        mock_client.send_file.assert_awaited_once()

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_flood_wait(
        self, mock_sleep: AsyncMock, mock_client: MagicMock
    ) -> None:
        """_send_with_retry() should retry on FloodWaitError and return True on success."""
        target = MagicMock()
        mock_client.send_message.side_effect = [FloodWaitError(request=None), None]
        result = await _send_with_retry(
            mock_client, target, "Hello", None, max_tries=3, channel_name="test"
        )
        assert result is True
        assert mock_client.send_message.await_count == 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_worker_busy(
        self, mock_sleep: AsyncMock, mock_client: MagicMock
    ) -> None:
        """_send_with_retry() should retry on WorkerBusyTooLongRetryError."""
        target = MagicMock()
        mock_client.send_message.side_effect = [WorkerBusyTooLongRetryError(request=None), None]
        result = await _send_with_retry(
            mock_client, target, "Hello", None, max_tries=3, channel_name="test"
        )
        assert result is True
        assert mock_client.send_message.await_count == 2

    @patch("asyncio.sleep", return_value=None)
    async def test_retries_on_rpc_error(
        self, mock_sleep: AsyncMock, mock_client: MagicMock
    ) -> None:
        """_send_with_retry() should retry on RPCError."""
        target = MagicMock()
        mock_client.send_message.side_effect = [RPCError(request=None, message="error"), None]
        result = await _send_with_retry(
            mock_client, target, "Hello", None, max_tries=3, channel_name="test"
        )
        assert result is True
        assert mock_client.send_message.await_count == 2

    @patch("asyncio.sleep", return_value=None)
    async def test_returns_false_after_all_retries_fail(
        self, mock_sleep: AsyncMock, mock_client: MagicMock
    ) -> None:
        """_send_with_retry() should return False when all retries fail."""
        target = MagicMock()
        mock_client.send_message.side_effect = FloodWaitError(request=None)
        result = await _send_with_retry(
            mock_client, target, "Hello", None, max_tries=3, channel_name="test"
        )
        assert result is False
        assert mock_client.send_message.await_count == 3

    @patch("asyncio.sleep", return_value=None)
    async def test_logs_info_on_success(
        self, mock_sleep: AsyncMock, mock_client: MagicMock
    ) -> None:
        """_send_with_retry() should log info on successful send."""
        target = MagicMock()
        target.id = 12345
        with patch("mko_telebot.monitor_forward.logger") as mock_logger:
            await _send_with_retry(
                mock_client, target, "Hello", None, max_tries=3, channel_name="test"
            )
            mock_logger.info.assert_called_once()

    @patch("asyncio.sleep", return_value=None)
    async def test_logs_warning_on_retry(
        self, mock_sleep: AsyncMock, mock_client: MagicMock
    ) -> None:
        """_send_with_retry() should log warning on retry."""
        target = MagicMock()
        target.id = 12345
        mock_client.send_message.side_effect = [FloodWaitError(request=None), None]
        with patch("mko_telebot.monitor_forward.logger") as mock_logger:
            await _send_with_retry(
                mock_client, target, "Hello", None, max_tries=3, channel_name="test"
            )
            mock_logger.warning.assert_called_once()
            assert "Flood wait" in mock_logger.warning.call_args[0][0]