# Phase 07 Audit Findings â€” Test Quality (Validated)

**Executor:** auditor
**Validator:** validator
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** yes
**Validation date:** 2026-07-03
**Validation scope:** `.ai/audit/07-tests/findings.md`
**Source files inspected:** `src/mko_telepost/core/gsheets_reader.py`, `src/mko_telepost/core/paths.py`, `tests/test_gsheets_reader.py`, `tests/test_app.py`, `tests/test_image_cache.py`, `pyproject.toml`, `.ai/context/commands.md`
**Tooling verification:** `uv run ruff check tests/test_image_cache.py tests/test_gsheets_reader.py tests/test_app.py` â†’ `All checks passed!`; `uv run ruff format --check tests/test_image_cache.py` â†’ `Would reformat` (confirms TST-005).

---

## Validation Outcome

All five findings are **VALIDATED as submitted**. None rejected, none merged, none reclassified. Types and severities are confirmed against the implementation. One cross-finding dependency note (TST-001 â†” TST-002) and a non-blocking rollout-ordering suggestion are recorded below.

**Problems only:** This report records only confirmed problems and their validation status per the `problems_only = TRUE` directive. No approved-as-is platitudes are restated beyond what is required for self-containment.

---

## Runtime Verification Summary

- **Step R1 (full suite):** `224 passed in 1.81s` (Python 3.14.0, pytest 9.0.2, plugins anyio, mock). Zero failures, zero skips, zero errors. Suite is fast and green.
- **Step R2 (failure analysis):** N/A â€” no failures to analyze.
- **Step R3 (tautological/no-op tests):** No `assert True`, `assert 1 == 1`, empty-body, or call-without-assert tests found. The 6 `pass` statements in `test_telegram_service.py` are all inside `except asyncio.CancelledError: pass` blocks (legitimate cancellation handling), not no-op tests.
- **Step R4 (isolation):** Suite run twice in sequence â†’ `224 passed` both times. No order-dependent or non-deterministic failures observed at the suite level. One environment-dependent isolation defect found (see TST-001).
- **Step R5 (coverage gaps):** No coverage tool configured (`pyproject.toml` has no `coverage`/`pytest-cov`). Per phase rules this is advisory, not a finding. Coverage gaps in critical paths are filed individually below.
- **Static gates:** `uv run ruff check tests/` â†’ `All checks passed!`. `uv run mypy tests/` â†’ `Success: no issues found in 17 source files`.

---

## Findings

### TST-001: Environment-dependent test can hang or make real network calls

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | tests/test_gsheets_reader.py, src/mko_telepost/core/gsheets_reader.py |
| **Classification** | mandatory |
| **Validation** | VALIDATED (unchanged) |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Verified against:** `tests/test_gsheets_reader.py:158-170` (relative `Path("credentials.json")`, no `@patch` for `_initialize_service`/`_get_credentials`/`APP_PATHS` â€” confirmed); `src/mko_telepost/core/gsheets_reader.py:79-82` (`self.credentials_file = credentials_file or self._resolve_path(...)`, confirmed); `:88-94` (`_resolve_path` resolves relative paths against `APP_PATHS.user_dir`, confirmed); `:235-240` (`if self.service is None: self.service = self._initialize_service()` then raises only when it returns `None`, confirmed); `:176-199` (`_authorize_new_token` â†’ `flow.run_local_server(port=0)`, confirmed blocking/browser).
> - **Root-cause correctness:** the chain `get_sheet_data` â†’ `_initialize_service` â†’ `_get_credentials` â†’ `_try_load_token` (real `~/.config/mko_telepost/token.json`) â†’ `_authorize_new_token` (real `~/.config/mko_telepost/credentials.json`) is real and unmocked in this test. On a host with a valid `token.json`, the test makes a live Google Sheets API call; on a host with only `credentials.json`, `flow.run_local_server(port=0)` blocks indefinitely. Both hazards are confirmed in the implementation.
> - **Severity:** HIGH confirmed â€” a hanging suite blocks CI; silent network I/O in a unit test is a correctness defect, not a style issue.
> - **Recommendation soundness:** both proposed fixes are hermetic. Option (b) (patch `GSheetsReader._initialize_service` to return `None`) is the smallest change and matches the test docstring intent. Option (a) (tmp_path-absolute `credentials_file`/`token_file`) is also hermetic because neither file would exist â†’ `_try_load_token` returns `None` â†’ `_authorize_new_token` raises `FileNotFoundError` â†’ `_initialize_service` returns `None` â†’ raises. Either is acceptable.
> - **No merge:** distinct defect from TST-002 (which is a coverage gap, not an isolation defect). See cross-finding note below.

