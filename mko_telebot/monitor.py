# monitor.py
import asyncio
import random
from telethon import TelegramClient
from telethon.errors import FloodWaitError
import logging.config
from pathlib import Path
from mko_telebot.core import CONFIG, PATHS, Task, search_match, utils

# Настройка логирования
logging.config.dictConfig(CONFIG.LOGGING)
logger = logging.getLogger('monitor')

# Инициализация клиента
is_user = CONFIG.TELETHON_API.is_user
phone_or_token = CONFIG.TELETHON_API.phone_or_token

# Проверяем существование папки с сессиями
if 'session' in CONFIG.TELETHON_API.client:
    session_path = Path.joinpath(PATHS.session_dir, CONFIG.TELETHON_API.client['session'])
    if session_path.suffix != '.session':
        session_path = session_path.with_suffix('.session')
    utils.ensure_path_exists(session_path)
    CONFIG.TELETHON_API.client['session'] = session_path

client = TelegramClient(**CONFIG.TELETHON_API.client)

# Очередь задач
task_queue = asyncio.Queue()


async def start_client():
    """Инициализация Telethon клиента с учетом режима user/bot"""
    try:
        if is_user:
            await client.start(phone=phone_or_token)
        else:
            await client.start(bot_token=phone_or_token)
        logger.info("Клиент Telethon успешно запущен.")
        return True
    except Exception as e:
        logger.error(f"Ошибка запуска клиента: {e}")
        return False


async def process_messages(messages, task: Task):
    if not messages:
        return
    albums_msgs = {}
    albums_txt = {}
    # группируем альбомы, messages уже oldest first
    for msg in messages:
        try:
            group_id = msg.grouped_id if msg.grouped_id else msg.id
            albums_msgs.setdefault(group_id, []).append(msg)
            if hasattr(msg, 'message') and msg.message:
                albums_txt.setdefault(group_id, []).append(msg.message)
            elif hasattr(msg, 'media') and hasattr(msg.media, 'caption') and msg.media.caption:
                albums_txt.setdefault(group_id, []).append(msg.media.caption)
        except Exception as e:
            logger.exception(f"Ошибка при обработке сообщения {getattr(msg, 'id', None)} из {task.channel_name}: {e}")

    for album_id, album_msgs in albums_msgs.items():
        text = " ".join(albums_txt.get(album_id, []))
        if text and any(search_match(text, kw) for kw in task.keywords):
            logger.info(f"Найдено совпадение в сообщении {album_id} в канале {task.channel_name}")
            await asyncio.sleep(random.uniform(3, 10))
            await forward_to_users(album_msgs, task)


async def forward_to_users(msgs, task: Task):
    for target in task.forward_to_entities:
        try:
            await client.forward_messages(target, msgs)
            logger.info(f"Переслано {len(msgs)} сообщений пользователю/группе {getattr(target, 'id', target)}")
            await asyncio.sleep(random.uniform(2, 5))  # задержка между пользователями
        except FloodWaitError as e:
            logger.warning(f"Flood wait {e.seconds}s при пересылке в {getattr(target, 'id', target)}")
            await asyncio.sleep(e.seconds + random.uniform(5, 10))
        except Exception as e:
            logger.exception(f"Ошибка при пересылке в {getattr(target, 'id', target)}. Ошибка: {e}")


async def process_task(task: Task):
    logger.info(f"Проверяем канал: {task.channel_name}")
    min_id = max(1, task.last_msg_id - task.overlap + 1)
    new_messages = []
    try:
        async for msg in client.iter_messages(task.channel_entity, min_id=min_id, reverse=True):
            if msg.id <= task.last_msg_id:
                continue  # пропускаем overlap, если уже обработаны
            new_messages.append(msg)

    except FloodWaitError as e:
        logger.warning(f"Flood wait {e.seconds}s при получении истории {task.channel_name}")
        await asyncio.sleep(e.seconds + random.uniform(5, 15))
        return
    except Exception as e:
        logger.error(f"Ошибка при итерации сообщений в {task.channel_name}: {e}")
        return

    if new_messages:
        await process_messages(new_messages, task)
        task.last_msg_id = max(msg.id for msg in new_messages)
        logger.info(f"Обработано {len(new_messages)} новых сообщений, last_msg_id = {task.last_msg_id}")
    else:
        logger.info(f"Нет новых сообщений в {task.channel_name}")


async def process_and_reschedule(task: Task):
    try:
        await process_task(task)
    except Exception as e:
        logger.error(f"Ошибка в канале {task.channel_name}: {e}")
    finally:
        await task.save_state()
        logger.info(f"Состояние для {task.channel_name} сохранено")
        # Переотправляем задачу в очередь после задержки (асинхронно)
        await asyncio.sleep(task.scan_delay + random.uniform(10, 30))
        await task_queue.put(task)


async def main_loop():
    # Загрузка конфига каналов
    channels_config = CONFIG.MONITORING.channels
    defaults = channels_config.get('DEFAULTS', {})
    channels = [ch for ch in channels_config if ch != 'DEFAULTS']

    # Инициализация задач
    for channel in channels:
        channel_settings = {**defaults, **channels_config[channel]}
        task = Task(
            channel=channel,
            forward_to=channel_settings.get('forward_to', []),
            keywords=channel_settings.get('keywords', []),
            scan_delay=channel_settings.get('scan_delay', 420),
            history_limit=channel_settings.get('history_limit', 50),
            overlap=channel_settings.get('overlap', 5),  # новый param для extensible
        )
        await task.resolve_channel_entity(client)
        task.resolve_state_file()
        await task.load_state()
        await task.resolve_targets_entities(client)
        await task_queue.put(task)

    logger.info("Запуск основного consumer loop для task_queue")
    while True:
        task = await task_queue.get()
        asyncio.create_task(process_and_reschedule(task))
        await asyncio.sleep(0.01)


async def run_monitor():
    await start_client()
    await main_loop()