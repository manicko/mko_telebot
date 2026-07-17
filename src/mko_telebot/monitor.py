"""Telegram channel monitoring orchestration module.

Provides the main monitoring loop and entry point for the monitor system.
"""

import asyncio
import logging
import random

from telethon import TelegramClient

from mko_telebot.core import Task
from mko_telebot.core.models import TelepostSettings
from mko_telebot.core.errors import StateError, ConfigError, TelegramServiceError, TelegramAuthError
from .monitor_client import start_client
from .monitor_forward import process_task

logger = logging.getLogger(__name__)


def _handle_task_exception(task: asyncio.Task[None]) -> None:
    """Log any unhandled exceptions from background task.

    Args:
        task: The completed asyncio Task to check for exceptions.

    """
    try:
        task.result()
    except Exception as e:
        logger.error("Unhandled exception in background task: %s", e)


async def reschedule_task(task: Task, queue: asyncio.Queue[Task]) -> None:
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
) -> None:
    """Process a single task, save its state, and reschedule it asynchronously.

    Args:
        task (Task): Task object to process.
        client (TelegramClient): The Telethon client instance.
        queue (asyncio.Queue): Queue used for scheduling tasks.
        lock (asyncio.Lock): Lock to serialize task processing.
        settings (TelepostSettings): Application settings.

    """
    try:
        async with lock:
            await process_task(task, client, settings)

            try:
                await task.save_state()
            except StateError as e:
                logger.error(
                    "Failed to save task state for %s: %s", task.channel_name, e
                )
                # Continue with in-memory state for next iteration
    except TelegramServiceError as e:
        logger.error(
            "Error processing channel %s: %s", task.channel_name, e
        )
    finally:
        asyncio.create_task(reschedule_task(task, queue))


async def main_loop(
        settings: TelepostSettings,
        client: TelegramClient,
        queue: asyncio.Queue[Task],
        lock: asyncio.Lock,
    ) -> None:
        """Main monitoring loop that sequentially processes channels.

        Args:
            settings (TelepostSettings): Application settings.
            client (TelegramClient): The Telethon client instance.
            queue (asyncio.Queue): Queue for scheduling tasks.
            lock (asyncio.Lock): Lock to serialize task processing.

        """

        max_retries = settings.telethon.max_retries

        channels_delay = settings.channels.channels_delay

        channels = settings.channels.channels

        channels_list = list(channels.keys())

        if not channels:

            logger.error(

                "No channels configured. Please add at least one channel to your configuration."

            )

            raise ConfigError("No channels configured in configuration file")

        stagger_start_seconds = settings.channels.stagger_start_seconds

        for channel_name in channels_list:

            try:

                channel_settings = channels[channel_name]

                task = Task(config=channel_settings)

                await task.resolve_channel_entity(client, max_retries)

                task.resolve_state_file()

                await task.load_state()

                await task.resolve_targets_entities(client, max_retries)

                await asyncio.sleep(random.uniform(0, stagger_start_seconds))

                await queue.put(task)

            except TelegramServiceError as e:

                logger.error(f"Failed to initialize channel {channel_name}: {e}")

                continue

        logger.info("Monitoring loop started.")

        while True:

            task = await queue.get()

            asyncio.create_task(process_and_reschedule(task, client, queue, lock, settings)).add_done_callback(_handle_task_exception)

            await asyncio.sleep(channels_delay)


async def run_monitor(settings: TelepostSettings, client: TelegramClient) -> None:
    """Run the monitoring system.

    Args:
        settings: Application settings.
        client: The Telethon client instance.

    """
    if await start_client(client, settings):
        queue: asyncio.Queue[Task] = asyncio.Queue()
        lock: asyncio.Lock = asyncio.Lock()
        try:
            await main_loop(settings, client, queue, lock)
        finally:
            await client.disconnect()  # pyright: ignore[reportGeneralTypeIssues]
            logger.info("Telethon client disconnected.")
    else:
        raise TelegramAuthError("Telegram authentication failed")
