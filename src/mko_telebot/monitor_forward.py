"""Message processing and forwarding module.

Provides functions to process messages and forward matched content to targets.
"""

import asyncio
import logging
import random
from collections.abc import Sequence
from typing import Any

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError, WorkerBusyTooLongRetryError
from telethon.hints import Entity
from telethon.tl.custom.message import Message

from mko_telebot.core import Task, search_match
from mko_telebot.core.errors import TelegramServiceError
from mko_telebot.core.models import TelepostSettings
from .monitor_client import build_message_link, build_sender_tag

def _calculate_retry_delay(attempt: int, is_flood_wait: bool, seconds: int = 0) -> float:
    """Calculate backoff delay based on error type.

    Args:
        attempt: Current retry attempt number (0-indexed).
        is_flood_wait: True if error is FloodWaitError, False for other errors.
        seconds: Seconds from FloodWaitError, ignored for other error types.

    Returns:
        Wait time in seconds with exponential backoff and jitter.
    """
    if is_flood_wait:
        return seconds + random.uniform(5, 10) + (2 ** attempt)
    return (2 ** attempt) + random.uniform(0, 3)

logger = logging.getLogger(__name__)


def _group_messages_by_album(
    messages: Sequence[Message],
) -> dict[int | None, dict[str, Any]]:
    """Group messages by their album_id for combined processing.

    Groups messages that share the same grouped_id (album) and extracts
    their text content and media for keyword matching and forwarding.

    Args:
        messages: Sequence of Telethon Message objects to group.

    Returns:
        Dictionary mapping group_id to content dict with 'msg', 'text', and 'media' lists.
    """
    msg_content: dict[int | None, dict[str, Any]] = {}
    for msg in messages:
        group_id = msg.grouped_id if getattr(msg, "grouped_id", None) else msg.id

        if group_id not in msg_content:
            msg_content[group_id] = {"msg": msg, "text": [], "media": []}

        if getattr(msg, "message", None):
            msg_content[group_id]["text"].append(msg.message)

        if getattr(msg, "media", None):
            msg_content[group_id]["media"].append(msg.media)
            # Extract media caption for keyword matching
            media_caption = getattr(msg.media, "caption", None)
            if media_caption:
                msg_content[group_id]["text"].append(media_caption)

    return msg_content


async def _send_message_to_target(
    client: TelegramClient,
    target: Entity,
    caption: str,
    msg_media: list[Any] | None,
) -> None:
    """Send message or media to target entity."""
    if msg_media:
        await client.send_file(target, msg_media, caption=caption, link_preview=False)
    else:
        await client.send_message(target, caption or "", link_preview=False)




async def _send_with_retry(
    client: TelegramClient,
    target: Entity,
    caption: str,
    msg_media: list[Any] | None,
    max_tries: int,
    channel_name: str,
) -> bool:
    """Send message to target with retry logic for transient Telegram API errors."""
    for attempt in range(max_tries):
        try:
            await _send_message_to_target(client, target, caption, msg_media)
            logger.info(f"{channel_name}: forwarded message to {getattr(target, 'id', target)}")
            return True

        except FloodWaitError as e:
            wait_time = _calculate_retry_delay(attempt, is_flood_wait=True, seconds=e.seconds)
            logger.warning(
                f"Flood wait {e.seconds}s, retry {attempt + 1}/{max_tries} "
                f"for {getattr(target, 'id', target)}"
            )
            await asyncio.sleep(wait_time)

        except (WorkerBusyTooLongRetryError, RPCError) as e:
            wait_time = _calculate_retry_delay(attempt, is_flood_wait=False)
            logger.warning(
                f"{type(e).__name__} {e}, retry {attempt + 1}/{max_tries} "
                f"for {getattr(target, 'id', target)}"
            )
            await asyncio.sleep(wait_time)

    return False


