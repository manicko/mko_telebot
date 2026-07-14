---
name: 05-integrations-validated
description: Validated audit findings for external integrations phase
validated: yes
validated_date: 2026-07-14
---

# Phase 05 Audit Findings - External Integrations

**Executor:** auditor → validated
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** yes

---

## Findings

### INT-001: Missing RPCError handling during message fetching in process_task

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | advisory |

**Description:** The `process_task()` function in `monitor_forward.py` (lines 232-244) catches `FloodWaitError`, `WorkerBusyTooLongRetryError`, and `TelegramServiceError` during message fetching, but does NOT catch generic `RPCError`. Since `RPCError` is the base class for all Telegram RPC errors (including `TimedOutError` and `ServerError`), transient network errors during `iter_messages()` are not handled with retry logic. This creates an inconsistency: while send operations retry on `RPCError`, fetch operations do not.

**Evidence:** 
- `src/mko_telebot/monitor_forward.py:232-244` - Exception handlers for message fetching
- `src/mko_telebot/monitor_forward.py:78-84` - Exception handler for send operations DOES catch `RPCError`
- Telethon error hierarchy confirmed: `TimedOutError` and `ServerError` are direct subclasses of `RPCError`, while `FloodWaitError` is a subclass of `RPCError` via `FloodError`

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Finding is technically correct. The `_send_with_retry` function (lines 78-84) catches `RPCError` for send operations, but `process_task` only catches `FloodWaitError`, `WorkerBusyTooLongRetryError`, and `TelegramServiceError`. `TimedOutError`, `ServerError`, and other `RPCError` subclasses are not handled during message fetching, which could cause unhandled exceptions for transient API errors.
> - **See also:** —

**Recommendation:** Add `RPCError` handling to `process_task()` during message fetching to ensure transient errors like `TimedOutError` and `ServerError` are handled gracefully with appropriate delays, consistent with the send retry logic.

---

### INT-002: FloodWaitError seconds value defaults to 0 in test setup but production code assumes it has a value

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | tests/test_monitor_forward.py, tests/test_monitor.py |
| **Classification** | advisory |

**Description:** Tests instantiate `FloodWaitError(request=None)` without the `capture` parameter, resulting in `e.seconds == 0`. While the tests pass and verify the retry loop works, they do not validate that actual wait times from Telegram (e.g., 30s, 60s, etc.) are properly handled. The production code at line 63 uses `e.seconds` in the wait calculation, expecting a positive integer.

**Evidence:**
- `tests/test_monitor_forward.py:115` - `raise FloodWaitError(request=None)` creates error with seconds=0
- `tests/test_monitor_forward.py:241` - Same pattern
- `tests/test_monitor.py:428` - Same pattern in `mock_client.send_message.side_effect`
- Confirmed via runtime: `FloodWaitError(request=None)` yields `e.seconds == 0`, while `FloodWaitError(request=None, capture=30)` yields `e.seconds == 30`

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Finding is technically correct. The tests verify the retry loop mechanism works but do not validate realistic wait time handling. This is a test quality improvement opportunity.
> - **See also:** —

**Recommendation:** Update tests to use `FloodWaitError(request=None, capture=30)` or similar to verify actual wait time handling, though this is a test quality improvement rather than a critical bug.

---

### INT-003: Client lifecycle uses synchronous disconnect() but should handle potential async cleanup

| Field | Value |
|-------|-------|
| **ID** | INT-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `run_monitor()` function calls `client.disconnect()` synchronously in the finally block (line 137). While Telethon's `disconnect()` is a synchronous method, there could be pending async operations that need cleanup. Additionally, if `disconnect()` raises an exception, it would propagate after the main work is done, potentially masking the original error.

**Evidence:**
- `src/mko_telebot/monitor.py:137` - `client.disconnect()` without error handling
- Confirmed via runtime: `TelegramClient.disconnect` is a synchronous (non-coroutine) function, not async

> **Validation Note:**
> - **Action:** Rejected
> - **Detail:** The finding is technically correct about the synchronous nature, but Telethon's `disconnect()` is intentionally synchronous in Telethon's API design. The recommendation to wrap in try-except for cleanup errors is low ROI - `disconnect()` is a well-tested library method that rarely raises exceptions in normal operation. Any exception during disconnect would indicate a serious library or environment issue, and masking it would hide important diagnostic information. The current behavior is appropriate for a monitoring application that should surface unexpected problems.
> - **See also:** —

**Recommendation:** (Not accepted) Consider wrapping `client.disconnect()` in a try-except block to prevent cleanup errors from masking the original exception, and verify no pending async tasks need cancellation.

---

### INT-004: Unresolved FloodWaitError during entity resolution causes unhandled exception

| Field | Value |
|-------|-------|
| **ID** | INT-004 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** The `resolve_channel_entity()` and `resolve_targets_entities()` methods in `task.py` catch all exceptions and re-raise as `TelegramServiceError` (lines 81-87, 100-106). However, when `FloodWaitError` occurs during entity resolution, it is immediately re-raised as `TelegramServiceError` without any wait logic, causing the application to stop rather than waiting and retrying. This could prevent the monitor from starting when Telegram is rate-limiting entity lookups.

**Evidence:**
- `src/mko_telebot/core/task.py:81-87` - Generic exception handling without FloodWait special case
- `src/mko_telebot/core/task.py:100-106` - Same pattern in resolve_targets_entities
- `tests/test_task.py:300-308` - Tests expect `TelegramServiceError` to be raised on FloodWaitError

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Finding is correct. When FloodWaitError occurs during `get_entity()` calls for channel or target resolution, the current code immediately re-raises as TelegramServiceError without waiting. This would cause the monitor to fail during startup when Telegram rate-limits entity lookups, rather than waiting and potentially recovering. The test at line 305-307 confirms this is current behavior.
> - **See also:** —

**Recommendation:** Consider adding special handling for `FloodWaitError` during entity resolution to wait for the specified duration before re-raising, allowing the monitor to potentially recover from temporary rate limiting during startup.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 2 |

## Mandatory Fixes

None - no critical or mandatory-classified issues found.

## Advisory Recommendations

1. INT-001: Add RPCError handling during message fetching in process_task() (VALIDATED)
2. INT-002: Update FloodWaitError test setup to use realistic wait times (VALIDATED)
3. INT-003: Add error handling around client.disconnect() in run_monitor() (REJECTED - low ROI)
4. INT-004: Handle FloodWaitError with wait during entity resolution (VALIDATED)

## Doc Updates Needed

None

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 3 | INT-001, INT-002, INT-004 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 1 | INT-003 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| INT-003 | Client lifecycle uses synchronous disconnect() but should handle potential async cleanup | Low ROI for monitoring application. Telethon's disconnect() is intentionally synchronous. Exception during disconnect would indicate a serious issue that should be surfaced. The suggested try-except would mask diagnostic information without meaningful benefit. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | — |

---

**Note:** All 63 tests pass. The validated issues are recommendations for improved robustness during edge cases, particularly for transient Telegram API errors during both fetch and resolution operations.