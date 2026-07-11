"""

Telegram channel monitoring and forwarding module.



Provides functions to create a Telegram client, monitor channels,

process messages, and forward matched content to configured targets.

"""

import asyncio

import logging

import logging.config

from typing import Any
import random

from pathlib import Path


from telethon import TelegramClient

from telethon.errors import FloodWaitError, RPCError


from mko_telebot.core import APP_PATHS, Task, search_match

from mko_telebot.core.errors import TelegramAuthError, TelegramServiceError

from mko_telebot.core.models import TelepostSettings

from telethon.tl.custom.message import Message


logger = logging.getLogger(__name__)


def create_client(settings: TelepostSettings) -> TelegramClient:
    """Create a Telethon client from settings.



    Session files are stored in APP_PATHS.session_dir.



    Args:

        settings: Application settings with Telethon configuration.



    Returns:

        Configured TelegramClient instance.

    """

    client_config = settings.telethon.client.model_dump()

    session = client_config.get("session", "first_session")

    session_path = Path(session)

    if not session_path.suffix:
        session_path = session_path.with_suffix(".session")

    session_path = APP_PATHS.session_dir / session_path.name

    session_path.parent.mkdir(parents=True, exist_ok=True)

    client_config["session"] = str(session_path)

    return TelegramClient(**client_config)


async def start_client(client: TelegramClient, settings: TelepostSettings) -> bool:
    """Initialize and start the Telethon client.



    Args:

        client: The Telethon client instance.

        settings: Application settings with auth configuration.



    Returns:

        True if client started successfully, False otherwise.

    """

    try:
        if settings.telethon.is_user:
            await client.start(
                phone=settings.telethon.phone_or_token.get_secret_value()
            )

        else:
            await client.start(
                bot_token=settings.telethon.phone_or_token.get_secret_value()
            )

        logger.info("Telethon client started successfully.")

        return True

    except (TelegramAuthError, TelegramServiceError) as e:
        logger.error(f"Failed to start Telethon client: {e}")

        return False


def build_message_link(msg: Message) -> str | None:
    """Build a Telegram t.me link to the message if possible.



    Args:

        msg: telethon.tl.custom.message.Message



    Returns:

        URL like 'https://t.me/username/123' or None.

    """

    try:
        chat = getattr(msg, "chat", None)

        if chat and getattr(chat, "username", None):
            return f"https://t.me/{chat.username}/{msg.id}"

        return None

    except TelegramServiceError as e:
        logger.exception(f"Error while building message link: {e}")

        return None


async def build_sender_tag(msg: Message) -> str:
    """Return sender username or display name.



    Args:

        msg: telethon.tl.custom.message.Message



    Returns:

        '@username' if available, otherwise 'First Last' or empty string.

    """

    try:
        sender = await msg.get_sender()

        if not sender:
            return ""

        if getattr(sender, "username", None):
            return f"@{sender.username}"

        name = " ".join(
            filter(
                None,
                [
                    getattr(sender, "first_name", None),
                    getattr(sender, "last_name", None),
                ],
            )
        )

        return name.strip()

    except TelegramServiceError as e:
        logger.exception(f"Error while building sender tag: {e}")

        return ""


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

    Telegram API errors (FloodWaitError, RPCError).



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
        try:
            group_id = msg.grouped_id if getattr(msg, "grouped_id", None) else msg.id

            if group_id not in msg_content:
                msg_content[group_id] = {"msg": msg, "text": [], "media": []}

            if getattr(msg, "message", None):
                msg_content[group_id]["text"].append(msg.message)

            if getattr(msg, "media", None):
                if getattr(msg.media, "caption", None):
                    msg_content[group_id]["text"].append(msg.media.caption)

                msg_content[group_id]["media"].append(msg.media)

        except TelegramServiceError as e:
            logger.exception(
                f"Error processing message {getattr(msg, 'id', None)} "
                f"from {task.channel_name}: {e}"
            )

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


async def reschedule_task(task: Task, queue: asyncio.Queue[Task]):
    """Schedule the next run for the given channel after its scan delay.



    Args:

        task (Task): Task object to be rescheduled.

        queue (asyncio.Queue): Queue where the task will be re-added.

    """

    delay = task.scan_interval + random.uniform(10, 30)

    logger.debug(f"{task.channel_name} will return to queue in {delay:.1f}s")

    await asyncio.sleep(delay)

    await queue.put(task)

    logger.debug(f"{task.channel_name} returned to queue.")


async def process_and_reschedule(
    task: Task,
    client: TelegramClient,
    queue: asyncio.Queue[Task],
    lock: asyncio.Lock,
    settings: TelepostSettings,
):
    """Process a single task, save its state, and reschedule it asynchronously.



    Args:

        task (Task): Task object to process.

        client (TelegramClient): The Telethon client instance.

        queue (asyncio.Queue): Queue used for scheduling tasks.

        lock (asyncio.Lock): Lock to serialize task processing.

        settings (TelepostSettings): Application settings.

    """

    async with lock:
        await process_task(task, client, settings)

        await task.save_state()

    asyncio.create_task(reschedule_task(task, queue))


async def main_loop(
    settings: TelepostSettings,
    client: TelegramClient,
    queue: asyncio.Queue[Task],
    lock: asyncio.Lock,
):
    """Main monitoring loop that sequentially processes channels.



    Args:

        settings (TelepostSettings): Application settings.

        client (TelegramClient): The Telethon client instance.

        queue (asyncio.Queue): Queue for scheduling tasks.

        lock (asyncio.Lock): Lock to serialize task processing.

    """

    channels_delay = settings.channels.channels_delay

    channels = settings.channels.channels

    channels_list = list(channels.keys())

    stagger_start_seconds = settings.channels.stagger_start_seconds

    for channel_name in channels_list:
        channel_settings = channels[channel_name]

        task = Task(config=channel_settings)

        await task.resolve_channel_entity(client)

        task.resolve_state_file()

        await task.load_state()

        await task.resolve_targets_entities(client)

        await asyncio.sleep(random.uniform(0, stagger_start_seconds))

        await queue.put(task)

    logger.info("Monitoring loop started.")

    while True:
        task = await queue.get()

        asyncio.create_task(process_and_reschedule(task, client, queue, lock, settings))

        await asyncio.sleep(channels_delay)


async def run_monitor(settings: TelepostSettings, client: TelegramClient):
    """Run the monitoring system.



    Args:

        settings (TelepostSettings): Application settings.

        client (TelegramClient): The Telethon client instance.

    """

    if await start_client(client, settings):
        queue: asyncio.Queue[Task] = asyncio.Queue()

        lock: asyncio.Lock = asyncio.Lock()

        await main_loop(settings, client, queue, lock)
