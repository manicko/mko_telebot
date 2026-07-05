# Phase 07 Audit Findings â€” Test Quality

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

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

**Description:** `test_get_sheet_data_returns_empty_when_service_not_initialized` constructs a `GSheetsReader` with a *relative* `credentials_file=Path("credentials.json")` and does **not** patch `_initialize_service`, `_get_credentials`, `_authorize_new_token`, or `APP_PATHS`. The reader resolves the relative path against the real `APP_PATHS.user_dir` (`~/.config/mko_telepost/` on Linux, `%APPDATA%/mko_telepost/` on Windows).

When `get_sheet_data` is called, `service is None` triggers `_initialize_service()` â†’ `_get_credentials()` â†’ `_try_load_token()` (checks the *real* `~/.config/mko_telepost/token.json`) â†’ if missing, `_authorize_new_token()` calls `InstalledAppFlow.from_client_secrets_file(...)` on the *real* `~/.config/mko_telepost/credentials.json`.

The test only passes today because the developer machine has neither a real `token.json` nor `credentials.json` in the user config dir. On any machine where `mko-telepost init` has been run and real credentials placed:

1. If a **valid `token.json`** exists â†’ `_get_credentials` returns live creds â†’ `build("sheets","v4", credentials=...)` is called â†’ the test makes a **real Google Sheets API call** (network I/O in a unit test, and a flaky test that depends on the sheet's contents).
2. If only **`credentials.json`** exists (no valid token) â†’ `flow.run_local_server(port=0)` **opens a browser window and blocks indefinitely**, hanging the entire suite.

This is a test-isolation defect that couples a unit test to host filesystem/network state.

**Evidence:**
- `tests/test_gsheets_reader.py:158-170` â€” `test_get_sheet_data_returns_empty_when_service_not_initialized`: no `@patch` for `_initialize_service`/`_get_credentials`/`APP_PATHS`; `config = GoogleSheetsConfig(spreadsheet_id=..., credentials_file=Path("credentials.json"))`.
- `src/mko_telepost/core/gsheets_reader.py:79-82` â€” `self.credentials_file = credentials_file or self._resolve_path(self._credentials_file)` (relative path resolved against `APP_PATHS.user_dir`).
- `src/mko_telepost/core/gsheets_reader.py:235-240` â€” `if self.service is None: self.service = self._initialize_service()`; raises only when `_initialize_service()` returns `None`.
- `src/mko_telepost/core/gsheets_reader.py:184-199` â€” `_authorize_new_token` calls `flow.run_local_server(port=0)` (blocking, opens browser) when a credentials file is present.

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

**Description:** The OAuth2 credential lifecycle in `GSheetsReader` has several branches with **no positive-path coverage**. A grep across `tests/` shows `_try_refresh_token`, `_try_load_token`, `_initialize_service`, and the literal `"Token refreshed successfully"` log never appear in any test. `_save_token` appears exactly once â€” and only as a `patch.object(GSheetsReader, "_save_token")` that **mocks it out** (`tests/test_gsheets_reader.py:286-289`).

Specific untested branches in `src/mko_telepost/core/gsheets_reader.py`:

1. `_try_refresh_token` **success** path (lines 153-159): `creds.refresh(Request())` succeeds â†’ returns refreshed creds â†’ logs "Token refreshed successfully". Only the *failure* path is covered by `test_get_credentials_refresh_failure_falls_back_to_auth`. A regression that drops the `return creds` on success (e.g. returning `None` and forcing a needless re-auth every run) would not be caught.
2. `_try_load_token` **valid token, scopes match** path (lines 127-141): only the not-exists and scope-mismatch paths are tested. The happy path that returns a usable `Credentials` object directly is untested.
3. `_save_token` **actual write + permissions** path (lines 201-213): in the only test that reaches `_get_credentials` with a successful outcome (`test_get_credentials_mismatched_scopes_deletes_token`), `_save_token` is patched out. Therefore `token_file.write(creds.to_json())` and the security-relevant `set_restrictive_permissions(self.token_file)` call are **never executed by any test**. A bug that silently skips setting restrictive permissions on the token file (which contains live OAuth refresh tokens) would go undetected.

**Evidence:**
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

**Description:** `test_resize_image_cache_hit` asserts a wall-clock performance budget: `assert elapsed < 0.1, "Cache hit should return quickly without image processing"` (`tests/test_image_cache.py:143-151`). This is a non-deterministic, environment-dependent assertion. On a loaded CI runner, Windows defender scanning the cache file, or a container with throttled CPU, a cache-hit `stat` + hash lookup can exceed 100 ms even though the logic is correct. Such a failure would be a flake, not a real regression, and flaky tests erode trust in the suite (developers start re-running instead of investigating).

The test already verifies the *correct* outcome one line above: `assert result2 == result1`. The timing assertion adds no correctness signal — it only documents "cache hit is fast", which is a performance characteristic better left to a benchmark or omitted.

**Evidence:**
- `tests/test_image_cache.py:143-151` — `start_time = time.time()` ... `elapsed = time.time() - start_time` ... `assert elapsed < 0.1`.

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

**Description:** Two CLI tests verify only that a mock was invoked, with no assertion on the user-visible outcome (exit code, output, or whether the downstream flow actually ran). They give a false sense of coverage: the test passes as long as the function is *called*, regardless of whether the command behaved correctly.

1. `test_init_command_calls_init_project` (`tests/test_app.py:14-18`): the only assertion is `mock_init.assert_called_once()`. It does not check `result.exit_code`, stdout, or that `force` defaulted correctly. The sibling `test_init_command_success_output` already covers the success path *with* outcome assertions, making this test strictly weaker and redundant — it would still pass if `init` returned exit code 1.
2. `test_run_command_loads_config` (`tests/test_app.py:37-55`): asserts `mock_reader.from_user_dir.assert_called_once()` and `mock_reader_instance.load.assert_called()`, but never asserts `result.exit_code == 0`, never checks that `run_posting` was actually invoked, and never inspects stdout. A regression where `run` loaded config but then exited non-zero (or silently skipped `_run_posting_flow`) would pass this test.

These are "testing the mock, not the behavior" — the audit's Test Anti-Patterns checklist calls out tests that "only call a function without checking the result" / "assert a mock was called but the mock IS the implementation".

**Evidence:**
- `tests/test_app.py:14-18` — `test_init_command_calls_init_project`: single assertion `mock_init.assert_called_once()`, no `result.exit_code` check.
- `tests/test_app.py:37-55` — `test_run_command_loads_config`: asserts `from_user_dir.assert_called_once()` and `load.assert_called()`; no exit-code, no `mock_posting` assertion, no stdout check. Contrast with the stronger `test_run_command_dry_run` which asserts `mock_posting.assert_not_called()`, and `test_run_command_non_critical_warnings_do_not_fail` which asserts `mock_posting.assert_called_once()`.

**Recommendation:** Either strengthen these tests with outcome assertions (`assert result.exit_code == 0`, `mock_posting.assert_called_once()`, check stdout for "Configuration loaded") so they fail on real regressions, or remove the redundant `test_init_command_calls_init_project` in favor of `test_init_command_success_output` which already covers the same path meaningfully.

---

### TST-005: Inconsistent method-body indentation in test_image_cache.py

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_image_cache.py |
| **Classification** | advisory |

**Description:** `tests/test_image_cache.py` mixes two indentation styles within the same class. Methods `test_init_creates_directory` through `test_cleanup_unused_skips_directories` (lines 15-99) use the project-standard 4-space `def` / 8-space body. But `test_resize_image_happy_path` (line 101), `test_resize_image_cache_hit` (line 126), and `test_resize_image_alpha_outputs_png` (line 165) use 4-space `def` with a **12-space body** — an extra 4-space indent on every line of the method body.

`ruff check` does not flag this because the indentation is still a multiple of 4 and internally consistent per-block, so it is valid Python and passes the configured lint gate. However, the project's own rules (AGENTS.md / `.kilo/rules/project.md`) mandate consistent 4-space stepping, and `ruff format` (which is *not* part of the configured gate — only `ruff check` is) would normalize it. The inconsistency hurts readability and signals that the formatter is not applied to the test tree.

**Evidence:**
- `tests/test_image_cache.py:101-124` — `test_resize_image_happy_path` body indented 12 spaces (e.g. line 102 `            """resize_image should create cached image with correct dimensions."""`).
- `tests/test_image_cache.py:15-20` — `test_init_creates_directory` body indented 8 spaces (project standard) for comparison.
- `pyproject.toml:127-130` — `[tool.ruff.format]` is configured but `ruff format` is not in the documented command set (`uv run ruff check <path>` per AGENTS.md).

**Recommendation:** Run `uv run ruff format tests/test_image_cache.py` (or manually reindent the three affected methods to 8-space bodies) and add `ruff format --check` to the CI/lint gate so future indentation drift is caught. [DOC-UPDATE] optionally: document `ruff format --check` alongside `ruff check` in `.ai/context/commands.md` so the formatter is part of the standard workflow.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 3 |

## Mandatory Fixes

- **TST-001** — `test_get_sheet_data_returns_empty_when_service_not_initialized` is non-hermetic: it can hang (browser OAuth) or make real Google Sheets API calls when a developer has real credentials in the user config dir. Patch `_initialize_service` or use `tmp_path`-absolute credential paths.

## Advisory Recommendations

- **TST-002** — Add positive-path tests for `_try_refresh_token` (success), `_try_load_token` (valid token), and `_save_token` (real write + `set_restrictive_permissions`); the security-relevant token-file permissioning is currently never exercised.
- **TST-003** — Remove the `elapsed < 0.1` wall-clock assertion in `test_resize_image_cache_hit`; keep the correctness assertion `result2 == result1`.
- **TST-004** — Strengthen or remove the mock-call-only CLI tests (`test_init_command_calls_init_project`, `test_run_command_loads_config`) by adding exit-code / downstream-invocation / stdout assertions.
- **TST-005** — Normalize indentation in `tests/test_image_cache.py` and add `ruff format --check` to the lint gate.

## Doc Updates Needed

- **TST-005** (optional) — Document `ruff format --check` in `.ai/context/commands.md` as part of the standard lint workflow so formatter drift is prevented going forward.
