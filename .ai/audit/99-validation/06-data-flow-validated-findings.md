---
name: 06-data-flow-validated
description: Validated audit findings for End-to-End Data Flow
agent: validator
status: complete
validated: yes
---

# Phase 06 Validated Audit Findings — End-to-End Data Flow

**Executor:** validator  
**Source:** .ai/audit/06-data-flow/findings.md  
**Status:** complete  
**Validated:** yes

---

## Findings

### DF-001: ~~Audit spec references non-existent Google Sheets integration in data flow~~ [MERGED]

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | HIGH |
| **Type** | DOC-UPDATE |
| **Affected Modules** | .kilo/commands/audit/phases/06-audit-data-flow.md, .kilo/commands/audit/phases/05-audit-integrations.md, .kilo/commands/audit/phases/03-audit-services.md |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** merged
> - **Detail:** This finding shares the same root cause as INT-001 and SRV-005 — the audit specification describes a Google Sheets-based architecture that was never implemented. The codebase contains only Telegram integration with no Sheets code, models, or dependencies.
> - **See also:** INT-001 (Phase 05), SRV-005 (Phase 03)

**Description:** The audit phase spec (line 26) explicitly requires tracing data flow through "Google Sheets API call → raw data → post extraction → image processing". However, the codebase has no Google Sheets integration whatsoever — no GSheetsReader, no GoogleSheetsConfig, no spreadsheet_id fields. The actual architecture is purely Telegram-based: CLI → config.yaml → monitor → Task → Telethon messages → forwarding. This creates a fundamental mismatch where the audit spec describes a data flow that doesn't exist in the codebase.

**Evidence:**
- Audit spec line 26: "Trace the entire path: `CLI command` → `config loading` → `Google Sheets API call` → `raw data` → `post extraction` → `image processing` → `queue` → `Telegram API call` → `cleanup`."
- Codebase grep returns no matches for `GSheetsReader`, `GoogleSheetsConfig`, `google_sheets`, or `spreadsheet_id`
- `pyproject.toml` has no google-api-python-client or google-auth dependencies
- Actual flow is: `cli.py:run()` → `TelepostConfigReader.load()` → `TelegramClient` → `Task` → `iter_messages()` → `process_messages()` → `forward_to_users()`
- docs/00-overview/overview.md describes only Telegram integration with no mention of Google Sheets

**Recommendation:** Update the audit spec to reflect the actual architecture. The data flow consists of: CLI → config loading → Telegram client auth → per-channel message fetching → keyword matching → message forwarding. Remove references to Google Sheets, PostProcessor, and ImageCache which are not part of this codebase.

**Effort:** small
**Priority:** mandatory

---

### DF-002: ~~Missing forum topic support breaks data flow for Telegram forums~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor_forward.py, src/mko_telebot/core/channels.py |
| **Classification** | advisory |

> **Rejection reason:** No specification, documentation, or configuration model in this codebase references `topic_id` for Telegram forum topics. The current architecture works correctly for basic Telegram channel forwarding. Adding forum support would be a feature enhancement, not a spec deviation. The ROI is negative at this project scale — the feature doesn't exist in the product requirements. This finding duplicates SRV-004 which was similarly rejected.

**Description:** The audit spec requires "Topic/forum support — topic_id is passed correctly to send_message and send_file for forum topics" (line 97). The `forward_to_users()` function in `monitor_forward.py` (lines 71-76) calls `send_message` and `send_file` without passing `topic_id`, preventing forwarding to specific forum topics within a chat. The `ChannelConfig` model lacks a `topic_id` field to configure this.

**Evidence:**
- `monitor_forward.py` lines 71-76: `send_file(target, msg_media, caption=caption)` and `send_message(target, caption)` have no topic_id parameter
- `channels.py` ChannelConfig: No topic_id field defined among its 8 fields
- No references in docs/00-overview/overview.md or docs/11-guides/configuration.md
- SRV-004 (Phase 03) was rejected with identical reasoning: "feature enhancement, not spec requirement"

**Recommendation:** Consider adding `topic_id` support as a future enhancement if forum topic forwarding becomes a product requirement. Not a mandatory fix.

**Effort:** small
**Priority:** recommended

---

### DF-003: ~~OSError not handled in Telegram message sending/receiving~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | advisory |

> **Rejection reason:** OSError handling is unnecessary because RPCError already covers network-level failures in Telethon. Adding generic OSError handling could mask legitimate programming errors and is redundant with existing error handling. This finding duplicates INT-002 which was partially validated with the same conclusion.

**Description:** The audit spec requires "OSError triggers retries with exponential backoff" (line 84) for Telegram integration. However, `forward_to_users()` only handles `FloodWaitError` and `RPCError`, not `OSError`. Network-level failures (connection drops, DNS issues, timeouts) would raise `OSError` and cause message loss without retry.

**Evidence:**
- `monitor_forward.py` lines 84-102: Only `FloodWaitError` and `RPCError` are caught with retry logic
- `monitor_forward.py` lines 195-203: Only `FloodWaitError` and `TelegramServiceError` in `process_task()`
- Telethon's RPCError is the base class for all Telegram API network errors, covering connection-level failures
- INT-002 (Phase 05) validation concluded: "OSError handling is unnecessary (RPCError covers network-level failures)"

