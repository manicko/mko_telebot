# Phase 06 Audit Findings — End-to-End Data Flow

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### DF-001: Empty channels configuration causes infinite hang in main_loop

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | HIGH |
| **Type** | [BEST-PRACTICE] |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** When `channels.channels` is an empty dictionary (the template default in config.yaml), `main_loop()` adds zero tasks to the queue, then enters `while True: queue.get()` which blocks indefinitely. The application will hang forever waiting for tasks that will never arrive, with no warning or error message.

**Evidence:**
- `monitor.py` line 95-110: The for-loop iterates over `channels.keys()`. If empty, no tasks are added to the queue.
- `monitor.py` line 114-117: The while loop calls `queue.get()` with no timeout and no check for empty channels.
- `settings/config.yaml` line 11: Template has `channels: {}` as the default.

```python
# Line 95-110 in monitor.py
for channel_name in channels_list:
    channel_settings = channels[channel_name]
    task = Task(config=channel_settings)
    await task.resolve_channel_entity(client)
    # ... populate queue ...
    await queue.put(task)

# Line 114-117 - hangs forever if queue is empty
while True:
    task = await queue.get()
```

**Recommendation:** Add validation in `main_loop()` or during config loading to ensure at least one channel is configured. If `channels` is empty, log an error and exit gracefully rather than hanging indefinitely.

**effort:** trivial

---

### DF-002: Single channel resolution failure aborts all channel monitoring at startup

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | HIGH |
| **Type** | [BEST-PRACTICE] |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** If `resolve_channel_entity()` or `resolve_targets_entities()` fails for any channel during the initial setup loop in `main_loop()`, the exception propagates up and crashes the entire application. Other valid channels are never monitored because they are processed sequentially without try/except protection.

**Evidence:**
- `monitor.py` line 100-106: No exception handling around entity resolution calls.
- If one channel name is invalid or target is unreachable, the exception propagates.
- Tests only cover single-channel scenarios; no test verifies "other channels continue on one failure."

```python
# monitor.py lines 95-110 - no error handling
for channel_name in channels_list:
    channel_settings = channels[channel_name]
    task = Task(config=channel_settings)
    await task.resolve_channel_entity(client)  # Can raise TelegramServiceError
    task.resolve_state_file()
    await task.load_state()
    await task.resolve_targets_entities(client)  # Can raise TelegramServiceError
    await queue.put(task)
```

**Recommendation:** Wrap the channel initialization in a try/except block. Log errors for failed channels but continue to initialize remaining channels. Optionally skip monitoring the failed channel rather than aborting entirely.

**effort:** small

---

### DF-003: history_days=0 accepted but treated as "no limit"

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | LOW |
| **Type** | [BEST-PRACTICE] |
| **Affected Modules** | src/mko_telebot/core/channels.py, src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** The `history_days` field in `ChannelConfig` lacks a `ge=1` constraint, allowing `history_days=0`. However, `set_offset_date()` treats `history_days=0` as falsy (line 127: `if not self.history_days`), resulting in `offset_date=None`. This silently converts the user's "fetch 0 days of history" into "fetch all history, no date limit."

**Evidence:**
- `channels.py` line 48-50: No validation constraint on `history_days`.
- `task.py` line 127: `if not self.history_days: return` treats 0 the same as None.

**Recommendation:** Add `ge=1` constraint to `history_days` field in `ChannelConfig` to ensure semantic correctness, or update the logic to explicitly handle 0 as an invalid value.

**effort:** trivial

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 0 |
| LOW | 1 |

## Advisory Recommendations

1. **DF-001**: Empty channels configuration causes infinite hang in main_loop
2. **DF-002**: Single channel resolution failure aborts all channel monitoring at startup
3. **DF-003**: history_days=0 accepted but treated as "no limit"

---