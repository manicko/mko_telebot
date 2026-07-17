from __future__ import annotations

import logging
from pathlib import Path

from telethon import TelegramClient

from mko_telebot.core import APP_PATHS
from mko_telebot.core.models import TelepostSettings
from mko_telebot.core.utils import _secure_directory_permissions, _secure_file_permissions
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

    client = settings.telethon.client

    # Build proxy dict for Telethon compatibility
    proxy_dict: dict[str, str | int | bool] | None = None
    if client.proxy is not None:
        proxy_dict = client.proxy.to_dict()

    # Build api_hash string (SecretStr must be converted)
    api_hash = client.api_hash.get_secret_value()

    # Get session path
    session = client.session
    session_path = Path(session)

    if not session_path.suffix:
        session_path = session_path.with_suffix(".session")

    session_path = APP_PATHS.session_dir / session_path.name

    # Ensure session directory exists with secure permissions (0700)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    _secure_directory_permissions(session_path.parent)

    # Disable Telethon's auto-sleep on FloodWaitError (default 60s) to use manual handlers only
    return TelegramClient(
        session=str(session_path),
        api_id=client.api_id,
        api_hash=api_hash,
        proxy=proxy_dict,  # pyright: ignore[reportArgumentType]
        app_version=client.app_version or "",
        device_model=client.device_model or "",
        system_version=client.system_version or "",
        lang_code=client.lang_code or "",
        system_lang_code=client.system_lang_code or "",
        flood_sleep_threshold=0,
    )


async def start_client(client: TelegramClient, settings: TelepostSettings) -> bool:
    """Initialize and start the Telethon client.

    Session files are secured after client creation to prevent credential exposure.

    Args:
        client: The Telethon client instance.
        settings: Application settings with auth configuration.

    Returns:
        True if client started successfully, False otherwise.

    """
    from telethon.errors import RPCError, AuthKeyUnregisteredError, SessionPasswordNeededError

    try:
        if settings.telethon.is_user:
            await client.start(  # pyright: ignore[reportGeneralTypeIssues]
                phone=settings.telethon.phone_or_token.get_secret_value()
            )
        else:
            await client.start(  # pyright: ignore[reportGeneralTypeIssues]
                bot_token=settings.telethon.phone_or_token.get_secret_value()
            )

        logger.info("Telethon client started successfully.")

        # Harden session file permissions after successful start
        if client.session and hasattr(client.session, "filename"):
            session_path = Path(client.session.filename)
            if session_path.exists():
                _secure_file_permissions(session_path)

        return True

    except (AuthKeyUnregisteredError, SessionPasswordNeededError, ValueError) as e:
        logger.error(f"Telegram authentication failed: {e}")
        return False

    except (RPCError, OSError, ConnectionError, TimeoutError) as e:
        logger.error(f"Telegram service error: {e}")
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
    from telethon.errors import RPCError

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

    except RPCError as e:
        logger.exception(f"Error while building sender tag: {e}")

        return ""

    except (OSError, ConnectionError, TimeoutError) as e:
        logger.exception(f"Error while building sender tag: {e}")

        return ""