async def forward_to_users(
    msg: Message,
    msg_text: str | None,
    msg_media: list[Any],
    task: Task,
    client: TelegramClient,
    settings: TelepostSettings,
) -> None:
    """Forward message or album to targets, appending author and link."""
    link = build_message_link(msg)
    sender_tag = await build_sender_tag(msg)
    caption = _build_caption(msg_text, sender_tag, link)

    for target in task.forward_to_entities:
        success = await _send_with_retry(
            client, target, caption, msg_media or None,
            settings.telethon.max_retries, task.channel_name,
        )
        if not success:
            logger.error(
                f"Failed to send to {getattr(target, 'id', target)} "
                f"after {settings.telethon.max_retries} attempts"
            )
        await asyncio.sleep(random.uniform(5, 10))


def _build_caption(msg_text: str | None, sender_tag: str | None, link: str | None) -> str:
    """Build caption for forwarded message from text, sender tag, and link."""
    caption_lines = []
    if msg_text:
        caption_lines.append(msg_text)
    if sender_tag:
        caption_lines.append(f"Author: {sender_tag}")
    if link:
        caption_lines.append(f"Source: {link}")
    return "\n\n".join(caption_lines).strip()


async def process_messages(
    messages: list[Message],
    task: Task,
    client: TelegramClient,
    settings: TelepostSettings,
) -> None:
    """Process messages, group albums, check keywords, and forward matches.

    Args:
        messages (list[telethon.tl.custom.message.Message]): List of Telethon messages.
        task (Task): Task object with configuration for a specific channel.
        client (TelegramClient): The Telethon client instance.
        settings (TelepostSettings): Application settings.

    """
    if not messages:
        return

    msg_content = _group_messages_by_album(messages)

    for album_id, content in msg_content.items():
        msg_text = "\n".join(content.get("text", []))

        if msg_text and (not task.keywords or any(search_match(msg_text, kw) for kw in task.keywords)):
            logger.debug(f"Keyword match in {task.channel_name}, message {album_id}")

            await forward_to_users(
                content["msg"],
                msg_text,
                content.get("media", []),
                task,
                client,
                settings,
            )


async def _fetch_messages(
    client: TelegramClient,
    task: Task,
) -> list[Message]:
    """Fetch messages from channel with error handling."""
    assert task.channel_entity is not None  # Checked in process_task before calling
    min_id = max(1, task.last_msg_id - task.overlap + 1)
    new_messages: list[Message] = []

    try:
        messages_iter = client.iter_messages(
            task.channel_entity,
            min_id=min_id,
            offset_date=task.offset_date,
            limit=task.history_limit,
            reverse=True,
        )

        async for msg in messages_iter:
            if msg.id <= task.last_msg_id:
                continue
            new_messages.append(msg)

    except FloodWaitError as e:
        logger.warning(f"Flood wait {e.seconds}s while fetching {task.channel_name}")
        await asyncio.sleep(e.seconds + random.uniform(10, 15))
        return []

    except WorkerBusyTooLongRetryError as e:
        logger.warning(f"Worker busy retry while fetching {task.channel_name}: {e}")
        await asyncio.sleep(random.uniform(5, 10))
        return []

    except RPCError as e:
        logger.warning(
            f"RPC error during message fetching: {type(e).__name__} in {task.channel_name}"
        )
        await asyncio.sleep(5)
        raise TelegramServiceError(
            f"Failed to fetch messages for {task.channel_name}: {e}"
        ) from e

    except TelegramServiceError as e:
        logger.error(f"Error fetching messages in {task.channel_name}: {e}")
        return []

    return new_messages


async def process_task(task: Task, client: TelegramClient, settings: TelepostSettings) -> None:
    """Fetch and process recent messages from a specific Telegram channel."""
    logger.debug(f"{task.channel_name} is processed")

    if task.channel_entity is None:
        logger.error(f"Channel entity not resolved for {task.channel_name}")
        return

    new_messages = await _fetch_messages(client, task)

    if new_messages:
        await process_messages(new_messages, task, client, settings)
        task.last_msg_id = max(msg.id for msg in new_messages)
        logger.info(
            f"{task.channel_name}: {len(new_messages)} new messages processed, "
            f"last_msg_id={task.last_msg_id}"
        )
    else:
        logger.info(f"{task.channel_name}: no new messages found")
