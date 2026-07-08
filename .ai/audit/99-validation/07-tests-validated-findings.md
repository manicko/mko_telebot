---
name: 07-audit-tests-validation
description: Validated test quality audit findings
agent: validator
status: complete
---

# Phase 07 Audit Findings — Test Quality (Validated)

**Source:** .ai/audit/07-tests/findings.md  
**Validator:** validator  
**Status:** complete

---

## Runtime Verification Results

| Check | Result |
|-------|--------|
| R1 - Full Test Suite Run | 103 passed in 2.39s (no failures) |
| R2 - Test Failures Analysis | No test failures to analyze |
| R3 - Tautological Tests | No tautological tests detected |
| R4 - Test Isolation | Tests pass consistently |
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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is confirmed — no `tests/test_task.py` exists. The `Task` class (158 lines) contains async state management (`load_state`, `save_state`), entity resolution (`resolve_channel_entity`, `resolve_targets_entities`), and offset date computation. None of these methods have unit tests. File I/O in `load_state()`/`save_state()` uses `aiofiles` and raises `StateError` on failure — entirely untested error paths.

**Description:** The `Task` class in `core/task.py` implements critical async state management logic including `load_state()`, `save_state()`, `resolve_channel_entity()`, `resolve_targets_entities()`, and `set_offset_date()`. None of these methods have unit tests. A failure in state persistence could cause message duplication or missed messages on restart.

**Evidence:**
- `tests/` directory contains no `test_task.py` file
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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is confirmed — no `tests/test_monitor.py` exists. `monitor.py` (356 lines) contains `forward_to_users()` (lines 121-173), `process_messages()` (lines 175-215), `process_task()` (lines 218-255), `create_client()` (lines 25-47), `start_client()` (lines 50-69), `run_monitor()` (lines 330-340), and `launcher()` (lines 343-353). None have unit tests. The `run` CLI command routes through these functions.

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is confirmed. `tests/test_config_reader.py` tests config loading with valid data only — it never exercises Pydantic field validators with invalid/placeholder values. The validators in `telethon.py` (lines 37-67, 90-100) reject `YOUR_*` placeholders and `api_id=12345`. The `channels.py` `strip_defaults_from_channels` validator (line 108-111) is tested only incidentally. These validators would catch serious configuration errors; their untested state is a gap.

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is confirmed. The template `config.yaml` (lines 4-16) has `DEFAULTS` nested inside `channels.channels` with field `stagger_start_seconds`. This field belongs to `ChannelsConfig` (line 103), not `ChannelDefaults`. Since `ChannelConfig` has `extra="forbid"`, Pydantic would reject `stagger_start_seconds` during dict validation. The `strip_defaults_from_channels` validator runs in `mode="after"`, meaning Pydantic first validates each dict value as `ChannelConfig` (which fails on the extra field). The `init` tests only check file copying (lines 106-127), not that the copied config can be loaded.

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is confirmed. `tests/test_cli.py` lines 87-88, 115-118, 140-144, 165-169 mutate `APP_PATHS.__dict__` directly. The tests use `try/finally` to restore original values, but this pattern creates shared mutable state on a module-level singleton. If tests run in parallel or in unexpected order, non-deterministic failures are possible. The `monkeypatch` fixture is the idiomatic pytest alternative.

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is confirmed. The `validate` command has a missing-config test (line 77-95 in test_cli.py), but `run` has no equivalent test. The `run` command (lines 86-100 in cli.py) has an error path that catches `ConfigError` and exits with code 1 — entirely untested. Testing this follows the same pattern as the existing validate test.

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is confirmed. The audit phase spec (`.kilo/commands/audit/phases/07-audit-tests.md`) lists `PostProcessor`, `ImageCache`, and `TelegramPoster` in its audit scope table (lines 27, 99-103). None of these classes exist in `src/`. Only `TelegramServiceError` exists in `core/errors.py`. This appears to be a copy-paste from a different project's audit spec. No `docs/SPEC.md` exists to cross-reference against.

**Description:** The audit phase specification (lines 27, 99-103) references `PostProcessor`, `ImageCache`, and `TelegramPoster` classes that do not exist in the codebase. The project is a Telegram channel monitor, not a Google Sheets → Telegram publisher.

**Evidence:**
- `.kilo/commands/audit/phases/07-audit-tests.md` lines 27, 99-103 list non-existent components
- No `class (PostProcessor|ImageCache|TelegramPoster)` exists in `src/`
- Only `TelegramServiceError` exists (in errors.py)

**Recommendation:** Update the audit phase specification to reflect actual architecture: `Task` and `monitor.py` functions handle Telegram operations. Effort: trivial - documentation update.

---

## Original Summary (from source findings)

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 2 |
| LOW | 1 |

## Mandatory Fixes (from source findings)

- TST-001: Task model has no unit tests despite complex async state management
- TST-002: Monitor module has no tests for core forwarding logic
- TST-003: Pydantic model validators have no dedicated test coverage
- TST-004: Template config.yaml has invalid structure, init tests don't catch it
- TST-006: `run` CLI command has no error path tests

## Advisory Recommendations (from source findings)

- TST-005: Test isolation pattern creates shared mutable state risks
- TST-007: Audit spec references non-existent PostProcessor/ImageCache/TelegramPoster

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 7 | TST-001, TST-002, TST-003, TST-004, TST-005, TST-006, TST-007 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None.

### Merged Findings

None.

### Reclassified Findings

None.

---

## Warnings

- **Cross-phase dependency:** TST-004 (config.yaml template structure) is a production bug, not just a test gap. Fixing the template structure is a prerequisite before adding the validation test recommended in TST-004.
- **TST-001/TST-002 shared testing infrastructure:** Both findings require async test patterns with mocked `TelethonClient`. A shared conftest fixture for `AsyncMock(TelegramClient)` would benefit both. This is a rollout dependency if implementing both.
- **TST-003/TST-004 overlap:** Both findings involve `channels.py` — TST-003 mentions untested `strip_defaults_from_channels` validator, while TST-004 involves the template data that this validator is designed to handle. Testing the validator requires test data that exercises the DEFAULTS-stripping path.
- **No `SPEC.md` exists:** The dead-code cross-reference rule in the validation process cannot be fully applied for TST-007 since no `docs/SPEC.md` exists. Finding is still valid as `DOC-UPDATE` based on direct code inspection.
- **TST-005 parallel test risk:** Currently low-risk since tests run sequentially, but would become a real problem if pytest-xdist is introduced for speed.