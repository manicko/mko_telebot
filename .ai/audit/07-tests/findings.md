---
name: 07-audit-tests-findings
description: Test quality audit findings
agent: auditor
status: complete
validated: no
---

# Phase 07 Audit Findings — Test Quality

**Executor:** auditor  
**Template:** .kilo/commands/audit/phases/07-audit-tests.md  
**Status:** complete  
**Validated:** no

---

## Runtime Verification Results

| Check | Result |
|-------|--------|
| R1 - Full Test Suite Run | 103 passed in 2.39s (no failures) |
| R2 - Test Failures Analysis | No test failures to analyze |
| R3 - Tautological Tests | No tautological tests detected (no `assert True`, `assert 1 == 1`, or empty test bodies) |
| R4 - Test Isolation | Tests pass consistently; however, test mutation of `APP_PATHS.__dict__` creates risks |
| R5 - Coverage Gaps | Multiple critical components have no tests |

---

## Findings

### TST-001: Task model has no unit tests despite complex async state management

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | mandatory |

**Description:** The `Task` class in `core/task.py` implements critical async state management logic including `load_state()`, `save_state()`, `resolve_channel_entity()`, `resolve_targets_entities()`, and `set_offset_date()`. None of these methods have unit tests. A failure in state persistence could cause message duplication or missed messages on restart.

**Evidence:**
- `tests/` directory contains no `test_task.py` file
- `tests/` contains no `test_monitor.py` file for monitor functions
- `Task.save_state()` and `Task.load_state()` involve file I/O that could fail silently
- `Task.resolve_channel_entity()` raises `TelegramServiceError` on failure — untested error path

**Recommendation:** Add `tests/test_task.py` with tests for: (1) state file creation and loading, (2) entity resolution errors, (3) offset date computation, (4) error handling for file I/O failures. Effort: medium - requires async test patterns with mocked Telethon client.

---

### TST-002: Monitor module has no tests for core forwarding logic

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | mandatory |

**Description:** The `monitor.py` module contains critical functions `create_client()`, `start_client()`, `forward_to_users()`, `process_messages()`, `process_task()`, and `run_monitor()` that handle Telegram API interactions. None of these functions have unit tests. The `run` CLI command is tested only for its help output, not for actual execution paths.

**Evidence:**
- `tests/test_cli.py` only tests `--help`, `version`, `config`, `validate`, and `init` commands — no `run` command tests
- No `test_monitor.py` exists in tests directory
- `forward_to_users()` (lines 121-173) handles FloodWait and TelegramService errors — untested
- `process_messages()` (lines 175-215) handles keyword matching and media grouping — untested
- Monitor tests would require async patterns and mocked Telethon client

**Recommendation:** Add `tests/test_monitor.py` with async tests for: (1) `create_client()` session path resolution, (2) `forward_to_users()` message and media handling, (3) `process_messages()` keyword filtering logic. Effort: medium - requires async test fixtures and mocking TelegramClient.

---

### TST-003: Pydantic model validators have no dedicated test coverage

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/telethon.py, src/mko_telebot/core/channels.py |
| **Classification** | mandatory |

**Description:** Pydantic validators in `telethon.py` (`validate_api_hash`, `validate_api_id`, `validate_phone_or_token`) and `channels.py` (`strip_defaults_from_channels`) are not explicitly tested. Invalid configuration values would only be caught at runtime during `load()`, potentially with unclear error messages.

**Evidence:**
- `tests/test_config_reader.py` tests config loading but does not explicitly test invalid field values
- `telethon.py` lines 37-67: validators reject placeholder values (`YOUR_`, `12345`) — untested
- No tests verify that `api_hash` validation rejects `YOUR_API_HASH`
- No tests verify that `api_id=12345` raises a clear validation error

**Recommendation:** Add tests for model validation edge cases: (1) placeholder rejection in `TelethonConfig`, (2) `ChannelsConfig` `DEFAULTS` stripping behavior, (3) field constraint violations. Effort: small - add parameterized tests to `test_config_reader.py`.

---

### TST-004: Template config.yaml has invalid structure, init tests don't catch it

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/settings/config.yaml, src/mko_telebot/core/channels.py |
| **Classification** | mandatory |