**Description:** `test_get_sheet_data_returns_empty_when_service_not_initialized` constructs a `GSheetsReader` with a *relative* `credentials_file=Path("credentials.json")` and does **not** patch `_initialize_service`, `_get_credentials`, `_authorize_new_token`, or `APP_PATHS`. The reader resolves the relative path against the real `APP_PATHS.user_dir` (`~/.config/mko_telepost/` on Linux, `%APPDATA%/mko_telepost/` on Windows).

When `get_sheet_data` is called, `service is None` triggers `_initialize_service()` â†’ `_get_credentials()` â†’ `_try_load_token()` (checks the *real* `~/.config/mko_telepost/token.json`) â†’ if missing, `_authorize_new_token()` calls `InstalledAppFlow.from_client_secrets_file(...)` on the *real* `~/.config/mko_telepost/credentials.json`.

The test only passes today because the developer machine has neither a real `token.json` nor `credentials.json` in the user config dir. On any machine where `mko-telepost init` has been run and real credentials placed:

1. If a **valid `token.json`** exists â†’ `_get_credentials` returns live creds â†’ `build("sheets","v4", credentials=...)` is called â†’ the test makes a **real Google Sheets API call** (network I/O in a unit test, and a flaky test that depends on the sheet's contents).
2. If only **`credentials.json`** exists (no valid token) â†’ `flow.run_local_server(port=0)` **opens a browser window and blocks indefinitely**, hanging the entire suite.

This is a test-isolation defect that couples a unit test to host filesystem/network state.

**Evidence (verified):**
- `tests/test_gsheets_reader.py:158-170` â€” `test_get_sheet_data_returns_empty_when_service_not_initialized`: no `@patch` for `_initialize_service`/`_get_credentials`/`APP_PATHS`; `config = GoogleSheetsConfig(spreadsheet_id=..., credentials_file=Path("credentials.json"))`.
- `src/mko_telepost/core/gsheets_reader.py:79-82` â€” `self.credentials_file = credentials_file or self._resolve_path(self._credentials_file)` (relative path resolved against `APP_PATHS.user_dir`).
- `src/mko_telepost/core/gsheets_reader.py:235-240` â€” `if self.service is None: self.service = self._initialize_service()`; raises only when `_initialize_service()` returns `None`.
- `src/mko_telepost/core/gsheets_reader.py:184-199` â€” `_authorize_new_token` calls `flow.run_local_server(port=0)` (blocking, opens browser) when a credentials file is present.
- `src/mko_telepost/core/paths.py:25,116` â€” `USER_DIR = Path(user_config_dir(APP_NAME))` and `APP_PATHS = AppPaths(..., user_dir=USER_DIR)` â€” confirms the real user-config dir is the resolution base.

**Recommendation:** Make the test hermetic: either (a) pass absolute `tmp_path`-based `credentials_file`/`token_file` to `GoogleSheetsConfig` so `_resolve_path` is never applied to the real user dir, or (b) patch `GSheetsReader._initialize_service` to return `None` directly so the `service is None` branch is exercised without touching real credential resolution. Option (b) is the smallest change and matches the intent stated in the test docstring ("Service is None when initialization fails").

---

### TST-002: GSheetsReader credential-refresh and token-save happy paths are untested

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_gsheets_reader.py, src/mko_telepost/core/gsheets_reader.py |
| **Classification** | advisory |
| **Validation** | VALIDATED (unchanged) |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Verified against:** grep over `tests/` for `_try_refresh_token|_try_load_token|_initialize_service|Token refreshed|_save_token` returns exactly one match â€” `tests/test_gsheets_reader.py:288` (`"_save_token"` as a `patch.object` target). Confirms `_try_refresh_token`, `_try_load_token`, `_initialize_service`, and the `"Token refreshed successfully"` log are never exercised by any test.
> - **Branch 1 (refresh success, `gsheets_reader.py:153-159`):** confirmed untested. The only refresh-related test (`test_get_credentials_refresh_failure_falls_back_to_auth`, lines 214-249) sets `mock_creds.refresh.side_effect=Exception` â€” failure path only. A regression dropping `return creds` on success would not be caught.
> - **Branch 2 (load valid token, `:127-141`):** confirmed untested. Only not-exists and scope-mismatch paths are covered. The happy path returning a usable `Credentials` object directly is never asserted.
> - **Branch 3 (`_save_token` write + permissions, `:206-213`):** confirmed untested. In `test_get_credentials_mismatched_scopes_deletes_token` (lines 251-293), `_save_token` is patched out at lines 286-289, so `token_file.write(creds.to_json())` and `set_restrictive_permissions(self.token_file)` are never executed by any test. The security-adjacent permissioning gap is real.
> - **Type/ROI:** BEST-PRACTICE advisory confirmed. The recommendation (focused unit tests with `MagicMock(spec=OAuth2Credentials)` and a real `tmp_path` token file for `_save_token`) matches project patterns (existing tests already use `MagicMock(spec=OAuth2Credentials)` and `tmp_path`) â€” not overengineered, no new abstraction. Per validator rules, modularization/coverage of security-relevant branches is high-ROI and is not rejected.

**Description:** The OAuth2 credential lifecycle in `GSheetsReader` has several branches with **no positive-path coverage**. A grep across `tests/` shows `_try_refresh_token`, `_try_load_token`, `_initialize_service`, and the literal `"Token refreshed successfully"` log never appear in any test. `_save_token` appears exactly once â€” and only as a `patch.object(GSheetsReader, "_save_token")` that **mocks it out** (`tests/test_gsheets_reader.py:286-289`).

Specific untested branches in `src/mko_telepost/core/gsheets_reader.py`:

1. `_try_refresh_token` **success** path (lines 153-159): `creds.refresh(Request())` succeeds â†’ returns refreshed creds â†’ logs "Token refreshed successfully". Only the *failure* path is covered by `test_get_credentials_refresh_failure_falls_back_to_auth`. A regression that drops the `return creds` on success (e.g. returning `None` and forcing a needless re-auth every run) would not be caught.
2. `_try_load_token` **valid token, scopes match** path (lines 127-141): only the not-exists and scope-mismatch paths are tested. The happy path that returns a usable `Credentials` object directly is untested.
3. `_save_token` **actual write + permissions** path (lines 201-213): in the only test that reaches `_get_credentials` with a successful outcome (`test_get_credentials_mismatched_scopes_deletes_token`), `_save_token` is patched out. Therefore `token_file.write(creds.to_json())` and the security-relevant `set_restrictive_permissions(self.token_file)` call are **never executed by any test**. A bug that silently skips setting restrictive permissions on the token file (which contains live OAuth refresh tokens) would go undetected.

**Evidence (verified):**
- `tests/test_gsheets_reader.py:214-249` â€” `test_get_credentials_refresh_failure_falls_back_to_auth`: only the `refresh.side_effect=Exception` path; no test for `refresh` succeeding.
- `tests/test_gsheets_reader.py:251-293` â€” `test_get_credentials_mismatched_scopes_deletes_token`: `patch.object(GSheetsReader, "_save_token")` at lines 286-289 prevents the real write/permissions code from running.
- `src/mko_telepost/core/gsheets_reader.py:153-159` (refresh success), `:127-141` (load success), `:206-213` (write + `set_restrictive_permissions`) â€” code under test with no exercising test.
- `grep` over `tests/` for `_try_refresh_token|_try_load_token|_initialize_service|Token refreshed` â†’ only `_save_token` matched, and only as a mock target.

**Recommendation:** Add focused unit tests with `MagicMock(spec=OAuth2Credentials)` instances: (a) refresh-succeeds â†’ assert `creds.refresh` called and creds returned; (b) valid token loaded with matching scopes â†’ assert returned without calling `_authorize_new_token`; (c) `_save_token` with a real `tmp_path` token file â†’ assert the file is written and `set_restrictive_permissions` is invoked (this closes the security-adjacent gap on the token-file permissions path).

---

### TST-003: Brittle wall-clock timing assertion in cache-hit test

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_image_cache.py |
| **Classification** | advisory |
| **Validation** | VALIDATED (unchanged) |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Verified against:** `tests/test_image_cache.py:143-151` â€” `start_time = time.time()` â€¦ `elapsed = time.time() - start_time` â€¦ `assert elapsed < 0.1` (confirmed verbatim). The correctness assertion `assert result2 == result1` is present at line 148, so removing the timing assertion leaves a meaningful behavior check in place.
> - **Non-determinism:** confirmed. The bound `0.1 s` is a wall-clock budget over a `stat` + dict lookup that can exceed 100 ms on a throttled CI container or under Windows Defender on-demand scanning of the cache file. Such a failure would be a flake, not a regression.
> - **ROI:** LOW confirmed. The fix is a single-line removal; no behavior change, no abstraction added. Not overengineered.

**Description:** `test_resize_image_cache_hit` asserts a wall-clock performance budget: `assert elapsed < 0.1, "Cache hit should return quickly without image processing"` (`tests/test_image_cache.py:143-151`). This is a non-deterministic, environment-dependent assertion. On a loaded CI runner, Windows defender scanning the cache file, or a container with throttled CPU, a cache-hit `stat` + hash lookup can exceed 100 ms even though the logic is correct. Such a failure would be a flake, not a real regression, and flaky tests erode trust in the suite (developers start re-running instead of investigating).

The test already verifies the *correct* outcome one line above: `assert result2 == result1`. The timing assertion adds no correctness signal â€” it only documents "cache hit is fast", which is a performance characteristic better left to a benchmark or omitted.

**Evidence (verified):**
- `tests/test_image_cache.py:143-151` â€” `start_time = time.time()` â€¦ `elapsed = time.time() - start_time` â€¦ `assert elapsed < 0.1`.

**Recommendation:** Drop the `elapsed` timing assertion and keep only `assert result2 == result1` (the cache-hit correctness check). If performance regression protection is genuinely desired, gate it behind a `@pytest.mark.slow` benchmark or assert against a generous upper bound (e.g. 1.0 s) that cannot flake on a healthy machine.

---

### TST-004: CLI wiring tests assert mock calls without verifying outcomes

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_app.py, src/mko_telepost/app.py |
| **Classification** | advisory |
| **Validation** | VALIDATED (unchanged) |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Verified against:** `tests/test_app.py:14-18` â€” `test_init_command_calls_init_project`: single assertion `mock_init.assert_called_once()`, no `result.exit_code` check (confirmed). `tests/test_app.py:37-55` â€” `test_run_command_loads_config`: asserts `from_user_dir.assert_called_once()` and `load.assert_called()`, no exit-code, no `mock_posting` assertion, no stdout check (confirmed).
> - **Redundancy:** confirmed. The sibling `test_init_command_success_output` (`tests/test_app.py:27-32`) asserts `result.exit_code == 0` and `"Configuration initialized" in result.stdout` â€” strictly stronger than `test_init_command_calls_init_project`.
> - **Sibling-strength contrast:** confirmed. `test_run_command_dry_run` (`:84-94`) asserts `mock_posting.assert_not_called()`; `test_run_command_non_critical_warnings_do_not_fail` (`:138-153`) asserts `mock_posting.assert_called_once()`. These prove the pattern of adding outcome assertions is already established, so the recommendation aligns with existing patterns rather than introducing a new convention.
> - **ROI:** LOW confirmed. Strengthening or removing the two tests is a small, behavior-preserving change.

**Description:** Two CLI tests verify only that a mock was invoked, with no assertion on the user-visible outcome (exit code, output, or whether the downstream flow actually ran). They give a false sense of coverage: the test passes as long as the function is *called*, regardless of whether the command behaved correctly.

1. `test_init_command_calls_init_project` (`tests/test_app.py:14-18`): the only assertion is `mock_init.assert_called_once()`. It does not check `result.exit_code`, stdout, or that `force` defaulted correctly. The sibling `test_init_command_success_output` already covers the success path *with* outcome assertions, making this test strictly weaker and redundant â€” it would still pass if `init` returned exit code 1.
2. `test_run_command_loads_config` (`tests/test_app.py:37-55`): asserts `mock_reader.from_user_dir.assert_called_once()` and `mock_reader_instance.load.assert_called()`, but never asserts `result.exit_code == 0`, never checks that `run_posting` was actually invoked, and never inspects stdout. A regression where `run` loaded config but then exited non-zero (or silently skipped `_run_posting_flow`) would pass this test.

These are "testing the mock, not the behavior" â€” the audit's Test Anti-Patterns checklist calls out tests that "only call a function without checking the result" / "assert a mock was called but the mock IS the implementation".

**Evidence (verified):**
- `tests/test_app.py:14-18` â€” `test_init_command_calls_init_project`: single assertion `mock_init.assert_called_once()`, no `result.exit_code` check.
- `tests/test_app.py:37-55` â€” `test_run_command_loads_config`: asserts `from_user_dir.assert_called_once()` and `load.assert_called()`; no exit-code, no `mock_posting` assertion, no stdout check. Contrast with the stronger `test_run_command_dry_run` which asserts `mock_posting.assert_not_called()`, and `test_run_command_non_critical_warnings_do_not_fail` which asserts `mock_posting.assert_called_once()`.

**Recommendation:** Apply two separate actions:

1. **Remove** `test_init_command_calls_init_project` from `tests/test_app.py` (lines 14-18). It is redundant — `test_init_command_success_output` covers the same happy path with `assert result.exit_code == 0` and `assert "Configuration initialized" in result.stdout`. The only unique signal ("was `init_project` called?") is already an implicit precondition of `test_init_command_success_output`; if `init_project` stopped being called, that test would fail. Removing this test reduces suite noise without losing coverage.

2. **Strengthen** `test_run_command_loads_config` in `tests/test_app.py` (lines 37-55) by adding outcome assertions. The config-loading path has no stronger sibling test, so removal is not an option. Add the `result` capture, exit-code check, downstream-invocation check, and stdout assertion:

```python
@patch("mko_telepost.app.APP_PATHS")
@patch("mko_telepost.app.TelepostConfigReader")
@patch("mko_telepost.app.run_posting")
def test_run_command_loads_config(self, mock_posting, mock_reader, mock_paths):
    mock_reader_instance = MagicMock()
    mock_reader_instance.load.return_value = MagicMock()
    mock_reader_instance.validate_files.return_value = []
    mock_reader.return_value = mock_reader_instance
    mock_reader.from_user_dir.return_value = mock_reader_instance
    mock_paths.app_config.exists.return_value = True

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert "Configuration loaded" in result.stdout
    mock_reader.from_user_dir.assert_called_once()
    mock_reader_instance.load.assert_called()
    mock_posting.assert_called_once()
```

This follows the existing project pattern (same approach as `test_run_command_dry_run` and `test_run_command_non_critical_warnings_do_not_fail`, which already assert outcomes).

---

### TST-005: Inconsistent method-body indentation in test_image_cache.py

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_image_cache.py |
| **Classification** | advisory |
| **Validation** | VALIDATED (unchanged) |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Verified against:** `tests/test_image_cache.py:101-124` (`test_resize_image_happy_path` body at 12-space indent, e.g. line 102 `            """resize_image should create cached image with correct dimensions."""`), `:126-151` (`test_resize_image_cache_hit`), `:165-180` (`test_resize_image_alpha_outputs_png`) â€” all use 12-space bodies. Compare `:15-20` (`test_init_creates_directory`, 8-space body â€” project standard). Confirmed.
> - **Lint gate:** confirmed. `uv run ruff check tests/test_image_cache.py` â†’ `All checks passed!` (so `ruff check` does not flag it). `uv run ruff format --check tests/test_image_cache.py` â†’ `Would reformat: tests\test_image_cache.py` (1 file would be reformatted) â€” confirms `ruff format` is the tool that normalizes this, and it is not in the configured gate.
> - **Config claim:** confirmed. `pyproject.toml` has `[tool.ruff.format]` at line 127, but `.ai/context/commands.md` lists only `uv run ruff check <path>` (no `ruff format`). AGENTS.md also documents only `uv run ruff check <path>`.
> - **DOC-UPDATE sub-item ~~DONE~~:** `ruff format --check` has been documented in `.ai/context/commands.md`. This accurately reflected the desired workflow â€” code reality (formatter exists and is configured) vs documented workflow (only `check`). Validated as a low-priority DOC-UPDATE rider on this finding, not a separate finding.
> - **ROI:** LOW confirmed. `uv run ruff format tests/test_image_cache.py` is a no-behavior-change normalization; adding `ruff format --check` to the gate is a one-line CI addition. Aligns with project rule on consistent 4-space stepping.

**Description:** `tests/test_image_cache.py` mixes two indentation styles within the same class. Methods `test_init_creates_directory` through `test_cleanup_unused_skips_directories` (lines 15-99) use the project-standard 4-space `def` / 8-space body. But `test_resize_image_happy_path` (line 101), `test_resize_image_cache_hit` (line 126), and `test_resize_image_alpha_outputs_png` (line 165) use 4-space `def` with a **12-space body** â€” an extra 4-space indent on every line of the method body.

`ruff check` does not flag this because the indentation is still a multiple of 4 and internally consistent per-block, so it is valid Python and passes the configured lint gate. However, the project's own rules (AGENTS.md / `.kilo/rules/project.md`) mandate consistent 4-space stepping, and `ruff format` (which is *not* part of the configured gate â€” only `ruff check` is) would normalize it. The inconsistency hurts readability and signals that the formatter is not applied to the test tree.

**Evidence (verified):**
- `tests/test_image_cache.py:101-124` â€” `test_resize_image_happy_path` body indented 12 spaces (e.g. line 102 `            """resize_image should create cached image with correct dimensions."""`).
- `tests/test_image_cache.py:15-20` â€” `test_init_creates_directory` body indented 8 spaces (project standard) for comparison.
- `pyproject.toml:127-130` â€” `[tool.ruff.format]` is configured but `ruff format` is not in the documented command set (`uv run ruff check <path>` per AGENTS.md).
- Tooling: `uv run ruff check tests/test_image_cache.py` â†’ `All checks passed!`; `uv run ruff format --check tests/test_image_cache.py` â†’ `Would reformat`.

**Recommendation:** Run `uv run ruff format tests/test_image_cache.py` (or manually reindent the three affected methods to 8-space bodies) and add `ruff format --check` to the CI/lint gate so future indentation drift is caught. [DOC-UPDATE ~~DONE~~] `ruff format --check` documented in `.ai/context/commands.md`.

---

## Cross-Finding Analysis

### Same-root-cause assessment

No merge candidates. TST-001 and TST-002 both touch `tests/test_gsheets_reader.py` and the `GSheetsReader` OAuth2 lifecycle, but their root causes are distinct:

- **TST-001** â€” a *specific existing test* (`test_get_sheet_data_returns_empty_when_service_not_initialized`) fails to mock `_initialize_service`, coupling it to host filesystem/network state. Defect class: test isolation.
- **TST-002** â€” *missing tests* for the refresh-success / load-valid / save-write+permissions branches. Defect class: coverage gap.

Fixing TST-001 does not close TST-002's coverage gap, and adding TST-002's positive-path tests does not make `test_get_sheet_data_returns_empty_when_service_not_initialized` hermetic. They remain separate findings.

### Cross-phase conflicts

No cross-phase conflicts identified. This validation is scoped to Phase 07 only; no other phase findings contradict the Runtime Verification Summary ("suite green, 224 passed") recorded here.

### Dependency chains

One weak dependency (informational, not blocking):

- TST-001 fix and TST-002 fix both modify `tests/test_gsheets_reader.py`. If implemented in parallel branches, the only conflict surface is test-file edit locality â€” they edit different test functions. No logical dependency. TST-001 does not need TST-002 to be applied first, and vice versa.

## Rollout Analysis

### Risks

- **TST-001 (HIGH):** test-only change, no production code touched. Both proposed fixes are hermetic (verified). No rollback risk beyond reverting the test edit. The *deferral* risk is the real concern â€” leaving it as-is means any contributor who runs `mko-telepost init` will have a suite that hangs or makes live API calls.
- **TST-002 (MEDIUM):** additive tests only. No existing behavior change. New tests must use `MagicMock(spec=OAuth2Credentials)` and `tmp_path` per the recommendation to stay hermetic (otherwise they risk reintroducing a TST-001-style isolation defect).
- **TST-003 / TST-004 (LOW):** test-only edits, behavior-preserving. TST-004's "remove the redundant test" option reduces suite size; the "strengthen" option keeps size constant. Either is safe.
- **TST-005 (LOW):** `ruff format` is a no-behavior-change normalization on a single test file. Adding `ruff format --check` to the gate is a one-line CI addition; risk is that pre-existing unformatted files in other directories would then fail the gate â€” recommend scoping the new gate step or running `ruff format` repo-wide once before enabling `--check`.

### Sequencing

Suggested order (non-blocking advisory):

1. **TST-001** first â€” HIGH severity isolation defect; smallest, highest-value fix; unblocks safe local suite runs for any contributor with real credentials.
2. **TST-005** â€” trivial formatter pass; independent of the others.
3. **TST-002, TST-003, TST-004** â€” advisory improvements; can be done in any order.

No circular dependencies, no unsafe ordering, no fragile insertion points. All fixes target test files only; no production code, no migrations, no config schema changes.

## Execution Validation

All recommendations are test-tree-only edits with no production-code impact:

- **Targets confirmed present:** every referenced file, function, line range, and code branch was verified to exist as described (see per-finding Validation Notes).
- **Plan is not stale:** the codebase matches the auditor's evidence at every cited line.
- **Dependencies remain valid:** no production-code refactor pending that would invalidate the test edits.
- **Architecture integrity preserved:** no layer boundaries crossed; no new abstraction introduced; recommendations reuse existing test patterns (`MagicMock(spec=...)`, `tmp_path`, `CliRunner`, `caplog`).
- **Task applicability:** all five findings apply to the current state of `main`.

## Warnings

- **Rollout risk (TST-005 gate expansion):** adding `ruff format --check` to the lint gate without first running `ruff format` across the whole repo may surface pre-existing formatting drift in other directories. Run `uv run ruff format .` once before enabling `--check` in CI.
- **Documentation inconsistency:** `.ai/context/commands.md` and `AGENTS.md` document only `uv run ruff check <path>` while `pyproject.toml` configures `[tool.ruff.format]`. The formatter is configured but not invoked by the documented workflow â€” this is the TST-005 DOC-UPDATE rider.
- **Test-isolation hygiene (TST-002 follow-on):** new positive-path tests for `_save_token` / `_try_refresh_token` must use `tmp_path` and `MagicMock(spec=OAuth2Credentials)` to avoid reintroducing the host-state coupling described in TST-001.

## Required Fixes

- **TST-001** â€” `test_get_sheet_data_returns_empty_when_service_not_initialized` is non-hermetic: it can hang (browser OAuth) or make real Google Sheets API calls when a developer has real credentials in the user config dir. Patch `_initialize_service` or use `tmp_path`-absolute credential paths.

## Advisory Recommendations

- **TST-002** â€” Add positive-path tests for `_try_refresh_token` (success), `_try_load_token` (valid token), and `_save_token` (real write + `set_restrictive_permissions`); the security-relevant token-file permissioning is currently never exercised.
- **TST-003** â€” Remove the `elapsed < 0.1` wall-clock assertion in `test_resize_image_cache_hit`; keep the correctness assertion `result2 == result1`.
- **TST-004** â€” Strengthen or remove the mock-call-only CLI tests (`test_init_command_calls_init_project`, `test_run_command_loads_config`) by adding exit-code / downstream-invocation / stdout assertions.
- **TST-005** â€” Normalize indentation in `tests/test_image_cache.py` and add `ruff format --check` to the lint gate.

## Doc Updates Needed

- **TST-005** (optional) â€” Document `ruff format --check` in `.ai/context/commands.md` as part of the standard lint workflow so formatter drift is prevented going forward.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|--------|
| Validated (unchanged) | 5 | TST-001, TST-002, TST-003, TST-004, TST-005 |
| Reclassified | 0 | â€” |
| Merged | 0 | â€” |
| Rejected | 0 | â€” |
| Cross-phase conflicts added | 0 | â€” |
| Rollout safety issues added | 0 | â€” |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| â€” | â€” | No rejections. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| â€” | â€” | No merges. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|----------|
| â€” | â€” | â€” | No reclassifications. |

### Notes

- TST-001 is the only mandatory (HIGH) fix. TST-002 through TST-005 are advisory but TST-002's `_save_token` / `set_restrictive_permissions` gap is security-adjacent and should not be deferred indefinitely.
- All findings are test-tree-only; no production code changes are required to close any of them.
