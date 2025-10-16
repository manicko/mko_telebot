import asyncio
import logging
from mko_telebot.monitor import run_monitor

logger = logging.getLogger('monitor')

if __name__ == '__main__':
    try:
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        logger.info("Мониторинг остановлен пользователем.")
