---
name: 07-tests-validated
description: Validated audit findings for Test Quality
agent: validator
status: complete
validated: yes
---

# Phase 07 Validated Audit Findings — Test Quality

**Executor:** validator  
**Source:** .ai/audit/07-tests/findings.md  
**Status:** complete  
**Validated:** yes

---

## Findings

### TST-001: Missing tests for process_task function (critical path)

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | mandatory |

**Description:** The `process_task` function in `monitor_forward.py` is a critical architectural component that fetches messages from Telegram channels and orchestrates the message processing pipeline. It handles `iter_messages` API calls, `FloodWaitError`, and `TelegramServiceError` exceptions. No tests exist for this function, leaving a critical path untested that could silently fail in production.

**Evidence:**
- `src/mko_telebot/monitor_forward.py` lines 164-216 define `process_task`
- Search confirms 0 matches for `process_task` in any test file
- Function handles min_id calculation, async iteration, flood wait errors, and TelegramServiceError

**Recommendation:** Add tests for `process_task` covering: successful message fetching, flood wait error handling, Telegram service error handling, empty message list handling, and last_msg_id update logic. Effort: medium.

---

### TST-002: Missing tests for run_monitor main orchestration (critical path)

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | mandatory |

**Description:** The `run_monitor` function in `monitor.py` is the primary entry point for the monitoring service. It handles client startup, main loop execution, and client disconnection. Without tests, failures in the orchestration layer (startup failures, cleanup issues) cannot be detected.

**Evidence:**
- `src/mko_telebot/monitor.py` lines 117-133 define `run_monitor`
- Search confirms 0 matches for `run_monitor` or `TestRun` in test files
- Function wraps `start_client`, `main_loop`, and cleanup in try/finally

**Recommendation:** Add tests for `run_monitor` covering: successful startup and loop entry, KeyboardInterrupt handling, client disconnect on exit, and error handling for MkoTelebotError. Effort: medium.

---

### TST-003: Missing tests for main_loop scheduling logic

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | mandatory |

**Description:** The `main_loop` function handles task queue management, channel entity resolution, state loading, and target resolution. This is critical for correct monitoring behavior but has no test coverage.

**Evidence:**
- `src/mko_telebot/monitor.py` lines 66-115 define `main_loop`
- No test classes or functions reference this function
- Function creates tasks, resolves entities, loads state, populates queue

**Recommendation:** Add tests for `main_loop` covering: task creation, entity resolution calls, state loading, queue population, and the infinite loop structure. Effort: medium.

---

### TST-004: Missing tests for async reschedule_task function

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | mandatory |

**Description:** The `reschedule_task` function handles staggered task rescheduling with random delays. This affects monitoring timing and rate limiting but has no test coverage.

**Evidence:**
- `src/mko_telebot/monitor.py` lines 20-37 define `reschedule_task`
- Search confirms 0 matches in test files
- Function uses asyncio.sleep with random delay, then puts task back in queue

**Recommendation:** Add tests for `reschedule_task` covering: delay calculation, queue put operation, and async sleep behavior. Effort: small.

---

### TST-005: Missing tests for setup_logging function

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/logging.py |
| **Classification** | mandatory |

**Description:** The `setup_logging` function in `logging.py` configures application logging from YAML config or falls back to basicConfig. This is critical for operational reliability and observability. No tests cover this function.

**Evidence:**
- `src/mko_telebot/logging.py` lines 22-46 define `setup_logging`
- No test imports `setup_logging` directly
- Function handles config loading, dictConfig, and fallback to basicConfig

**Recommendation:** Add tests for `setup_logging` covering: successful YAML config loading, fallback to basicConfig when file missing, and error handling. Effort: small.

---

### TST-006: Over-mocking in process_messages tests undermines test value

| Field | Value |
|-------|-------|
| **ID** | TST-006 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_monitor.py |
| **Classification** | advisory |

**Description:** The `process_messages` tests mock `forward_to_users` (which is in the same module) and verify only that the mock was called. This tests the mock infrastructure, not the actual business logic. The tests cannot detect bugs in `forward_to_users` itself because it's replaced with a mock. Additionally, the assertions check mock call counts rather than verifying meaningful side effects.

