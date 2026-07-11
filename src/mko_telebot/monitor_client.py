"""Telegram client creation and authentication module.

Provides functions to create and start a Telethon client for monitoring.
"""

import logging
from pathlib import Path

from telethon import TelegramClient

from mko_telebot.core import APP_PATHS
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

    client_config = settings.telethon.client.model_dump(mode='json')

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
    chat = getattr(msg, "chat", None)

    if chat and getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{msg.id}"

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