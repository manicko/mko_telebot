---
name: 06-data-flow-validated
description: Validated audit findings for End-to-End Data Flow
agent: validator
status: validated
validated: yes
---

# Phase 06 Audit Findings — End-to-End Data Flow (Validated)

**Executor:** auditor  
**Validator:** validator  
**Status:** validated  
**Validated:** yes

---

## Findings

### DF-001: ~~ChannelDefaults configuration never applied to individual channels~~ [MERGED]

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/channels.py, src/mko_telebot/core/task.py |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** merged
> - **Detail:** This finding describes the same root cause as CFG-002 (Phase 02). The `defaults` field in `ChannelsConfig` is documented to provide "fallback values for all channels" (configuration.md line 122) but is never merged into individual `ChannelConfig` instances. Both findings share the same architectural issue: `Task.__init__` and `main_loop` use `ChannelConfig` values directly without referencing `ChannelsConfig.defaults`.
> - **See also:** CFG-002 (Phase 02)

---

### DF-002: SecretStr api_hash passed directly to TelegramClient without proper serialization

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py:35-46 |
| **Classification** | mandatory |

**Description:** The `create_client()` function calls `settings.telethon.client.model_dump()` to extract configuration for the Telethon client, but `model_dump()` returns `SecretStr` objects as-is (masked) instead of their string values. The Telethon `TelegramClient` constructor expects `api_hash` as a plain `str`. This causes a type mismatch that would fail at Telethon API initialization time. While the test suite mocks this correctly (using plain string values), the actual runtime code would pass a `SecretStr` object to the Telegram API.

**Evidence:**
- `core/telethon.py:25` - `api_hash` defined as `SecretStr` type
- `monitor.py:35` - `client_config = settings.telethon.client.model_dump()` returns `{'api_hash': SecretStr('**********')}`
- `monitor.py:46` - `return TelegramClient(**client_config)` passes the SecretStr object directly
- `monitor.py:37-44` - Session string is manually extracted and converted, but `api_hash` is not
- `test_monitor.py:76-80` - mock `model_dump.return_value` uses plain string `"test_hash_abcdef123456"` instead of SecretStr

**Recommendation:** In `monitor.py` lines 35-46, convert SecretStr api_hash to its string value:

```python
def create_client(settings: TelepostSettings) -> TelegramClient:
    client_config = settings.telethon.client.model_dump()
    # Add this line after model_dump to unwrap SecretStr:
    if "api_hash" in client_config:
        client_config["api_hash"] = client_config["api_hash"].get_secret_value()
    # ... rest of function unchanged
```

This is the same fix as INT-002 (use `model_dump(mode='json')` or explicit `.get_secret_value()` call).

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed via runtime check: Pydantic's `model_dump()` returns `SecretStr('**********')` not the string value. Telethon's `TelegramClient` expects `api_hash: str` and would fail with `SecretStr`. The test suite uses mocks that return plain strings, masking this bug. This is a genuine SPEC-DEVIATION that would cause runtime failure.
> - **See also:** —

---

### DF-003: No cleanup of Telegram client connection on exit paths

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/cli.py:96-101, src/mko_telebot/monitor.py:346-356 |
| **Classification** | advisory |

**Description:** The `run()` CLI command and `run_monitor()` function lack proper cleanup on exit. When `run_monitor()` exits due to `KeyboardInterrupt` or error, the Telethon client connection is never explicitly disconnected. The audit checklist requires try/finally or context manager cleanup for all exit paths.

**Evidence:**
- `monitor.py:353-356` - `run_monitor()` calls `start_client()` but never calls `await client.disconnect()`
- `cli.py:96-101` - The outer try/except catches `KeyboardInterrupt` but has no cleanup hook for client disconnection
- The Telethon client remains connected after `main_loop()` exits, leaving orphaned sessions

**Recommendation:** In `monitor.py` lines 346-356, add try/finally for client cleanup:

```python
async def run_monitor(settings: TelepostSettings, client: TelegramClient):
    """Run the monitoring system."""
    try:
        if await start_client(client, settings):
            queue: asyncio.Queue[Task] = asyncio.Queue()
            lock: asyncio.Lock = asyncio.Lock()
            await main_loop(settings, client, queue, lock)
    finally:
        await client.disconnect()
        logger.info("Telethon client disconnected.")
```

This ensures `client.disconnect()` is called even on KeyboardInterrupt, preventing orphaned sessions.

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed: `run_monitor()` at lines 346-356 creates a client via `start_client()` but lacks cleanup. The `main_loop()` at lines 308-343 runs an infinite loop with no exit handling for cleanup. The `cli.py:run()` command at lines 85-101 catches exceptions but never calls `client.disconnect()`. Per project rules (clean up temp files with try/finally), this represents a resource leak risk for session files and lingering connections.
> - **See also:** —

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- DF-002: SecretStr api_hash passed directly to TelegramClient without proper serialization
- DF-001 (merged to CFG-002): ChannelDefaults configuration never applied to individual channels

## Advisory Recommendations

- DF-003: No cleanup of Telegram client connection on exit paths

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | DF-002, DF-003 |
| Reclassified | 0 | — |
| Merged | 1 | DF-001 → CFG-002 |
| Rejected | 0 | — |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| DF-001 | CFG-002 (Phase 02) | Both findings describe the same root cause: `defaults` in `ChannelsConfig` is documented but never applied to individual channels. CFG-002 was validated first and has complete analysis. |

### Architectural Observations

1. **Cross-phase finding consolidation:** DF-001 is identical to CFG-002. The `defaults` feature is documented in `configuration.md` (line 122) but the data flow from `ChannelsConfig.defaults` through `Task.__init__` to actual message filtering/forwarding is broken. The `strip_defaults_from_channels` validator only removes a 'DEFAULTS' key but does not merge defaults into channels.

2. **SecretStr serialization gap:** The `create_client()` function correctly handles `SecretStr` for `phone_or_token` (via `.get_secret_value()` at line 61-63), but the bug at line 35 for `api_hash` was missed. This inconsistency suggests a systematic review of all `SecretStr` usages is warranted.

3. **Resource cleanup pattern:** The project lacks a consistent pattern for client lifecycle management. Adding cleanup would align with the established rule for try/finally cleanup of resources.