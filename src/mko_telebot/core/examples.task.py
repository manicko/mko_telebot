from pathlib import Path
from dataclasses import dataclass

@dataclass
class Post:
    """Represents a processed post ready for Telegram dispatch.

    Attributes:
        txt: Text content of the post.
        photos: List of resolved photo file paths.
    """

    txt: str
    photos: list[Path]


@dataclass
class Task:
    """Represents a task for posting to a Telegram chat.

    Attributes:
        chat_id: Telegram chat ID
        topic_id: Forum topic ID (optional)
        chat_name: Name of the chat
        txt: Text content of the post
        photos: Photo paths or list of photo paths
        count: Current post count
        max_count: Maximum post count
        min_delay_minutes: Configured base delay (minutes) for this chat
        delay_jitter_percent: Configured jitter % for this chat
    """

    chat_id: int | str
    txt: str
    photos: list[Path]
    chat_name: str
    topic_id: int = 0
    count: int = 0
    max_count: int = 0
    min_delay_minutes: float = 0.0
    delay_jitter_percent: int = 0
