# task.py
import logging.config
from pathlib import Path
import json
from mko_telebot.core import CONFIG, PATHS, utils
import aiofiles  # async I/O

logging.config.dictConfig(CONFIG.LOGGING)
logger = logging.getLogger('Task')

# Файлы для сохранения состояния
state_dir = Path(PATHS.state_dir)


class Task:
    def __init__(self, channel, forward_to, keywords,
                 scan_delay, history_limit, last_msg_id=0, overlap=5):
        self.channel_name = channel
        self.channel_entity = None
        self.forward_to = forward_to or []
        self.forward_to_entities = []
        self.keywords = keywords or []
        self.scan_delay = scan_delay
        self.history_limit = history_limit
        self.last_msg_id = last_msg_id or 0
        self.overlap = overlap
        self.state_file = None

    async def resolve_targets_entities(self, client):
        # Попробуем получить каждую цель по отдельности
        self.forward_to_entities = []
        for ent in self.forward_to:
            try:
                entity = await client.get_entity(ent)
                self.forward_to_entities.append(entity)
            except Exception as e:
                logger.error(f"Не удалось получить entity для {ent} в канале {self.channel_name}. Ошибка {e}")

    async def resolve_channel_entity(self, client):
        try:
            self.channel_entity = await client.get_entity(self.channel_name)
        except Exception as e:
            logger.error(f"Не удалось получить entity для канала {self.channel_name}. Ошибка {e}")

    def resolve_state_file(self):
        self.state_file = state_dir / f"{self.channel_name}.json"
        try:
            utils.ensure_path_exists(self.state_file)
            logger.info(f"Создан/проверен файл состояния для канала {self.channel_name}: {self.state_file}")
        except Exception as e:
            logger.error(f"Ошибка при создании пути для state file {self.state_file}. Ошибка {e}")

    # ===== Функции состояния =====
    async def load_state(self):
        if self.state_file and self.state_file.exists():
            try:
                async with aiofiles.open(self.state_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                state = json.loads(content) if content else {}
                self.last_msg_id = max(self.last_msg_id, state.get("last_id", 0))
                logger.info(f"Состояние канала {self.channel_name} восстановлено, last_id={self.last_msg_id}")
            except Exception as e:
                logger.error(f"Ошибка загрузки состояния для {self.channel_name}: {e}")
        else:
            logger.info(f"Нет состояния для {self.channel_name}, starting fresh")

    async def save_state(self):
        try:
            async with aiofiles.open(self.state_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps({"last_id": self.last_msg_id}))
            logger.info(f"Состояние канала {self.channel_name} сохранено (last_id={self.last_msg_id})")
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния для {self.channel_name}: {e}")