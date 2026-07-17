"""Tests for the Task model — async state management, entity resolution, offset date computation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.errors import FloodWaitError

from mko_telebot.core.channels import ChannelConfig
from mko_telebot.core.errors import StateError, TelegramServiceError
from mko_telebot.core.task import Task
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_config(**overrides: Any) -> ChannelConfig:
    """Create a ChannelConfig with default test values."""
    defaults: dict[str, Any] = {
        "name": "@test_monitor",
        "forward_to": [],
        "keywords": [],
        "scan_interval": 420,
        "history_limit": 50,
        "history_days": None,
        "overlap": 5,
    }
    defaults.update(overrides)
    return ChannelConfig(**defaults)


def _make_task(config: ChannelConfig | None = None) -> Task:
    """Create a Task with default config."""
    cfg = config or _make_config()
    return Task(cfg)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestTaskInit:
    """Tests for Task.__init__()."""

    def test_init_sets_attributes(self) -> None:
        """Constructor should populate attributes from ChannelConfig."""
        config = _make_config(
            name="@test_channel",
            forward_to=["@target1"],
            keywords=["hello"],
            scan_interval=300,
            history_limit=100,
            overlap=3,
        )
        task = Task(config)
        assert task.channel_name == "@test_channel"
        assert task.forward_to == ["@target1"]
        assert task.keywords == ["hello"]
        assert task.scan_interval == 300
        assert task.history_limit == 100
        assert task.overlap == 3
        assert task.last_msg_id == 0
        assert task.channel_entity is None
        assert task.forward_to_entities == []
        assert task.state_file is None

    def test_init_loads_state_persists_last_msg_id(self) -> None:
        """Constructor initializes last_msg_id to 0, load_state() restores from file."""
        config = _make_config()
        task = Task(config)
        assert task.last_msg_id == 0

    def test_init_computes_offset_date_with_history_days(self) -> None:
        """Constructor should compute offset_date when history_days is set."""
        config = _make_config(history_days=7)
        task = Task(config)
        assert task.offset_date is not None

    def test_init_offset_date_none_without_history_days(self) -> None:
        """Constructor should leave offset_date as None when no history_days."""
        config = _make_config(history_days=None)
        task = Task(config)
        assert task.offset_date is None


# ---------------------------------------------------------------------------
# set_offset_date
# ---------------------------------------------------------------------------


class TestSetOffsetDate:
    """Tests for Task.set_offset_date()."""

    def test_sets_none_when_no_history_days(self) -> None:
        """set_offset_date() should set offset_date to None when history_days is None."""
        config = _make_config(history_days=None)
        task = _make_task(config)
        task.offset_date = datetime.now(UTC)  # Set initial value to verify it gets cleared
        task.set_offset_date()
        assert task.offset_date is None

    def test_computes_correct_offset(self) -> None:
        """set_offset_date() should compute (now - history_days) in UTC."""
        config = _make_config(history_days=7)
        task = _make_task(config)
        task.set_offset_date()
        assert task.offset_date is not None
        assert task.offset_date.tzname() == "UTC"

    def test_raises_config_error_on_invalid_days(self) -> None:
        """set_offset_date() should raise ConfigError when history_days is not int-convertible."""
        from mko_telebot.core.errors import ConfigError

        config = _make_config(history_days=None)
        task = _make_task(config)
        task.history_days = "not_a_number"  # type: ignore[assignment]
        with pytest.raises(ConfigError, match="Invalid history_days"):
            task.set_offset_date()


# ---------------------------------------------------------------------------
# resolve_state_file
# ---------------------------------------------------------------------------


class TestResolveStateFile:
    """Tests for Task.resolve_state_file()."""

    def test_creates_state_file_path(self, tmp_path: Path) -> None:
        """resolve_state_file() should set state_file under state_dir."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        with patch("mko_telebot.core.task.state_dir", tmp_path):
            task.resolve_state_file()
        expected = tmp_path / "@test_channel.json"
        assert task.state_file == expected
        assert expected.parent.exists()

    def test_raises_state_error_on_failure(self, tmp_path: Path) -> None:
        """resolve_state_file() should raise StateError when path creation fails."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        with (
            patch("mko_telebot.core.task.state_dir", tmp_path),
            patch("mko_telebot.core.task.ensure_path_exists", side_effect=ValueError("Cannot create")),
        ):
            with pytest.raises(StateError, match="Failed to create or verify state file"):
                task.resolve_state_file()


# ---------------------------------------------------------------------------
# load_state
# ---------------------------------------------------------------------------


class TestLoadState:
    """Tests for Task.load_state()."""

    async def test_noop_when_state_file_none(self) -> None:
        """load_state() should do nothing when state_file is None."""
        config = _make_config()
        task = _make_task(config)
        assert task.state_file is None
        await task.load_state()
        assert task.last_msg_id == 0

    async def test_noop_when_state_file_missing(self, tmp_path: Path) -> None:
        """load_state() should do nothing when state file does not exist."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.state_file = tmp_path / "@test_channel.json"
        await task.load_state()
        assert task.last_msg_id == 0

    async def test_loads_last_id_from_existing_file(self, tmp_path: Path) -> None:
        """load_state() should read last_id from an existing state file."""
        state_file = tmp_path / "@test_channel.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"last_id": 99}), encoding="utf-8")
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.state_file = state_file
        await task.load_state()
        assert task.last_msg_id == 99

    async def test_loads_max_of_existing_and_current(self, tmp_path: Path) -> None:
        """load_state() should take max of loaded last_id and current last_msg_id."""
        state_file = tmp_path / "@test_channel.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"last_id": 50}), encoding="utf-8")
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.last_msg_id = 100
        task.state_file = state_file
        await task.load_state()
        assert task.last_msg_id == 100

    async def test_raises_on_corrupted_file(self, tmp_path: Path) -> None:
        """load_state() should raise StateError when file contains invalid JSON."""
        state_file = tmp_path / "@test_channel.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("{invalid json}", encoding="utf-8")
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.state_file = state_file
        with pytest.raises(StateError, match="Failed to load state"):
            await task.load_state()

    async def test_handles_empty_file(self, tmp_path: Path) -> None:
        """load_state() should handle empty state file gracefully."""
        state_file = tmp_path / "@test_channel.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("", encoding="utf-8")
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.state_file = state_file
        await task.load_state()
        assert task.last_msg_id == 0


