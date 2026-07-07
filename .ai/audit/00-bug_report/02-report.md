# Bug Report 02: Broken import in core/task.py

## Discovered During
TASK_009_update_test_imports — updating tests/test_config_reader.py references after module rename.

## Description
`core/task.py` line 14 imports `ChannelConfig` from `.chats_config`:

```python
from mko_telebot.core.chats_config import ChannelConfig
```

However, the module `chats_config.py` does not exist in the project. `ChannelConfig` is defined in `core/channels.py` and exported via `core/__init__.py`.

## Impact
- **Blocked imports**: Loading `conftest.py` (and therefore running any test) raises `ModuleNotFoundError: No module named 'mko_telebot.core.chats_config'`.
- **Runtime failure**: The `task.py` module cannot be imported at all, cascading to all modules importing from `core`.

## Root Cause
The module was presumably renamed from `chats_config.py` to `channels.py` but the import in `task.py` was not updated.

## Affected File
`src/mko_telebot/core/task.py` — line 14

## Suggested Fix
Change line 14 from:
```python
from mko_telebot.core.chats_config import ChannelConfig
```
to:
```python
from mko_telebot.core.channels import ChannelConfig
```

## Priority
High — blocks all tests from running.

## Status
Open