**Evidence:**
- `tests/test_monitor.py` lines 466-536 show 7 tests using `patch("mko_telebot.monitor_forward.forward_to_users", ...)` and asserting mock call counts
- Example at lines 466-468

**Recommendation:** Tests should either: (1) use integration-style tests that don't mock internal functions, verifying actual outcomes; or (2) test `process_messages`'s grouping logic and filtering logic directly by checking internal state changes. Mocking `forward_to_users` and asserting it was called tests nothing meaningful. Effort: medium.

---

### TST-007: Missing tests for resolve_channel_entity in critical paths

| Field | Value |
|-------|-------|
| **ID** | TST-007 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | mandatory |

**Description:** While `resolve_channel_entity` has basic tests, it's tested in isolation without integration context. The function is a critical dependency for all channel monitoring but error paths involving rate limiting or connection failures are not tested with realistic scenarios.

**Evidence:**
- `tests/test_task.py` lines 275-298 test only success and generic ValueError
- No tests cover rate limiting (FloodWaitError), network timeouts, or connection failures
- Function wraps `client.get_entity` in generic try/except

**Recommendation:** Add tests covering FloodWaitError, timeout scenarios, and verify proper error propagation to TelegramServiceError. Effort: small.

---

### TST-008: Missing tests for resolve_targets_entities partial failure

| Field | Value |
|-------|-------|
| **ID** | TST-008 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Classification** | mandatory |

**Description:** `resolve_targets_entities` has error handling that continues after partial success (first entity resolved before error). The test at line 333 verifies `forward_to_entities` has length 1, but the real behavior involves an async sleep between resolutions that could affect rate limiting not covered.

**Evidence:**
- `tests/test_task.py` lines 320-342
- The test mocks `get_entity` side effects but doesn't verify the async sleep calls between entity resolutions

**Recommendation:** Add test verifying async sleep is called between target resolutions to confirm rate-limiting behavior. Effort: small.

---

### TST-009: No coverage for parser module unit tests

| Field | Value |
|-------|-------|
| **ID** | TST-009 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/parser.py, src/mko_telebot/core/ast_nodes.py |
| **Classification** | mandatory |

**Description:** The `parser.py` and `ast_nodes.py` modules contain the query parsing logic but have no dedicated unit tests. Tests in `test_parser.py` only indirectly test `search_match` which calls `parse_query` internally. Parser edge cases (malformed queries, nested groups, invalid syntax) are not tested at the parser level.

**Evidence:**
- `tests/test_parser.py` only tests `search_match` via the `matcher` fixture
- No tests import `PatternParser` or `parse_query` directly
- No tests reference `ExactMatch`, `Wildcard`, `Exclusion`, `Sequence`, or `OrOperation` classes directly

**Recommendation:** Add unit tests for `PatternParser` and `parse_query` covering: tokenization edge cases, nested parentheses, malformed queries, and verify AST node types produced. Effort: large (but could be incremental).

---

### TST-010: Missing tests for path resolution helper

| Field | Value |
|-------|-------|
| **ID** | TST-010 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/config.py |
| **Classification** | advisory |

**Description:** The `resolve_path` helper function handles relative/absolute path resolution for configuration files. While it's used in tests via the config reader, it has no dedicated unit tests.

**Evidence:**
- `src/mko_telebot/core/config.py` lines 27-47 define `resolve_path`
- No direct tests for this function

**Recommendation:** Add unit tests for `resolve_path` covering: absolute path passthrough, relative path resolution, home-directory expansion (~), and edge cases. Effort: trivial.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 10 | All findings |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

- None

### Merged Findings

- None

### Reclassified Findings

- None

---

## Validation Notes

All findings from the auditor were verified as technically correct. The codebase lacks test coverage for:

1. **Critical orchestration functions** (`process_task`, `run_monitor`, `main_loop`) - these are the main execution paths for the monitoring system
2. **Supporting utility functions** (`reschedule_task`, `setup_logging`, `resolve_path`) - these are used across the codebase
3. **Error scenarios for entity resolution** - FloodWaitError and timeout handling not tested
4. **Parser unit tests** - only integration testing via `search_match` exists
5. **Rate limiting verification** - async sleep calls between entity resolutions not verified

The recommendation to add these tests aligns with project patterns of small, focused test modules and provides clear operational value for a CLI tool that interacts with external APIs.