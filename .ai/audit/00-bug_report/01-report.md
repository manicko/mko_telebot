# Bug Report 01: Broken import in core/models.py

## Discovered During
TASK_008_update_core_models — updating imports and field names in `core/models.py`.

## Description
`core/models.py` line 7 still imports `TelethonConfig` from `.telethon_models`:

```python
from .telethon_models import TelethonConfig
```

However, the file `telethon_models.py` was renamed to `telethon.py` (by TASK_002). The import statements in `models.py` were not updated to reflect this rename, leaving a dangling import.

## Impact
- **Blocked imports**: Any code importing `TelepostSettings` from `models.py` will raise `ModuleNotFoundError`.
- **Runtime failure**: The config loader will crash when trying to parse the configuration.

## Root Cause
TASK_002 (`rename_telethon_models`) renamed the file and/or class but did not update the import in `core/models.py`.

## Affected File
`src/mko_telebot/core/models.py` — line 7

## Suggested Fix
Change line 7 from:
```python
from .telethon_models import TelethonConfig
```
to:
```python
from .telethon import TelethonConfig
```

## Priority
High — blocks config loading at runtime.

## Status
Open