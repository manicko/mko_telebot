---
name: 06-data-flow-audit-findings
description: Audit findings for end-to-end data flow phase
agent: auditor
status: complete
validated: no
---

# Phase 06 Audit Findings — End-to-End Data Flow

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### DF-001: Audit spec references non-existent Google Sheets integration in data flow

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | .kilo/commands/audit/phases/06-audit-data-flow.md |
| **Classification** | mandatory |

**Description:** The audit phase spec (line 26) explicitly requires tracing data flow through "Google Sheets API call → raw data → post extraction → image processing". However, the codebase has no Google Sheets integration whatsoever — no GSheetsReader, no GoogleSheetsConfig, no spreadsheet_id fields. The actual architecture is purely Telegram-based: CLI → config.yaml → monitor → Task → Telethon messages → forwarding. This creates a fundamental mismatch where the audit spec describes a data flow that doesn't exist in the codebase.

**Evidence:**
- Audit spec line 26: "Trace the entire path: `CLI command` → `config loading` → `Google Sheets API call` → `raw data` → `post extraction` → `image processing` → `queue` → `Telegram API call` → `cleanup`."
- Codebase grep returns no matches for `GSheetsReader`, `GoogleSheetsConfig`, `google_sheets`, or `spreadsheet_id`
- `pyproject.toml` has no google-api-python-client or google-auth dependencies
- Actual flow is: `cli.py:run()` → `TelepostConfigReader.load()` → `TelegramClient` → `Task` → `iter_messages()` → `process_messages()` → `forward_to_users()`

**Recommendation:** Update the audit spec to reflect the actual architecture. The data flow consists of: CLI → config loading → Telegram client auth → per-channel message fetching → keyword matching → message forwarding. Remove references to Google Sheets, PostProcessor, and ImageCache which are not part of this codebase.

**Effort:** small
**Priority:** mandatory

---

### DF-002: Missing forum topic support breaks data flow for Telegram forums

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor_forward.py, src/mko_telebot/core/channels.py |
| **Classification** | advisory |

**Description:** The audit spec requires "Topic/forum support — topic_id is passed correctly to send_message and send_file for forum topics" (line 97). The `forward_to_users()` function in `monitor_forward.py` (lines 71-76) calls `send_message` and `send_file` without passing `topic_id`, preventing forwarding to specific forum topics within a chat. The `ChannelConfig` model lacks a `topic_id` field to configure this. While Telethon supports the `topic_id` parameter for forum threads, it is never extracted from config or passed to the API calls.

**Evidence:**
- `monitor_forward.py` lines 71-76: `send_file(target, msg_media, caption=caption)` and `send_message(target, caption)` have no topic_id parameter
- `channels.py` ChannelConfig: No topic_id field defined among its 8 fields
- Telethon documentation: `send_message()` accepts `topic_id` parameter for forum topics
- Audit spec line 97: "Chat-specific topics — topic_id is correctly scoped to its chat"

**Recommendation:** Add `topic_id: int | None = None` field to `ChannelConfig`, propagate it through `Task.__init__()`, and pass it to `send_message()` and `send_file()` calls in `forward_to_users()` when set.

**Effort:** small
**Priority:** recommended

---

### DF-003: OSError not handled in Telegram message sending/receiving

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | advisory |

**Description:** The audit spec requires "OSError triggers retries with exponential backoff" (line 84) for Telegram integration. However, `forward_to_users()` only handles `FloodWaitError` and `RPCError`, not `OSError`. Network-level failures (connection drops, DNS issues, timeouts) would raise `OSError` and cause message loss without retry. Similarly, `process_task()` doesn't wrap the `iter_messages` loop in a generic exception handler for OSError.

**Evidence:**
- `monitor_forward.py` lines 84-102: Only `FloodWaitError` and `RPCError` are caught with retry logic
- `monitor_forward.py` lines 195-203: Only `FloodWaitError` and `TelegramServiceError` in `process_task()`
- No `except OSError:` clause in either function
- Audit spec line 84: "OSError triggers retries with exponential backoff"

**Recommendation:** Add `except OSError as e:` handler in both `forward_to_users()` and `process_task()` with exponential backoff retry logic following the existing pattern.

**Effort:** small
**Priority:** recommended

---

### DF-004: Task entity resolution errors can leave partial state

| Field | Value |
|-------|-------|
| **ID** | DF-004 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | src/mko_telebot/core/task.py, src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** In `resolve_targets_entities()` (task.py lines 63-78), when resolving multiple targets, the code appends each entity to `forward_to_entities` as it succeeds. If an error occurs on the second or later target, the first entity remains in the list while the exception is raised. This partial state could cause messages to be forwarded to resolved targets even when some targets failed to resolve. The error happens in `main_loop()` (monitor.py lines 90-106) before any messages are processed, but the partial state remains in the Task object. The test at `test_task.py` lines 327-330 explicitly validates this behavior (partial state is left after error).

**Evidence:**
- `task.py` lines 63-78: `self.forward_to_entities.append(entity)` happens inside the try block before the potential exception
- `task.py` line 76: `raise TelegramServiceError` only after the exception, but entity is already appended
- `test_task.py` lines 327-330: Test confirms partial state is left (asserts `len(task.forward_to_entities) == 1` after error on second target)
- `monitor.py` line 101: After entity resolution, task is immediately queued without validation that all targets resolved

**Recommendation:** Refactor `resolve_targets_entities()` to resolve all entities into a temporary list first, then assign to `forward_to_entities` only if all succeed. This ensures atomic state updates.

**Effort:** small
**Priority:** recommended

---

### DF-005: Task state save failures during normal operation leave state inconsistent

| Field | Value |
|-------|-------|
| **ID** | DF-005 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | src/mko_telebot/monitor.py, src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** In `process_and_reschedule()` (monitor.py lines 40-63), `task.save_state()` is called after `process_task()` completes. If `save_state()` fails (disk full, permission denied), a `StateError` is raised and propagates up, but the in-memory `task.last_msg_id` was already updated during message processing. On restart, the state file would be stale (old last_msg_id), potentially causing re-processing of already-forwarded messages. The finally block in `run_monitor()` only disconnects the client, it doesn't attempt state recovery.

**Evidence:**
- `monitor.py` line 59: `await process_task(task, client, settings)` updates `task.last_msg_id` (monitor_forward.py line 208)
- `monitor.py` line 61: `await task.save_state()` called after - if this fails, in-memory state is newer
- `task.py` line 157: `raise StateError` on save failure
- `monitor.py` lines 126-132: The finally block disconnects client but doesn't handle state save failures
- `monitor_forward.py` line 208: `task.last_msg_id = max(msg.id for msg in new_messages)` updates in-memory state

**Recommendation:** Wrap `save_state()` in a try/except in `process_and_reschedule()` to log errors without crashing. Consider implementing a transactional approach: write to temp file, then rename on success.

**Effort:** small
**Priority:** recommended

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 4 |
| LOW | 0 |

## Mandatory Fixes

- DF-001: Update audit spec to reflect actual architecture (Telegram-only, no Google Sheets)

## Advisory Recommendations

- DF-002: Missing forum topic support (topic_id) in message forwarding
- DF-003: Missing OSError handling in Telegram message sending/receiving
- DF-004: Task entity resolution leaves partial state on error
- DF-005: Task state save failures cause state inconsistency

## Doc Updates Needed

- DF-001: Update audit spec to reflect actual service architecture (monitor_forward.py, monitor_client.py, Task)