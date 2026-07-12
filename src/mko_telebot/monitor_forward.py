"""Message processing and forwarding module.

Provides functions to process messages and forward matched content to targets.
"""

import asyncio
import logging
import random
from typing import Any

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError, WorkerBusyTooLongRetryError
from telethon.tl.custom.message import Message

from mko_telebot.core import Task, search_match
from mko_telebot.core.errors import TelegramServiceError
from mko_telebot.core.models import TelepostSettings
from .monitor_client import build_message_link, build_sender_tag

logger = logging.getLogger(__name__)


async def forward_to_users(
    msg: Message,
    msg_text: str | None,
    msg_media: list[Any],
    task: Task,
    client: TelegramClient,
    settings: TelepostSettings,
) -> None:
    """Forward message or album to targets, appending author and link.

    Implements retry logic with exponential backoff and jitter for transient
    Telegram API errors (FloodWaitError, WorkerBusyTooLongRetryError, RPCError).

    Args:
        msg (telethon.tl.custom.message.Message): The main message object (used to extract author and link).
        msg_text (str): Text content (combined text and captions).
        msg_media (list): List of message.media objects, if any.
        task (Task): Task configuration including forwarding targets.
        client (TelegramClient): The Telethon client instance.
        settings (TelepostSettings): Application settings (used for max_retries).

    """

    link = build_message_link(msg)

    sender_tag = await build_sender_tag(msg)

    caption_lines = []

    if msg_text:
        caption_lines.append(msg_text)

    if sender_tag:
        caption_lines.append(f"Author: {sender_tag}")

    if link:
        caption_lines.append(f"Source: {link}")

    caption = "\n\n".join(caption_lines).strip()

    # Send to each target with retry loop

    for target in task.forward_to_entities:
        max_tries = settings.telethon.max_retries

        for attempt in range(max_tries):
            try:
                if msg_media:
                    await client.send_file(
                        target, msg_media, caption=caption or None, link_preview=False
                    )

                else:
                    await client.send_message(target, caption or "", link_preview=False)

                logger.info(
                    f"{task.channel_name}: forwarded message to {getattr(target, 'id', target)}"
                )

                break

            except FloodWaitError as e:
                wait_time = e.seconds + random.uniform(5, 10) + (2**attempt)

                logger.warning(
                    f"Flood wait {e.seconds}s, retry {attempt + 1}/{max_tries} "
                    f"for {getattr(target, 'id', target)}"
                )

                await asyncio.sleep(wait_time)

            except WorkerBusyTooLongRetryError as e:
                wait_time = (2**attempt) + random.uniform(0, 3)

                logger.warning(
                    f"Worker busy retry error {e}, retry {attempt + 1}/{max_tries} "
                    f"for {getattr(target, 'id', target)}"
                )

                await asyncio.sleep(wait_time)

            except RPCError as e:
                wait_time = (2**attempt) + random.uniform(0, 3)

                logger.warning(
                    f"RPC error {e}, retry {attempt + 1}/{max_tries} "
                    f"for {getattr(target, 'id', target)}"
                )

                await asyncio.sleep(wait_time)

        else:
            logger.error(
                f"Failed to send to {getattr(target, 'id', target)} "
                f"after {max_tries} attempts"
            )

        await asyncio.sleep(random.uniform(5, 10))


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

    msg_content = {}

    for msg in messages:
        group_id = msg.grouped_id if getattr(msg, "grouped_id", None) else msg.id

        if group_id not in msg_content:
            msg_content[group_id] = {"msg": msg, "text": [], "media": []}

        if getattr(msg, "message", None):
            msg_content[group_id]["text"].append(msg.message)

        if getattr(msg, "media", None):
            if getattr(msg.media, "caption", None):
                msg_content[group_id]["text"].append(msg.media.caption)

            msg_content[group_id]["media"].append(msg.media)

    for album_id, content in msg_content.items():
        msg_text = "\n".join(content.get("text", []))

        if msg_text and any(search_match(msg_text, kw) for kw in task.keywords):
            logger.debug(f"Keyword match in {task.channel_name}, message {album_id}")

            await forward_to_users(
                content["msg"],
                msg_text,
                content.get("media", []),
                task,
                client,
                settings,
            )


async def process_task(task: Task, client: TelegramClient, settings: TelepostSettings):
    """Fetch and process recent messages from a specific Telegram channel.

    Args:
        task (Task): Task object representing the channel to process.
        client (TelegramClient): The Telethon client instance.
        settings (TelepostSettings): Application settings.

    """

    logger.debug(f"{task.channel_name} is processed")

    min_id = max(1, task.last_msg_id - task.overlap + 1)

    new_messages = []

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

    except WorkerBusyTooLongRetryError as e:
        logger.warning(f"Worker busy retry while fetching {task.channel_name}: {e}")
        await asyncio.sleep(random.uniform(5, 10))

    except TelegramServiceError as e:
        logger.error(f"Error fetching messages in {task.channel_name}: {e}")

        return

    if new_messages:
        await process_messages(new_messages, task, client, settings)

        task.last_msg_id = max(msg.id for msg in new_messages)

        logger.info(
            f"{task.channel_name}: {len(new_messages)} new messages processed, "
            f"last_msg_id={task.last_msg_id}"
        )

    else:
        logger.info(f"{task.channel_name}: no new messages found")