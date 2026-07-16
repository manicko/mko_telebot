"""Tests for monitor_forward module — process_task function."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.errors import FloodWaitError, WorkerBusyTooLongRetryError

from mko_telebot.monitor_forward import process_task


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

            async def gen() -> Any:
                raise FloodWaitError(request=None, capture=30)
                yield  # pyright: ignore[reportUnreachable]

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

            async def gen() -> Any:
                raise WorkerBusyTooLongRetryError(request=None)
                yield  # pyright: ignore[reportUnreachable]

            mock_client.iter_messages.return_value = gen()

            await process_task(mock_task, mock_client, mock_settings)
            assert mock_sleep.await_count >= 1

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
