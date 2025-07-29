import asyncio
import random
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.errors import FloodWaitError
import logging.config
from pathlib import Path
from mko_telebot.core import CONFIG, PATHS
import json

# Файлы для сохранения состояния
state_file = Path(PATHS.state_file)

# Настройка логирования
logging.config.dictConfig(CONFIG.LOGGING)
logger = logging.getLogger('monitor')

# Настройка мониторинга
forward_to = CONFIG.MONITORING.forward_to
history_limit = CONFIG.MONITORING.history_limit
channels = CONFIG.MONITORING.channels
keywords = CONFIG.MONITORING.keywords
default_keywords = keywords.pop('default', None)
scan_delay = CONFIG.MONITORING.scan_delay
is_user = CONFIG.TELETHON_API.is_user
phone_or_token = CONFIG.TELETHON_API.phone_or_token
# Хранилище обработанных ID и смещений для каждого канала
processed_msg_ids = set()
last_ids = {channel: 0 for channel in channels}

# Инициализация клиента
client = TelegramClient(**CONFIG.TELETHON_API.client)
target_entities = []


# ===== Функции состояния =====
def load_state():
    if state_file.exists():
        data = json.loads(state_file.read_text())
        last_ids.update(data.get("last_ids", {}))
        logger.info("Состояние восстановлено")


def save_state():
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"last_ids": last_ids}))
    logger.info("Состояние сохранено")


async def start_client():
    """Инициализация Telethon клиента с учетом режима user/bot"""
    if is_user:
        await client.start(phone=phone_or_token)
    else:
        await client.start(bot_token=phone_or_token)
    logger.info("Клиент Telethon успешно запущен.")


async def matches(text, search_items: dict):
    """Check if message matches the search criteria"""
    if not search_items:
        return True
    text = text.strip().lower()
    if isinstance(search_items, dict):
        for key, value in search_items.items():
            if key == 'default':
                continue
            if key.lower() in text:
                if value == 'default':
                    value = default_keywords
                # Check if the value is a dictionary (nested keywords)
                if isinstance(value, dict):
                    # Check if any nested keywords match
                    if await matches(text, value):
                        return True
                # For empty dict values (no additional requirements)
                # For list values (exclusion check)
                elif isinstance(value, list):
                    # Check that no exclusion words are present
                    if not any(excl.lower() in text for excl in value):
                        return True
                elif isinstance(value, bool) and value:
                    return True
                elif not value:
                    return True
        return False


async def process_messages(messages, channel):
    albums_msgs = {}
    albums_txt = {}
    # группируем альбомы
    for msg in reversed(messages):
        if msg.id in processed_msg_ids:
            continue
        try:
            group_id = msg.grouped_id if msg.grouped_id else msg.id
            albums_msgs.setdefault(group_id, []).append(msg)
            if msg.message:
                albums_txt.setdefault(group_id, []).append(msg.message)
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения {msg.id} из {channel}: {e}")

    for album_id, album_msgs in albums_msgs.items():
        text = " ".join(albums_txt.get(album_id, []))
        if text and await matches(text, keywords):
            logger.info(f"Найдено совпадение в сообщении {album_id} в канале {channel}")
            await asyncio.sleep(random.uniform(3, 10))
            await forward_to_users(album_msgs)
        processed_msg_ids.update(m.id for m in album_msgs)

async def forward_to_users(msgs):
    for target in target_entities:
        try:
            await client.forward_messages(target, msgs)
            logger.info(f"Переслано {len(msgs)} сообщений пользователю/группе {target.id}")
            await asyncio.sleep(random.uniform(2, 5))  # задержка между пользователями
        except FloodWaitError as e:
            logger.warning(f"Flood wait {e.seconds}s при пересылке")
            await asyncio.sleep(e.seconds + random.uniform(5, 10))
        except Exception as e:
            logger.error(f"Ошибка при пересылке: {e}")


async def monitor_channel(channel):
    logger.info(f"Проверяем канал: {channel}")
    limit = history_limit
    min_id = max(1, last_ids[channel] - 5)
    while True:
        try:
            history = await client(GetHistoryRequest(
                peer=channel,
                offset_id=0,
                limit=limit,
                add_offset=0,
                max_id=0,
                min_id=min_id,
                offset_date=None,
                hash=0
            ))
        except FloodWaitError as e:
            logger.warning(f"Flood wait {e.seconds}s при получении истории {channel}")
            await asyncio.sleep(e.seconds + random.uniform(5, 15))
        else:
            messages = history.messages
            if not messages:
                break

            await process_messages(messages, channel)
            last_ids[channel] = max(msg.id for msg in messages)

            save_state()
            if len(messages) < limit:
                break


async def main_loop():
    load_state()
    for e in forward_to:
        target_entities.append(await client.get_entity(e))

    while True:
        for channel in channels:
            try:
                await monitor_channel(channel)
            except Exception as e:
                logger.error(f"Ошибка в канале {channel}: {e}")
            await asyncio.sleep(random.uniform(10, 30))  # интервал между каналами
        await asyncio.sleep(scan_delay + random.uniform(10, 30))  # основной интервал


async def main():
    await start_client()
    await main_loop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Мониторинг остановлен пользователем.")
