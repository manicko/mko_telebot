## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 4 |

## Mandatory Fixes

None. All findings are advisory-level test coverage improvements.

---

## Advisory Recommendations

- **TST-002:** Add a test that makes `client.iter_messages` raise a generic `RPCError` (e.g., `ServerError`) and asserts `process_task` propagates/converts it to `TelegramServiceError`.
- **TST-003:** Add one test where `msg.get_sender` raises `ConnectionError` (or `OSError`/`TimeoutError`) and assert `build_sender_tag` returns `""`.
- **TST-004:** Add a trivial smoke test that imports `mko_telebot.main` and asserts `main` is callable.
- **TST-005:** Add at least one test using the real `process_messages` (with `send_message`/`send_file` mocked at client boundary) so that `process_task` → `_fetch_messages` → real `process_messages` → real `forward_to_users` is exercised as one path.

---

## Runtime Verification Log

- **R1 — TST-001 failure:** `uv run pytest` confirms `test_property_no_crash_generated` fails at line 629 with `search_match("xyz", "-X*")` returning `False`. This is correct production behavior — `X*` matches words starting with `X` (case-insensitive `IGNORECASE` flag), and `xyz` starts with `x` which matches under `IGNORECASE`.
- **R2 — Exclusion pattern behavior:** Verified `search_match('xyz', '"-X*"')` → `False` (correct: xyz matches X* exclusion), `search_match('abc', '"-X*"')` → `True` (abc does not match X* under case-insensitive matching).
- **R3 — Coverage gaps:** `uv run pytest --cov=mko_telebot --cov-report=term-missing` confirms:
  - `main.py`: 0% coverage (lines 3-12) — TST-004 validated
  - `monitor_client.py:157-160`: OSError/ConnectionError/TimeoutError fallback uncovered — TST-003 validated
  - `monitor_forward.py:251-256`: RPCError → TelegramServiceError path uncovered — TST-002 validated
- **R4 — Test mocking pattern:** Confirmed all `TestProcessTask` tests in `test_monitor_forward.py` patch `process_messages` with `AsyncMock` and assert only on the mock, not integration with real `process_messages`.
- **R5 — Cross-phase overlap:** TST-001 describes the same exclusion-wildcard property test failure as DF-004 (phase 06). Both findings agree the test is wrong, not the production code.

---

## Findings Validation

### TST-001: Property test asserts wrong invariant for exclusion queries (false-sense-of-security)

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | HIGH |
| **Type** | ~~RUNTIME-ERROR~~ (merged) |
| **Status** | **MERGED** |

**Evidence:**
- `tests/test_parser.py:626-629` — assertion `assert matcher("xyz", query) is True` inside `if query_content.startswith("-")` block.
- `matcher.py:106` — `_check_patterns_match` uses `re.IGNORECASE | re.UNICODE`.
- `matcher.py:39-44` — Wildcard pattern generates regex with word boundaries and `[^\s]*`.
- Runtime: `search_match('xyz', '"-X*"')` → `False` (xyz starts with x, matches X* under IGNORECASE).
- The invariant "exclusion-only queries should return True for non-matching text" is over-broad; `xyz` **does** match `X*` under case-insensitive matching.

> **Validation Note:**
> - **Action:** Merged into DF-004 (phase 06)
> - **Detail:** This finding duplicates DF-004. Both describe the same failing property test. DF-004 provides more complete analysis including the IGNORECASE regex flag behavior. TST-001 is absorbed into DF-004.
> - **See also:** DF-004 (phase 06)

---

### TST-002: `_fetch_messages` RPCError → TelegramServiceError path is uncovered

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Status** | **VALIDATED** |

**Evidence:**
- `monitor_forward.py:251-256` — `except RPCError ... raise TelegramServiceError(...)` block.
- Coverage report: `src\mko_telebot\monitor_forward.py    117    7    94%   190, 251-256, 268-269`.
- Existing error tests (`test_handles_flood_wait_error`, `test_handles_worker_busy_error`) only cover the non-raising branches (`FloodWaitError`, `WorkerBusyTooLongRetryError`).

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Coverage confirms lines 251-256 are never exercised. The test suite covers `FloodWaitError` and `WorkerBusyTooLongRetryError` paths which return `[]`, but not the generic `RPCError` path which raises `TelegramServiceError`. This is a genuine coverage gap.
> - **See also:** INT-001 (phase 05) for related RPCError handling concerns

---

### TST-003: `build_sender_tag` broad-exception branch is uncovered

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Status** | **VALIDATED** |

**Evidence:**
- `monitor_client.py:157-160` — `except (OSError, ConnectionError, TimeoutError) as e: return ""` fallback.
- Coverage report: `src\mko_telebot\monitor_client.py       58    3    95%   157-160`.
- `test_monitor.py` `TestBuildSenderTag` only tests `RPCError` branch (`test_returns_empty_on_rpc_error`) and `None` sender.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Coverage confirms lines 157-160 are never exercised. Existing tests cover `RPCError` branch and `None` sender, but not transport-level errors. This is a real exception-handling gap.
> - **See also:** INT-005 (phase 05) for related transient error handling concerns

---

### TST-004: `main.py` entry point has zero test coverage

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Status** | **VALIDATED** |

**Evidence:**
- Coverage report: `src\mko_telebot\main.py    5    5     0%   3-12`.
- `pyproject.toml:167` — `mko-telebot = "mko_telebot.cli:app"` defines the console-script entry point.
- `main.py` (lines 1-12) is the actual process entry invoked by the installed `mko-telebot` command.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Coverage confirms 0% coverage (5/5 statements missed) for `main.py`. While the entry point is thin (calls `cli.app()`), it is invoked by the installed `mko-telebot` command. A broken import would not be caught. This is a valid smoke-test gap.

---

### TST-005: `process_task` tests mock `process_messages` wholesale, masking integration

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Status** | **VALIDATED** |

**Evidence:**
- `test_monitor_forward.py:55-176` — every `TestProcessTask` test uses `patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock)` and asserts only on the mock.
- `test_monitor_forward.py:80, 98, 117, 135, 158, 171` — all assertions check mock calls, not real integration.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Confirmed: all `TestProcessTask` tests use mocked `process_messages`. No test exercises the real `process_messages` path. This is a legitimate integration testing gap.

---

## Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| TST-001 | DF-004 (Phase 06) | Same root cause: the property test's exclusion-only invariant is incorrect for case-insensitive wildcard patterns. DF-004 provides more context including the IGNORECASE regex flag behavior. |

---

## Cross-Phase Conflicts

None detected. TST-002 links to INT-001 (phase 05) as related, not conflicting. Both describe different aspects of RPCError handling in different modules.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 4 | TST-002, TST-003, TST-004, TST-005 |
| Reclassified | 0 | — |
| Merged | 1 | TST-001 → DF-004 |
| Rejected | 0 | — |

### Rejected Findings

None.