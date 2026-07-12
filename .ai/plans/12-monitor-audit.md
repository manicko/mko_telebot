# basedpyright Audit Report: monitor.py

## Summary
- **File**: `src/mko_telebot/monitor.py`
- **Total Issues**: 4 (1 error, 3 warnings)

---

## Errors

### 1. CRITICAL - Unused Call Result (reportUnusedCallResult)
**Line 137:19** - `"None" is not awaitable`

**Issue**:
```python
await client.disconnect()
```

**Description**: The `TelegramClient.disconnect()` method returns `None | None` (the type checker infers this). Awaiting `None` is invalid. The `disconnect()` method is synchronous and does not return a coroutine.

**Severity**: CRITICAL
**Category**: Type Safety

---

## Warnings

### 2. MEDIUM - Unused Call Result (reportUnusedCallResult)
**Line 68:5** - `asyncio.create_task(reschedule_task(...))`

**Description**: The result of `asyncio.create_task()` is not captured. While this is intentional fire-and-forget behavior, the type checker flags this as a potential issue. The task is deliberately backgrounded for the rescheduling logic.

**Severity**: MEDIUM
**Category**: Best Practice

### 3. MEDIUM - Unused Call Result (reportUnusedCallResult)
**Line 117:9** - `asyncio.create_task(process_and_reschedule(...))`

**Description**: Same as above - intentional fire-and-forget pattern for concurrent task processing.

**Severity**: MEDIUM
**Category**: Best Practice

### 4. LOW - Missing Type Stubs (reportMissingTypeStubs)
**Line 10:6** - `from telethon import TelegramClient`

**Description**: The `telethon` package does not include type stubs (`.pyi` files). This causes reduced type checking accuracy for Telethon API usage throughout the codebase.

**Severity**: LOW
**Category**: Type Safety

---

## Recommendations

1. **CRITICAL**: Replace `await client.disconnect()` with `client.disconnect()` (remove `await`) at line 137. The `disconnect()` method is synchronous.

2. **MEDIUM**: Consider capturing task references in a list for cleanup on exit:
   ```python
   task_group = asyncio.TaskGroup()
   # or use a set() to track tasks for graceful shutdown
   ```

3. **LOW**: Install `telethon-stubs` package if available, or add type stubs to improve type checking precision.