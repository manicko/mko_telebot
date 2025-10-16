import asyncio
import random
import logging.config
import time
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from pathlib import Path
from mko_telebot.core import CONFIG, PATHS, Task, search_match, utils

logging.config.dictConfig(CONFIG.LOGGING)
logger = logging.getLogger('monitor')

is_user = CONFIG.TELETHON_API.is_user
phone_or_token = CONFIG.TELETHON_API.phone_or_token

if 'session' in CONFIG.TELETHON_API.client:
    session_path = Path.joinpath(PATHS.session_dir, CONFIG.TELETHON_API.client['session'])
    if session_path.suffix != '.session':
        session_path = session_path.with_suffix('.session')
    utils.ensure_path_exists(session_path)
    CONFIG.TELETHON_API.client['session'] = session_path

client = TelegramClient(**CONFIG.TELETHON_API.client)
task_queue = asyncio.Queue()
process_lock = asyncio.Lock()


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


async def process_messages(messages, task: Task):
    """Process messages, group albums, check keywords, and forward matches.

    Args:
        messages (list): List of Telethon Message objects.
        task (Task): Task object with configuration for a specific channel.
    """
    if not messages:
        return

    albums_msgs = {}
    albums_txt = {}

    for msg in messages:
        try:
            group_id = msg.grouped_id if getattr(msg, "grouped_id", None) else msg.id
            albums_msgs.setdefault(group_id, []).append(msg)
            if getattr(msg, "message", None):
                albums_txt.setdefault(group_id, []).append(msg.message)
            elif getattr(msg, "media", None) and getattr(msg.media, "caption", None):
                albums_txt.setdefault(group_id, []).append(msg.media.caption)
        except Exception as e:
            logger.exception(f"Error while processing message {getattr(msg, 'id', None)} "
                             f"from {task.channel_name}: {e}")

    for album_id, album_msgs in albums_msgs.items():
        text = " ".join(albums_txt.get(album_id, []))
        if text and any(search_match(text, kw) for kw in task.keywords):
            logger.debug(f"Match found in message {album_id} from {task.channel_name}")
            await forward_to_users(album_msgs, task)


async def forward_to_users(msgs, task: Task):
    """Forward messages to the target users or groups.

    Args:
        msgs (list): List of Telethon Message objects to forward.
        task (Task): Task object containing forwarding configuration.
    """
    for target in task.forward_to_entities:
        try:
            await client.forward_messages(target, msgs)
            logger.info(f"Forwarded {len(msgs)} messages to {getattr(target, 'id', target)}")
            await asyncio.sleep(random.uniform(5, 10))
        except FloodWaitError as e:
            logger.warning(f"Flood wait {e.seconds}s while forwarding to {getattr(target, 'id', target)}")
            await asyncio.sleep(e.seconds + random.uniform(5, 10))
        except Exception as e:
            logger.exception(f"Failed to forward messages to {getattr(target, 'id', target)}: {e}")


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
            reverse=True
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
        logger.info(f"{task.channel_name}: {len(new_messages)} new messages are processed, "
                    f"last_msg_id={task.last_msg_id}")
    else:
        logger.info(f"{task.channel_name}: no new messages found")


async def reschedule_task(task: Task, queue: asyncio.Queue):
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


async def process_and_reschedule(task: Task, queue: asyncio.Queue):
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
    defaults = channels_config.get('DEFAULTS', {})
    channels = [ch for ch in channels_config if ch != 'DEFAULTS']

    stagger_start_seconds = getattr(channels_config, "stagger_start_seconds", 3)

    for channel in channels:
        channel_settings = {**defaults, **channels_config[channel]}
        task = Task(
            channel=channel,
            forward_to=channel_settings.get('forward_to', []),
            keywords=channel_settings.get('keywords', []),
            scan_interval=channel_settings.get('scan_interval', 420),
            history_limit=channel_settings.get('history_limit', 50),
            history_days=channel_settings.get('history_days', None),
            overlap=channel_settings.get('overlap', 5),
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


if __name__ == "__main__":
    try:
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        logger.info("Мониторинг остановлен пользователем.")
