---
name: 07-tests
description: Test quality audit findings for Telegram classified monitor CLI
status: complete
validated: no
---

# Phase 07 Audit Findings — Test Quality

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### TST-001: Over-mocking in process_messages tests — testing mocks instead of actual logic

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_monitor.py |
| **Classification** | advisory |

**Description:** The tests in `TestProcessMessages` mock `forward_to_users` (an internal helper) rather than testing the actual message processing logic. These tests verify that `forward_to_users` was called, but since `forward_to_users` is mocked, the tests do not validate that the actual message forwarding logic works correctly. The critical path — the integration between message parsing, keyword matching, and forwarding — is not tested end-to-end.

**Evidence:** `tests/test_monitor.py:415-485` shows `process_messages` tests using `patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock)` and then asserting `mock_forward.assert_awaited_once()` or `mock_forward.assert_not_called()`. The actual `forward_to_users` logic (including caption building, retry logic, and media handling) is never exercised in combination with `process_messages`.

**Recommendation:** Add integration tests that exercise `process_messages` → `forward_to_users` → `client.send_message` without mocking `forward_to_users`, or test `forward_to_users` independently with a real mock client. The current tests provide a false sense of security because they only verify the mock was called, not that the forwarding actually works.

---

### TST-002: No tests for monitor main orchestration functions (process_task, reschedule_task, process_and_reschedule, main_loop, run_monitor)

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** Critical orchestration functions in `monitor.py` have zero test coverage. These functions form the main monitoring loop, task processing, and state persistence flow:
- `process_task()` (lines 231-269) — fetches and processes messages for a channel
- `reschedule_task()` (lines 272-283) — schedules next run with random delay
- `process_and_reschedule()` (lines 286-305) — combines processing and persistence
- `main_loop()` (lines 308-344) — main async monitoring loop
- `run_monitor()` (lines 346-356) — entry point for monitoring

**Evidence:** `grep -r "process_task\|reschedule_task\|process_and_reschedule\|main_loop\|run_monitor" tests/` returns no matches. The audit dimension table in phase 07-audit-tests.md requires tests for TelegramPoster equivalent (monitor), but the main orchestration functions are untested.

**Recommendation:** Add async tests for these functions. At minimum, test that `main_loop` creates tasks correctly, `process_task` handles empty results, and `reschedule_task` applies the correct delay formula. A bug in any of these functions could cause the monitor to fail silently or not process messages at all.

---

### TST-003: No tests for logging setup module

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/logging.py |
| **Classification** | advisory |

**Description:** The `setup_logging()` function in `logging.py` has no dedicated tests. It handles fallback to `basicConfig` when log config is missing and applies logging configuration via `dictConfig`. If this function fails, users would get no visibility into application behavior.

**Evidence:** `grep -r "setup_logging" tests/` returns no results. The function at `src/mko_telebot/logging.py:22-46` contains logic for loading logging config and handling errors, which is critical for operational observability.

**Recommendation:** Add tests for:
1. Successful logging config loading
2. Fallback behavior when log_config.yaml is missing
3. Application of dictConfig with resolved paths

---

### TST-004: PathResolver utility class and utils module functions lack tests

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/paths.py, src/mko_telebot/core/utils.py |
| **Classification** | advisory |

**Description:** The `PathResolver` class in `paths.py` and several utility functions in `utils.py` have no dedicated tests:
- `PathResolver.resolve()` and `PathResolver.ensure_dir()` methods
- `utils.list_files_in_directory()` 
- `utils.load_config()`
- `utils.merge_dicts()`

**Evidence:** `grep -r "PathResolver\|list_files_in_directory\|load_config\|merge_dicts" tests/` returns no results except for one indirect reference in test_task.py:150. These utilities are used throughout the codebase for path resolution and config loading.

**Recommendation:** Add unit tests for these utility functions to verify path resolution, home directory expansion, and error handling. A path resolution bug could cause config files not to be found in production.

---

### TST-005: Time-dependent test without time freezing

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_task.py |
| **Classification** | advisory |

**Description:** The test `test_computes_correct_offset` verifies that `set_offset_date()` returns a datetime with `tzname() == "UTC"` but does not freeze time. While this test is unlikely to fail, it represents time-dependent testing that could theoretically exhibit non-determinism in edge cases.

**Evidence:** `tests/test_task.py:108-114` calls `set_offset_date()` without mocking `datetime.now(UTC)`. The test passes because UTC timezone is reliably applied, but best practice would freeze time for deterministic testing.

**Recommendation:** Use `freezegun` or `pytest-freeze-time` to freeze time in this test, or at minimum not assert on the specific datetime values. The current test is acceptable but not following strict time-freeze best practices.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 1 |

## Advisory Recommendations

- TST-001: Over-mocking in process_messages tests — testing mocks instead of actual logic
- TST-002: No tests for monitor main orchestration functions (process_task, reschedule_task, process_and_reschedule, main_loop, run_monitor)
- TST-003: No tests for logging setup module
- TST-004: PathResolver utility class and utils module functions lack tests
- TST-005: Time-dependent test without time freezing

---