# ---------------------------------------------------------------------------
# save_state
# ---------------------------------------------------------------------------


class TestSaveState:
    """Tests for Task.save_state()."""

    async def test_creates_file_with_last_id(self, tmp_path: Path) -> None:
        """save_state() should create a JSON file with the current last_msg_id."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.last_msg_id = 42
        state_file = tmp_path / "@test_channel.json"
        task.state_file = state_file
        await task.save_state()
        assert state_file.exists()
        content = json.loads(state_file.read_text(encoding="utf-8"))
        assert content == {"last_id": 42}

    async def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """save_state() should overwrite an existing state file."""
        state_file = tmp_path / "@test_channel.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"last_id": 10}), encoding="utf-8")
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.last_msg_id = 99
        task.state_file = state_file
        await task.save_state()
        content = json.loads(state_file.read_text(encoding="utf-8"))
        assert content == {"last_id": 99}

    async def test_raises_on_io_error(self, tmp_path: Path) -> None:
        """save_state() should raise StateError when write fails."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.last_msg_id = 42
        mock_aiofiles = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.side_effect = OSError("Permission denied")
        mock_aiofiles.open.return_value = mock_cm
        with patch("mko_telebot.core.task.aiofiles", mock_aiofiles):
            task.state_file = tmp_path / "state.json"
            with pytest.raises(StateError, match="Failed to save state"):
                await task.save_state()


# ---------------------------------------------------------------------------
# resolve_channel_entity
# ---------------------------------------------------------------------------


