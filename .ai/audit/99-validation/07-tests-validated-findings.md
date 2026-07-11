---
name: 07-tests-validated
description: Validated test quality audit findings for Telegram classified monitor CLI
status: complete
validated: yes
---

# Phase 07 Audit Findings — Test Quality (Validated)

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** yes

---

## Findings

### TST-001: ~~Over-mocking in process_messages tests — testing mocks instead of actual logic~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_monitor.py |
| **Classification** | advisory |

**Description:** The tests in `TestProcessMessages` mock `forward_to_users` (an internal helper) rather than testing the actual message processing logic. These tests verify that `forward_to_users` was called, but since `forward_to_users` is mocked, the tests do not validate that the actual message forwarding logic works correctly. The critical path — the integration between message parsing, keyword matching, and forwarding — is not tested end-to-end.

**Evidence:** `tests/test_monitor.py:415-485` shows `process_messages` tests using `patch("mko_telebot.monitor.forward_to_users", new_callable=AsyncMock)` and then asserting `mock_forward.assert_awaited_once()` or `mock_forward.assert_not_called()`. The actual `forward_to_users` logic (including caption building, retry logic, and media handling) is never exercised in combination with `process_messages`.

**Recommendation:** No action required - TST-001 is rejected. The audit specification overstates the testing gap; `forward_to_users` is already extensively tested independently in `TestForwardToUsers` (lines 311-400) with real mock clients. The `process_messages` tests correctly unit-test message grouping and keyword matching in isolation.

> **Rejection reason:** The finding overstates the testing gap. Examination of `tests/test_monitor.py` reveals that `forward_to_users` is extensively tested in `TestForwardToUsers` (lines 311-400) with real mock clients, testing caption building, retry logic on FloodWaitError and RPCError, and media handling. The `process_messages` tests correctly unit-test the message grouping and keyword matching logic in isolation — a standard testing pattern. Integration coverage exists via separate test classes, and mocking the internal helper is appropriate for unit testing. No meaningful gap exists that warrants this finding.

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

**Recommendation:** Add async tests in `tests/test_monitor.py` for orchestration functions. Create test methods with real mock clients:

1. `test_process_task_empty_results`: Create mock client with no messages, verify early return and no state save
2. `test_process_task_processes_new_messages`: Mock client returning one message, verify `process_messages` called with correct args
3. `test_reschedule_task_delay_calculation`: Verify delay = `scan_interval + random(10-30)`, use freezegun to test deterministically
4. `test_main_loop_creates_tasks`: Verify each channel creates a Task with resolved entities added to queue
5. `test_run_monitor_client_cleanup`: Verify `client.disconnect()` called even on exception

Use `AsyncMock` for client methods and `pytest-mock` fixtures for temporary state files.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Finding is technically accurate — these functions lack dedicated unit tests. However, architectural assessment shows these are thin orchestration functions primarily calling other tested components (`process_task` calls `process_messages` and `task.save_state` both tested elsewhere). The risk is low given the existing test coverage of dependencies. Still represents a legitimate improvement opportunity.

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

**Recommendation:** Add tests in `tests/test_logging.py`:

```python
def test_setup_logging_loads_config(tmp_path):
    """Test config file loading with valid log_config.yaml."""
    log_config = tmp_path / "log_config.yaml"
    log_config.write_text("version: 1\nformatters: {}")
    setup_logging(log_config=str(log_config))  # Verify no exception

def test_setup_logging_fallback_on_missing(tmp_path):
    """Test basicConfig fallback when config missing."""
    setup_logging(log_config=str(tmp_path / "nonexistent.yaml"))
    # Verify basicConfig was applied (logging.root.handlers not empty)

def test_setup_logging_resolves_paths(tmp_path):
    """Test path resolution in logging config."""
    # Verify dictConfig receives resolved paths, not relative paths
```

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Finding is confirmed. No tests exist for `setup_logging()`. However, the underlying `TelepostConfigReader.load_logging_config()` is tested in `test_config_reader.py` (lines 281-367). The `setup_logging` function is a thin wrapper. While tests would be ideal, the operational risk is mitigated by the existing tests of the underlying config loading. Still represents a valid improvement opportunity.

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

**Recommendation:** Add unit tests in `tests/test_paths.py` and `tests/test_utils.py`:

