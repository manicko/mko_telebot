# task.py
import asyncio
import json
import logging
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiofiles  # async I/O

# mko_telebot/core/utils.py
from mko_telebot.core.utils import ensure_path_exists
from mko_telebot.core.paths import APP_PATHS
from mko_telebot.core.errors import TelegramServiceError, StateError
from mko_telebot.core.channels import ChannelConfig
from telethon import TelegramClient
from telethon.hints import Entity

logger = logging.getLogger(__name__)

# Directory for persisting per-channel state files
state_dir = APP_PATHS.state_dir


class Task:
    """Represents a monitoring task for a single Telegram channel.

    The Task object holds configuration and runtime state for scanning a single
    channel: the channel identifier, targets to forward matched messages to,
    keyword filters, scan intervals and state persistence (last processed message id).

    Attributes:
        channel_name: Channel identifier used to resolve the channel entity.
        channel_entity: Telethon entity for the channel (resolved at runtime).
        forward_to: List of identifiers to forward matched messages to (raw config values).
        forward_to_entities: List of resolved Telethon entity objects for targets.
        keywords: List of keyword/pattern strings used for matching.
        scan_interval: Interval (seconds) between scans for this channel.
        history_limit: Optional maximum number of messages to fetch per scan.
        history_days: Optional number of days in the past to limit the scan window.
        offset_date: Computed datetime (UTC) from which to start scanning if history_days set.
        last_msg_id: Last processed message id (used to avoid reprocessing).
        overlap: Number of message ids to overlap between runs (to avoid misses).
        state_file: Path to the JSON file used for persisting last_msg_id.
    """

    def __init__(self, config: ChannelConfig, last_msg_id: int = 0) -> None:
        """Initialize Task from a ChannelConfig instance."""
        self.channel_name: str = config.name
        self.channel_entity: Entity | None = None
        self.forward_to: list[str] = config.forward_to
        self.forward_to_entities: list[Entity] = []
        self.keywords: list[str] = config.keywords
        self.scan_interval: int = config.scan_interval
        self.history_limit: int = config.history_limit
        self.history_days: int | None = config.history_days
        # offset_date computed from history_days (if provided)
        self.state_file: Path | None = None
        self.offset_date: datetime | None = None
        self.set_offset_date()
        # ensure last_msg_id is int and non-null
        self.last_msg_id: int = last_msg_id or 0
        self.overlap: int = config.overlap

    async def resolve_targets_entities(self, client: TelegramClient) -> None:
        """Resolve each forward target to a Telethon entity and store them.

        All entities are resolved into a temporary list first, then assigned
        atomically to forward_to_entities. This ensures no partial state remains
        if any resolution fails.
        """
        entities: list[Entity] = []
        for ent in self.forward_to:
            try:
                result = await client.get_entity(ent)
                if isinstance(result, list):
                    continue
                entities.append(result)
                # Small randomized pause to look "human" and avoid rate limits
                await asyncio.sleep(random.uniform(0, 3))
            except Exception as e:
                logger.error(
                    f"Failed to resolve entity for target {ent} in channel {self.channel_name}: {e}"
                )
                raise TelegramServiceError(
                    f"Failed to resolve entity for target {ent}"
                ) from e
        self.forward_to_entities = entities

    async def resolve_channel_entity(self, client: TelegramClient) -> None:
        """Resolve channel_name to a Telethon channel entity."""
        try:
            result = await client.get_entity(self.channel_name)
            # get_entity can return Entity or List[Entity], we expect single Entity
            if isinstance(result, list):
                raise TelegramServiceError(
                    f"Unexpected list result for channel {self.channel_name}"
                )
            self.channel_entity = result
        except Exception as e:
            logger.error(
                f"Failed to resolve entity for channel {self.channel_name}: {e}"
            )
            raise TelegramServiceError(
                f"Failed to resolve entity for channel {self.channel_name}"
            ) from e

    def resolve_state_file(self) -> None:
        """Determine and create (if needed) the path to the state file for this channel."""
        self.state_file = state_dir / f"{self.channel_name}.json"
        try:
            ensure_path_exists(self.state_file)
            logger.debug(
                f"State file for channel {self.channel_name} is ready: {self.state_file}"
            )
        except Exception as e:
            logger.error(
                f"Failed to create or verify state file path {self.state_file}: {e}"
            )
            raise StateError(
                f"Failed to create or verify state file for channel {self.channel_name}"
            ) from e

    def set_offset_date(self) -> None:
        """Compute and store offset_date as (now - history_days) in UTC."""
        self.offset_date = None
        if not self.history_days:
            return
        try:
            days = int(self.history_days)
        except (TypeError, ValueError) as e:
            logger.error(
                f"Invalid history_days for {self.channel_name}/{self.state_file}: {e}"
            )
            return
        self.offset_date = datetime.now(UTC) - timedelta(days=days)
        logger.debug(
            f"Offset date for {self.channel_name} set to {self.offset_date.isoformat()}"
        )

    # ===== State persistence functions =====
    async def load_state(self) -> None:
        """Load the last processed message id from the state file (if it exists)."""
        if self.state_file and self.state_file.exists():
            try:
                async with aiofiles.open(self.state_file, encoding="utf-8") as f:
                    content = await f.read()
                state = json.loads(content) if content else {}
                self.last_msg_id = max(self.last_msg_id, state.get("last_id", 0))
                logger.debug(
                    f"State for channel {self.channel_name} restored, last_id={self.last_msg_id}"
                )
            except Exception as e:
                logger.error(
                    f"Error loading state for channel {self.channel_name}: {e}"
                )
                raise StateError(
                    f"Failed to load state for channel {self.channel_name}"
                ) from e
        else:
            logger.debug(f"No saved state for {self.channel_name}, starting fresh")

    async def save_state(self) -> None:
        """Persist current last_msg_id to the state file."""
        try:
            async with aiofiles.open(str(self.state_file), "w", encoding="utf-8") as f:
                await f.write(json.dumps({"last_id": self.last_msg_id}))
            logger.debug(
                f"State for channel {self.channel_name} saved (last_id={self.last_msg_id})"
            )
        except Exception as e:
            logger.error(f"Error saving state for channel {self.channel_name}: {e}")
            raise StateError(
                f"Failed to save state for channel {self.channel_name}"
            ) from e