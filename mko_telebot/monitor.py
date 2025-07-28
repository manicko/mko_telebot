import asyncio
import random
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.errors import FloodWaitError
import logging.config
from mko_telebot.core import CONFIG
import json
from pathlib import Path

# Файлы для сохранения состояния
STATE_FILE = Path("state.json")


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

# Хранилище обработанных ID и смещений для каждого канала
processed_msg_ids = set()
last_ids = {channel: 0 for channel in channels}

# Инициализация клиента
client = TelegramClient(**CONFIG.TELETHON_API.client)
target_entities = []


# ===== Функции состояния =====
def load_state():
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        last_ids.update(data.get("last_ids", {}))
        logger.info("Состояние восстановлено")


def save_state():
    STATE_FILE.write_text(json.dumps({"last_ids": last_ids}))
    logger.info("Состояние сохранено")

async def start_client():
    """Инициализация Telethon клиента с учетом режима user/bot"""
    if CONFIG.TELETHON_API.is_user:
        await client.start(phone=CONFIG.TELETHON_API.phone_or_token)
    else:
        await client.start(bot_token=CONFIG.TELETHON_API.phone_or_token)
    logger.info("Клиент Telethon успешно запущен.")


async def matches(message, search_items: dict):
    """Check if message matches the search criteria"""
    if not search_items:
        return True

    if isinstance(search_items, dict):
        for key, value in search_items.items():
            if key == 'default':
                continue
            if key in message:
                if value == 'default':
                    value = default_keywords
                # Check if the value is a dictionary (nested keywords)
                if isinstance(value, dict):
                    # Check if any nested keywords match
                    if await matches(message, value):
                        return True
                # For empty dict values (no additional requirements)
                # For list values (exclusion check)
                elif isinstance(value, list):
                    # Check that no exclusion words are present
                    if not any(excl in message for excl in value):
                        return True
                elif isinstance(value, bool) and value:
                    return True
        return False


async def process_messages(messages, channel):
    # Обрабатываем в хронологическом порядке
    for msg in reversed(messages):
        if msg.id in processed_msg_ids:
            continue
        if not msg.message:
            continue
        try:
            if await matches(msg.message, keywords):
                logger.info(f"Найдено совпадение в сообщении {msg.id} канала {channel}")
                await asyncio.sleep(random.uniform(3, 10))  # задержка перед пересылкой
                await forward_to_users(msg)  # пересылаем сообщение
                processed_msg_ids.add(msg.id)  # помечаем как обработанное
        except FloodWaitError as e:
            logger.warning(f"Flood wait {e.seconds}s при обработке {msg.id} из {channel}")
            await asyncio.sleep(e.seconds + random.uniform(5, 10))
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения {msg.id} из {channel}: {e}")


async def forward_to_users(msg):
    for target in target_entities:
        try:
            await client.forward_messages(target, msg)
            logger.info(f"Переслано сообщение {msg.id} пользователю или группе {target}")
            await asyncio.sleep(random.uniform(2, 5))  # задержка между пользователями
        except FloodWaitError as e:
            logger.warning(f"Flood wait {e.seconds}s при отправке {msg.id}")
            await asyncio.sleep(e.seconds + random.uniform(5, 10))
        except Exception as e:
            logger.error(f"Ошибка при отправке {msg.id}: {e}")


async def monitor_channel(channel):
    logger.info(f"Проверяем канал: {channel}")
    offset_id = last_ids[channel]
    limit = history_limit

    try:
        history = await client(GetHistoryRequest(
            peer=channel,
            offset_id=offset_id,
            limit=limit,
            add_offset=0,
            max_id=0,
            min_id=0,
            offset_date=None,
            hash=0
        ))
    except FloodWaitError as e:
        logger.warning(f"Flood wait {e.seconds}s при получении истории {channel}")
        await asyncio.sleep(e.seconds + random.uniform(5, 15))
        return

    messages = history.messages
    if not messages:
        return

    await process_messages(messages, channel)
    last_ids[channel] = max(msg.id for msg in messages)
    save_state()

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
            await asyncio.sleep(random.uniform(10, 30)) # интервал между каналами
        await asyncio.sleep(scan_delay + random.uniform(10, 30))  # основной интервал


async def main():
    await start_client()
    await main_loop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Мониторинг остановлен пользователем.")