**Description:** The template `config.yaml` has `DEFAULTS` nested inside `channels` dictionary with fields from `ChannelsConfig` (`stagger_start_seconds`) in `ChannelDefaults`, which has a different field set. This misstructure causes a Pydantic validation error when users run `init` followed by `validate`. The init tests pass because they only check file copying, not whether the copied config is valid.

**Evidence:**
- `src/mko_telebot/settings/config.yaml` lines 4-16: `DEFAULTS` incorrectly placed under `channels`
- `src/mko_telebot/core/channels.py` line 103-104: `stagger_start_seconds` is a `ChannelsConfig` field, not `ChannelDefaults`
- `tests/test_cli.py` line 106-127: `test_init_creates_config_directory` only checks files are copied, not that content is valid

**Recommendation:** Test should verify that init-copied config can be successfully loaded by `TelepostConfigReader.load()`. Fix the template structure to match the Pydantic model. Effort: small.

---

### TST-005: Test isolation pattern creates shared mutable state risks

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_cli.py |
| **Classification** | advisory |

**Description:** Tests in `TestCliValidate` and `TestCliInit` mutate `APP_PATHS.__dict__` directly (lines 87-88, 115-118, 140-144, 165-169) to redirect paths. While tests pass individually, this pattern creates shared mutable state that could cause non-deterministic failures if tests run in parallel or different orders.

**Evidence:**
- `tests/test_cli.py` line 87-88: `APP_PATHS.__dict__["user_dir"] = tmp_path`
- `tests/test_cli.py` line 115-118: Same mutation pattern in multiple tests
- This modifies the singleton `APP_PATHS` instance rather than using dependency injection
- No fixture cleanup for parallel test safety

**Recommendation:** Use `monkeypatch` fixture or create isolated test instances instead of mutating module-level singletons. Effort: small - refactoring test setup.

---

### TST-006: `run` CLI command has no error path tests

| Field | Value |
|-------|-------|
| **ID** | TST-006 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/cli.py |
| **Classification** | mandatory |

**Description:** The `run` CLI command (lines 86-100 in cli.py) exits with code 1 on config errors (handled) but has no tests for other error scenarios like Telegram client initialization failure, auth errors, or service errors. The command is skipped entirely in tests.

**Evidence:**
- `tests/test_cli.py` lists tests for `init`, `validate`, `config`, `version` commands
- No test for `run` command execution
- `cli.py` line 88-94: `setup_logging()` and `TelepostConfigReader.from_user_dir()` error handling untested
- `cli.py` line 96-100: `create_client()` and `run_monitor()` have no test coverage

**Recommendation:** Add test for `run` command with missing config (exit code 1) and invalid config (exit code 1). Effort: small - reuse existing config error patterns.

---

### TST-007: Audit spec references non-existent PostProcessor/ImageCache/TelegramPoster

| Field | Value |
|-------|-------|
| **ID** | TST-007 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | Audit specification |
| **Classification** | advisory |

**Description:** The audit phase specification (lines 27, 99-103) references `PostProcessor`, `ImageCache`, and `TelegramPoster` classes that do not exist in the codebase. The project is a Telegram channel monitor, not a Google Sheets → Telegram publisher.

**Evidence:**
- `.kilo/commands/audit/phases/07-audit-tests.md` lines 27, 99-103 list non-existent components
- Grep search for `class (PostProcessor|ImageCache|TelegramPoster)` returns no matches in `src/`
- Only `TelegramServiceError` exists (in errors.py)

**Recommendation:** Update the audit phase specification to reflect actual architecture: `Task` and `monitor.py` functions handle Telegram operations. Effort: trivial - documentation update.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 2 |
| LOW | 1 |

## Mandatory Fixes

- TST-001: Task model has no unit tests despite complex async state management
- TST-002: Monitor module has no tests for core forwarding logic
- TST-003: Pydantic model validators have no dedicated test coverage
- TST-004: Template config.yaml has invalid structure, init tests don't catch it
- TST-006: `run` CLI command has no error path tests

## Advisory Recommendations

- TST-005: Test isolation pattern creates shared mutable state risks
- TST-007: Audit spec references non-existent PostProcessor/ImageCache/TelegramPoster