**Recommendation:** Consider adding handling for `WorkerBusyTooLongRetryError` from telethon.errors (which is a specific Telegram retryable error), but generic OSError handling provides no value.

**Effort:** small
**Priority:** recommended

---

### DF-004: Task entity resolution leaves partial state on error

| Field | Value |
|-------|-------|
| **ID** | DF-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py, src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** In `resolve_targets_entities()` (task.py lines 63-78), when resolving multiple targets, the code appends each entity to `forward_to_entities` as it succeeds. If an error occurs on the second or later target, the first entity remains in the list while the exception is raised. This partial state is tested and documented (test_task.py lines 327-330 explicitly validates this behavior), but represents poor design — entities should be collected atomically before assignment.

**Evidence:**
- `task.py` lines 66-69: `self.forward_to_entities.append(entity)` happens inside the try block before the potential exception
- `task.py` line 76: `raise TelegramServiceError` is raised after exception, but entity is already appended
- `test_task.py` lines 327-330: Test confirms partial state is left (asserts `len(task.forward_to_entities) == 1` after error on second target)
- The test suite treats this as intended behavior, but the design pattern violates atomic state update principles
- Cross-validation: SRV-001 (rejected) noted Task has entity resolution methods; DF-004 is a specific consequence of that design

**Recommendation:** Refactor `resolve_targets_entities()` to resolve all entities into a temporary list first, then assign to `forward_to_entities` only if all succeed. This ensures atomic state updates and prevents inconsistent intermediate state.

**Effort:** small
**Priority:** recommended

---

### DF-005: Task state save failures during normal operation leave state inconsistent

| Field | Value |
|-------|-------|
| **ID** | DF-005 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py, src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** In `process_and_reschedule()` (monitor.py lines 40-63), `task.save_state()` is called after `process_task()` completes. If `save_state()` fails (disk full, permission denied), a `StateError` is raised and propagates up, but the in-memory `task.last_msg_id` was already updated during message processing. On restart, the state file would be stale (old last_msg_id), potentially causing re-processing of already-forwarded messages.

**Evidence:**
- `monitor.py` line 59: `await process_task(task, client, settings)` updates `task.last_msg_id` (monitor_forward.py line 208)
- `monitor.py` line 61: `await task.save_state()` called after - if this fails, in-memory state is newer
- `task.py` line 157: `raise StateError` on save failure
- `monitor.py` lines 126-132: The finally block disconnects client but doesn't handle state save failures
- `monitor_forward.py` line 208: `task.last_msg_id = max(msg.id for msg in new_messages)` updates in-memory state

**Recommendation:** Wrap `save_state()` in a try/except in `process_and_reschedule()` to log errors without crashing, or implement transactional state writes (write to temp file, then rename on success).

**Effort:** small
**Priority:** recommended

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 0 |

## Mandatory Fixes

- None (Google Sheets spec mismatch was merged to INT-001)

## Advisory Recommendations

- DF-004: Task entity resolution leaves partial state on error
- DF-005: Task state save failures cause state inconsistency

## Doc Updates Needed

- DF-001 merge target: INT-001 (spec incorrectly references non-existent Google Sheets integration)

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | DF-004, DF-005 |
| Reclassified | 0 | — |
| Merged | 1 | DF-001 → INT-001 |
| Rejected | 2 | DF-002, DF-003 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| DF-002 | Missing forum topic support (topic_id) in message forwarding | Feature enhancement, not spec requirement; no product requirement for forum support |
| DF-003 | Missing OSError handling in Telegram message sending/receiving | Redundant with RPCError; OSError handling unnecessary and could mask bugs |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| DF-001 | INT-001 (Phase 05) | Same root cause: audit spec describes Google Sheets architecture that was never implemented. INT-001 has broader scope covering all spec/service mismatches. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| DF-001 | SPEC-DEVIATION | DOC-UPDATE | Code is correct; audit spec is wrong. The spec describes a Google Sheets data flow that doesn't exist. This is a documentation issue, not a code defect. |

---

## Cross-Phase Conflicts Detected

| ID | Type | Conflict |
|----|------|----------|
| DF-002 | SPEC-DEVIATION | Duplicates SRV-004 (Phase 03) regarding topic_id. SRV-004 was rejected as a feature enhancement, not a spec requirement. |
| DF-003 | SPEC-DEVIATION | Overlaps INT-002 (Phase 05). INT-002 was partially validated with same conclusion (OSError unnecessary, RPCError covers network errors). |

---

## Warnings

- DF-001/INT-001/SRV-005 collectively indicate a systematic audit spec error where the specification assumes a Google Sheets-based architecture that differs significantly from the actual Telegram-only implementation. All three findings stem from the same root cause.
- DF-004 represents a design quality issue where the Task class maintains intermediate state during error conditions. While the test suite validates this behavior, it violates atomic state update principles.
- DF-005 state inconsistency risk is low probability (disk/permission errors during save) but could cause message duplication on recovery.