class TestResolveChannelEntity:
    """Tests for Task.resolve_channel_entity()."""

    async def test_success(self) -> None:
        """resolve_channel_entity() should set channel_entity on success."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_entity = MagicMock()
        mock_client.get_entity.return_value = mock_entity
        await task.resolve_channel_entity(mock_client)
        assert task.channel_entity is mock_entity
        mock_client.get_entity.assert_awaited_once_with("@test_channel")

    async def test_raises_on_error(self) -> None:
        """resolve_channel_entity() should raise TelegramServiceError on failure."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_client.get_entity.side_effect = ValueError("Entity not found")
        with pytest.raises(TelegramServiceError, match="Failed to resolve entity for channel"):
            await task.resolve_channel_entity(mock_client)
        assert task.channel_entity is None

    async def test_raises_on_flood_wait_error(self) -> None:
        """resolve_channel_entity() should retry on FloodWaitError before raising TelegramServiceError."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_client.get_entity.side_effect = FloodWaitError(request=None, capture=30)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(
                TelegramServiceError,
                match="Failed to resolve entity for channel.*after \\d+ attempts",
            ):
                await task.resolve_channel_entity(mock_client)

        # Should have retried max_retries times
        assert mock_client.get_entity.await_count == 3
        assert task.channel_entity is None

    async def test_retries_and_succeeds_on_flood_wait_error(self) -> None:
        """resolve_channel_entity() should retry and succeed after FloodWaitError on 2nd attempt."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_entity = MagicMock()
        # First call raises FloodWaitError, second succeeds
        mock_client.get_entity.side_effect = [
            FloodWaitError(request=None, capture=30),
            mock_entity,
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await task.resolve_channel_entity(mock_client)

        assert task.channel_entity is mock_entity
        # Two calls: first failed, second succeeded
        assert mock_client.get_entity.await_count == 2

    async def test_raises_on_connection_error(self) -> None:
        """resolve_channel_entity() should raise TelegramServiceError on connection errors."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_client.get_entity.side_effect = OSError("Connection failed")
        with pytest.raises(TelegramServiceError, match="Failed to resolve entity for channel"):
            await task.resolve_channel_entity(mock_client)
        assert task.channel_entity is None

    async def test_raises_on_timeout_error(self) -> None:
        """resolve_channel_entity() should raise TelegramServiceError on timeout errors."""
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_client.get_entity.side_effect = TimeoutError("Connection timed out")
        with pytest.raises(TelegramServiceError, match="Failed to resolve entity for channel"):
            await task.resolve_channel_entity(mock_client)
        assert task.channel_entity is None


# ---------------------------------------------------------------------------
# resolve_targets_entities
# ---------------------------------------------------------------------------


class TestResolveTargetsEntities:
    """Tests for Task.resolve_targets_entities()."""

    async def test_success(self) -> None:
        """resolve_targets_entities() should populate forward_to_entities."""
        config = _make_config(
            name="@test_channel", forward_to=["@target1", "@target2"]
        )
        task = _make_task(config)
        mock_client = AsyncMock()
        entity1, entity2 = MagicMock(), MagicMock()
        mock_client.get_entity.side_effect = [entity1, entity2]
        await task.resolve_targets_entities(mock_client)
        assert task.forward_to_entities == [entity1, entity2]

    async def test_raises_on_error(self) -> None:
        """resolve_targets_entities() should raise TelegramServiceError on failure."""
        config = _make_config(
            name="@test_channel", forward_to=["@target1", "@target2"]
        )
        task = _make_task(config)
        mock_client = AsyncMock()
        entity1 = MagicMock()
        mock_client.get_entity.side_effect = [entity1, ValueError("Not found")]
        with pytest.raises(TelegramServiceError, match="Failed to resolve entity for target"):
            await task.resolve_targets_entities(mock_client)
        # No partial state - atomic assignment means forward_to_entities remains empty
        assert task.forward_to_entities == []

    async def test_handles_empty_targets(self) -> None:
        """resolve_targets_entities() should handle empty forward_to list."""
        config = _make_config(name="@test_channel", forward_to=[])
        task = _make_task(config)
        mock_client = AsyncMock()
        await task.resolve_targets_entities(mock_client)
        assert task.forward_to_entities == []
        mock_client.get_entity.assert_not_called()

    async def test_calls_sleep_between_resolutions(self) -> None:
        """resolve_targets_entities() should call asyncio.sleep between entity resolutions."""
        config = _make_config(
            name="@test_channel", forward_to=["@target1", "@target2"]
        )
        task = _make_task(config)
        mock_client = AsyncMock()
        entity1, entity2 = MagicMock(), MagicMock()
        mock_client.get_entity.side_effect = [entity1, entity2]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await task.resolve_targets_entities(mock_client)

        # Sleep is called after each successful resolution (rate limiting)
        assert mock_sleep.await_count == 2

    async def test_raises_on_flood_wait_error(self) -> None:
        """resolve_targets_entities() should retry on FloodWaitError before raising TelegramServiceError."""
        config = _make_config(
            name="@test_channel", forward_to=["@target1", "@target2"]
        )
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_client.get_entity.side_effect = FloodWaitError(request=None, capture=30)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(
                TelegramServiceError,
                match="Failed to resolve target entities for channel.*after \\d+ attempts",
            ):
                await task.resolve_targets_entities(mock_client)

        # Should have retried max_retries times for first target
        assert mock_client.get_entity.await_count == 3
        assert task.forward_to_entities == []

    async def test_retries_and_succeeds_on_flood_wait_error(self) -> None:
        """resolve_targets_entities() should retry and succeed after FloodWaitError on 2nd attempt."""
        config = _make_config(
            name="@test_channel", forward_to=["@target1"]
        )
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_entity = MagicMock()
        # First call raises FloodWaitError, second succeeds (for single target)
        mock_client.get_entity.side_effect = [
            FloodWaitError(request=None, capture=30),
            mock_entity,
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await task.resolve_targets_entities(mock_client)

        assert task.forward_to_entities == [mock_entity]
        assert mock_client.get_entity.await_count == 2

    async def test_error_on_first_target_stops_resolution(self) -> None:
        """resolve_targets_entities() should stop on first error without resolving remaining targets."""
        config = _make_config(
            name="@test_channel", forward_to=["@target1", "@target2", "@target3"]
        )
        task = _make_task(config)
        mock_client = AsyncMock()
        mock_client.get_entity.side_effect = ValueError("Not found")

        with pytest.raises(TelegramServiceError, match="Failed to resolve entity for target"):
            await task.resolve_targets_entities(mock_client)

        # Only one call should be made before error
        mock_client.get_entity.assert_awaited_once_with("@target1")
        assert task.forward_to_entities == []

    async def test_atomic_assignment_all_or_nothing(self) -> None:
        """resolve_targets_entities() should only assign forward_to_entities on complete success."""
        config = _make_config(
            name="@test_channel", forward_to=["@target1", "@target2"]
        )
        task = _make_task(config)
        mock_client = AsyncMock()
        entity1 = MagicMock()
        # First succeeds, second fails
        mock_client.get_entity.side_effect = [entity1, ValueError("Not found")]

        with pytest.raises(TelegramServiceError, match="Failed to resolve entity for target"):
            await task.resolve_targets_entities(mock_client)

        # Atomic behavior: no partial state assigned
        assert task.forward_to_entities == []


# ---------------------------------------------------------------------------
# Integration: state persistence round-trip
# ---------------------------------------------------------------------------


class TestStatePersistence:
    """Integration tests for save_state + load_state round-trip."""

    async def test_save_then_load_round_trip(self, tmp_path: Path) -> None:
        """Save state then load it back should preserve last_msg_id."""
        state_file = tmp_path / "@test_channel.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.last_msg_id = 77
        task.state_file = state_file
        await task.save_state()
        task2 = _make_task(config)
        task2.state_file = state_file
        await task2.load_state()
        assert task2.last_msg_id == 77

    async def test_reload_keeps_max_id(self, tmp_path: Path) -> None:
        """Reloading should keep the max of stored and current last_msg_id."""
        state_file = tmp_path / "@test_channel.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        config = _make_config(name="@test_channel")
        task = _make_task(config)
        task.last_msg_id = 50
        task.state_file = state_file
        await task.save_state()
        task2 = _make_task(config)
        task2.last_msg_id = 30
        task2.state_file = state_file
        await task2.load_state()
        assert task2.last_msg_id == 50
        task3 = _make_task(config)
        task3.last_msg_id = 100
        task3.state_file = state_file
        await task3.load_state()
        assert task3.last_msg_id == 100