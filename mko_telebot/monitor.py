import asyncio
import logging.config
import random
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError

from mko_telebot.core import CONFIG, PATHS, Task, search_match, utils

logging.config.dictConfig(CONFIG.LOGGING.model_dump())
logger = logging.getLogger(__name__)

is_user = CONFIG.TELETHON_API.is_user
phone_or_token = CONFIG.TELETHON_API.phone_or_token

if "session" in CONFIG.TELETHON_API.client:
    session_path = Path.joinpath(
        PATHS.session_dir, CONFIG.TELETHON_API.client["session"]
    )
    if session_path.suffix != ".session":
        session_path = session_path.with_suffix(".session")
    utils.ensure_path_exists(session_path)
    CONFIG.TELETHON_API.client["session"] = session_path

client: TelegramClient = TelegramClient(**CONFIG.TELETHON_API.client)
task_queue: asyncio.Queue[Task] = asyncio.Queue()
process_lock: asyncio.Lock = asyncio.Lock()


async def start_client():
    """Initialize and start the Telethon client.

    Returns:
        bool: True if client started successfully, False otherwise.
    """
    try:
        if is_user:
            await client.start(phone=phone_or_token)
        else:
            await client.start(bot_token=phone_or_token)
        logger.info("Telethon client started successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to start Telethon client: {e}")
        return False


def build_message_link(msg):
    """Build a Telegram t.me link to the message if possible.

    Args:
        msg: telethon.tl.custom.message.Message

    Returns:
        Optional[str]: URL like 'https://t.me/username/123' or None.
    """
    try:
        chat = getattr(msg, "chat", None)
        if chat and getattr(chat, "username", None):
            return f"https://t.me/{chat.username}/{msg.id}"
        return None
    except Exception as e:
        logger.exception(f"Error while building message link: {e}")
        return None


async def build_sender_tag(msg):
    """Return sender username or display name.

    Args:
        msg: telethon.tl.custom.message.Message

    Returns:
        str: '@username' if available, otherwise 'First Last' or empty string.
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
    except Exception as e:
        logger.exception(f"Error while building sender tag: {e}")
        return ""


async def forward_to_users(msg, msg_text, msg_media, task: Task):
    """Forward message or album to targets, appending author and link.

    Behavior:
        - If msg_media is not empty -> send media group via send_file(target, msg_media, caption=caption).
        - Otherwise -> send plain text message via send_message.
        - Caption includes text, author, and message link (if available).

    Args:
        msg (telethon.tl.custom.message.Message): The main message object (used to extract author and link).
        msg_text (str): Text content (combined text and captions).
        msg_media (list): List of message.media objects, if any.
        task (Task): Task configuration including forwarding targets.
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

    # Send to each target
    for target in task.forward_to_entities:
        try:
            if msg_media:
                # send_file will create an album if files is a list of medias
                await client.send_file(
                    target, msg_media, caption=caption or None, link_preview=False
                )
            else:
                # purely text messages
                await client.send_message(target, caption or "", link_preview=False)

            logger.info(
                f"{task.channel_name}: forwarded message to {getattr(target, 'id', target)}"
            )
            await asyncio.sleep(random.uniform(5, 10))
        except FloodWaitError as e:
            logger.warning(
                f"Flood wait {e.seconds}s while sending to {getattr(target, 'id', target)}"
            )
            await asyncio.sleep(e.seconds + random.uniform(5, 10))
        except Exception as e:
            logger.exception(
                f"Failed to send messages to {getattr(target, 'id', target)}: {e}"
            )


async def process_messages(messages, task: Task):
    """Process messages, group albums, check keywords, and forward matches.

    Args:
        messages (list[telethon.tl.custom.message.Message]): List of Telethon messages.
        task (Task): Task object with configuration for a specific channel.
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

        except Exception as e:
            logger.exception(
                f"Error processing message {getattr(msg, 'id', None)} "
                f"from {task.channel_name}: {e}"
            )

    for album_id, content in msg_content.items():
        msg_text = "\n".join(content.get("text", []))
        if msg_text and any(search_match(msg_text, kw) for kw in task.keywords):
            logger.debug(f"Keyword match in {task.channel_name}, message {album_id}")
            await forward_to_users(
                content["msg"], msg_text, content.get("media", []), task
            )


async def process_task(task: Task):
    """Fetch and process recent messages from a specific Telegram channel.

    Args:
        task (Task): Task object representing the channel to process.
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
        await asyncio.sleep(e.seconds + random.uniform(5, 15))
    except Exception as e:
        logger.error(f"Error fetching messages in {task.channel_name}: {e}")
        return

    if new_messages:
        await process_messages(new_messages, task)
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


async def process_and_reschedule(task: Task, queue: asyncio.Queue[Task]):
    """Process a single task, save its state, and reschedule it asynchronously.

    Args:
        task (Task): Task object to process.
        queue (asyncio.Queue): Queue used for scheduling tasks.
    """
    async with process_lock:
        await process_task(task)
        await task.save_state()
    asyncio.create_task(reschedule_task(task, queue))


async def main_loop():
    """Main monitoring loop that sequentially processes channels."""
    channels_delay = CONFIG.MONITORING.channels_delay
    channels_config = CONFIG.MONITORING.channels
    defaults = channels_config.get("DEFAULTS", {})
    channels = [ch for ch in channels_config if ch != "DEFAULTS"]

    stagger_start_seconds = getattr(channels_config, "stagger_start_seconds", 3)

    for channel in channels:
        channel_settings = {**defaults, **channels_config[channel]}
        task = Task(
            channel=channel,
            forward_to=channel_settings.get("forward_to", []),
            keywords=channel_settings.get("keywords", []),
            scan_interval=channel_settings.get("scan_interval", 420),
            history_limit=channel_settings.get("history_limit", 50),
            history_days=channel_settings.get("history_days", None),
            overlap=channel_settings.get("overlap", 5),
        )
        await task.resolve_channel_entity(client)
        task.resolve_state_file()
        await task.load_state()
        await task.resolve_targets_entities(client)
        await asyncio.sleep(random.uniform(0, stagger_start_seconds))
        await task_queue.put(task)

    logger.info("Monitoring loop started.")

    while True:
        task = await task_queue.get()
        asyncio.create_task(process_and_reschedule(task, task_queue))
        await asyncio.sleep(channels_delay)


async def run_monitor():
    """Run the monitoring system."""
    if await start_client():
        await main_loop()


def launcher():
    try:
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user.")


if __name__ == "__main__":
    launcher()
