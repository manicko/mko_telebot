---
name: 05-integrations
description: Audit findings for external integrations phase
agent: auditor
alwaysApply: false
---

# Phase 05 Audit Findings — External Integrations

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

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

**Recommendation:** Consider wrapping `client.disconnect()` in a try-except block to prevent cleanup errors from masking the original exception, and verify no pending async tasks need cancellation.

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
- `tests/test_task.py:300-308` - Tests expect `TelegramServiceError` to be raised on FloodWaitError

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

1. INT-001: Add RPCError handling during message fetching in process_task()
2. INT-002: Update FloodWaitError test setup to use realistic wait times
3. INT-003: Add error handling around client.disconnect() in run_monitor()
4. INT-004: Handle FloodWaitError with wait during entity resolution

## Doc Updates Needed

None

---

**Note:** All 63 tests pass. The identified issues are recommendations for improved robustness, not critical bugs.