```python
# tests/test_paths.py
def test_path_resolver_resolve_relative():
    """Verify relative paths resolve to absolute."""
    resolver = PathResolver("/base/dir")
    assert resolver.resolve("config.yaml").is_absolute()

def test_path_resolver_expand_home():
    """Verify ~ expansion in paths."""
    resolver = PathResolver("/base/dir")
    assert str(Path.home()) in resolver.resolve("~/config.yaml")

# tests/test_utils.py  
def test_load_config_parses_yaml(tmp_path):
    """Verify YAML config loading."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("channels:\n  test:\n    name: '@test'")
    result = load_config(str(config_file))
    assert "channels" in result

def test_merge_dicts_combines_nested(tmp_path):
    """Verify dict merging for nested configs."""
    defaults = {"a": 1, "b": {"x": 1}}
    override = {"b": {"y": 2}}
    result = merge_dicts(defaults, override)
    assert result["a"] == 1
    assert result["b"]["x"] == 1
    assert result["b"]["y"] == 2
```

> **Validation Note:**
> - **Action:** Validated with caveats
> - **Detail:** Confirmed — no dedicated tests for `PathResolver` class or utility functions. However, `PathResolver` is primarily used by `AppPaths` properties (tested implicitly via config reader tests), and `utils.load_config()`/`utils.merge_dicts()` are tested indirectly via `TelepostConfigReader` tests. The risk is low for path resolution since these are thin wrappers around standard library `pathlib` and `yaml` functions. Still represents a reasonable improvement opportunity.

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

**Recommendation:** In `tests/test_task.py` lines 108-114, use `freezegun` to freeze time for deterministic testing:

```python
# Add to existing imports or add pytest-freeze-time dependency
from freezegun import freeze_time

@freeze_time("2024-01-15 12:00:00")
def test_computes_correct_offset():
    """Test offset date calculation with frozen time."""
    task = Task(config=channel_config)  # 7-day default
    # Now assertions on specific date values are deterministic
    assert task.offset_date.year == 2024
    assert task.offset_date.month == 1
    assert task.offset_date.day == 8
```

Or remove the test entirely since `datetime.now(UTC)` timezone behavior is tested by Python itself.

> **Validation Note:**
> - **Action:** Validated (low priority)
> - **Detail:** Finding is accurate but trivial. The test only asserts `tzname() == "UTC"` which is deterministic regardless of the actual time. The recommendation to freeze time would add complexity (new dependency) without meaningful benefit. This is a minor best-practice suggestion that doesn't merit strong priority.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 2 |
| LOW | 1 |

## Advisory Recommendations

- TST-002: No tests for monitor main orchestration functions (process_task, reschedule_task, process_and_reschedule, main_loop, run_monitor)
- TST-003: No tests for logging setup module
- TST-004: PathResolver utility class and utils module functions lack tests
- TST-005: Time-dependent test without time freezing

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 4 | TST-002, TST-003, TST-004, TST-005 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 1 | TST-001 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| TST-001 | Over-mocking in process_messages tests | Tests are appropriately isolated; forward_to_users has extensive dedicated testing in TestForwardToUsers class |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | — |

---

## Rollout Analysis

The test coverage gaps identified (TST-002, TST-003, TST-004) present low operational risk:

1. **TST-002 orchestration functions**: Adding tests would require mocking `TelegramClient` and `Task` objects. The functions delegate to already-tested components (`process_task` → `process_messages`, `task.save_state`). Risk of bugs is mitigated by existing coverage.

2. **TST-003 setup_logging**: The underlying `load_logging_config` is tested. Adding unit tests would be straightforward using temporary files.

3. **TST-004 utility functions**: These are thin wrappers around `pathlib` and `yaml` modules with minimal business logic. Risk of bugs is inherently low.

---

## Cross-Phase Conflict Analysis

### CONFLICT-001: TST-002 vs SRV-003 — Architectural Discrepancy

| Field | Value |
|-------|-------|
| **Conflict ID** | CONFLICT-001 |
| **Severity** | MEDIUM |
| **Affected Phases** | 07-tests (TST-002), 03-services (SRV-003) |

**Description:** TST-002 recommends adding tests for monitor orchestration functions under the assumption they exist in a class-based architecture. SRV-003 identifies that the specification documents service classes (`TelegramPoster`, `TelegramService`, etc.) that do not exist — the actual implementation uses procedural functions in `monitor.py` instead.

**Evidence:**
- TST-002 references "TelegramPoster equivalent (monitor)" for test coverage expectations
- SRV-003 confirms `monitor.py` contains only standalone functions, not the documented `TelegramPoster` class
- The audit spec in `03-audit-services.md:63` expects class-based services that were never implemented

**Resolution:** TST-002's recommendation remains valid — the current procedural orchestration functions still need test coverage. However, any future re-architecture toward class-based services (as per SRV-003) should prioritize testability during implementation.