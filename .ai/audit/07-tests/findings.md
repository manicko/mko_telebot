# Phase 07 Audit Findings — Test Quality

**Executor:** audit-executor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### TST-001: Property test asserts wrong invariant for exclusion queries (false-sense-of-security)

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `tests/test_parser.py`, `src/mko_telebot/core/matcher.py` |
| **Classification** | mandatory |

**Description:** `test_property_no_crash_generated` (tests/test_parser.py:592-629) fails on every run. The test's final assertion block assumes that for any exclusion-only query, `matcher("xyz", query) is True` because "exclusions don't trigger, and there are no inclusions to fail". This invariant is correct in prose, but the chosen exemplar text `"xyz"` is NOT non-matching for an exclusion like `-X*`:

- `search_match('xyz', '"-X*"')` returns `False` — and this is CORRECT production behavior: the `X*` wildcard exclusion matches `xyz` (word-boundary `X` + `[^\s]*` matches `yz`), so the message is rightfully excluded.
- The test asserts `True`, but the production function correctly returns `False`. This is a **test bug**, not a production bug (verified via standalone reproduction).

Because the test fails 100% of the time (deterministic, confirmed across two consecutive full-suite runs), it breaks CI and, worse, the suite is currently red. The property test's intent ("exclusion-only queries should return True for genuinely non-matching text") is never actually verified with a text that does not contain the excluded pattern.

**Evidence:**
```
$ uv run pytest -q
FAILED tests/test_parser.py::test_property_no_crash_generated - assert False is True
1 failed, 372 passed in 8.65s

# Standalone reproduction:
search_match('xyz', '"-X*"') -> False   # CORRECT: xyz matches exclusion X*
search_match('abc', '"-X*"') -> True    # the invariant only holds for genuinely non-matching text
```
tests/test_parser.py:626-629:
```python
# Invariant: exclusion-only queries should return True for non-matching text
if query_content.startswith("-"):
    assert matcher("xyz", query) is True
```
The falsifying example: `query='"-X*"'`, `text=''` (hypothesis param), assertion calls `matcher('xyz', '"-X*"')` → `False`.

**Recommendation:** Fix the test so the exemplar text genuinely does not satisfy the exclusion. Use a fixed, known-non-matching literal (e.g. `assert matcher("abc", query) is True`) or, better, generate text that provably avoids the exclusion pattern. The production code in `matcher.py` (`evaluate_query`, lines 124-139) is correct and must NOT be changed to make this test pass. Restoring a green suite is mandatory before this audit phase can be considered complete.

---

### TST-002: `_fetch_messages` RPCError → TelegramServiceError path is uncovered

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py`, `tests/test_monitor_forward.py` |
| **Classification** | advisory |

**Description:** In `process_task`, the message-fetch step is delegated to `_fetch_messages` (monitor_forward.py:218-260). Coverage report shows lines 251-256 (the `except RPCError` branch that wraps the error in `TelegramServiceError` and re-raises) are never exercised. The two existing error tests (`test_handles_flood_wait_error`, `test_handles_worker_busy_error`) only cover the non-raising branches (which sleep and return `[]`). The branch that converts a transient/permanent RPC error during fetching into a `TelegramServiceError` — the path a real `process_task` caller depends on to reschedule the channel — has zero coverage.

**Evidence:** `uv run pytest --cov=mko_telebot --cov-report=term-missing`:
```
src\mko_telebot\monitor_forward.py    117    7    94%   190, 251-256, 268-269
```
Lines 251-256 are the `except RPCError ... raise TelegramServiceError(...)` block in `_fetch_messages`. No test in `tests/test_monitor_forward.py` triggers it (the fetch-error tests use `FloodWaitError`/`WorkerBusyTooLongRetryError`, not `RPCError`).

**Recommendation:** Add a test that makes `client.iter_messages` raise a generic `RPCError` (e.g. `ServerError`) and asserts `process_task` propagates/converts it to `TelegramServiceError`. This guards the reschedule-on-fetch-failure path used by `process_and_reschedule` (already tested for `TelegramServiceError`), keeping the fetch and orchestration layers consistent.

---

### TST-003: `build_sender_tag` broad-exception branch is uncovered

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_client.py`, `tests/test_monitor.py` |
| **Classification** | advisory |

**Description:** `build_sender_tag` (monitor_client.py:138-160) has an `except (OSError, ConnectionError, TimeoutError)` fallback that returns `""`. Coverage shows lines 157-160 are uncovered. The existing tests cover only the `RPCError` branch (`test_returns_empty_on_rpc_error`) and the `None`-sender branch. The `OSError`/`ConnectionError`/`TimeoutError` fallback — relevant when `get_sender` raises a transport-level error rather than a Telethon `RPCError` — is untested, so a regression that lets such an error propagate instead of returning `""` would go unnoticed.

**Evidence:**
```
src\mko_telebot\monitor_client.py       58    3    95%   157-160
```
tests/test_monitor.py `TestBuildSenderTag` only parametrizes `RPCError` and `None` sender.

**Recommendation:** Add one test where `msg.get_sender` raises `ConnectionError` (or `OSError`/`TimeoutError`) and assert `build_sender_tag` returns `""`. Cheap to add and closes a real exception-handling gap.

---

### TST-004: `main.py` entry point has zero test coverage

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/main.py` |
| **Classification** | advisory |

**Description:** `main.py` (the console-script entry point that calls `cli.app()`) is at 0% coverage (5/5 statements missed). While thin, it is the actual process entry invoked by the installed `mko-telebot` command; nothing verifies it imports and dispatches correctly. A broken import or signature change in `cli.app` would not be caught here.

**Evidence:**
```
src\mko_telebot\main.py    5    5     0%   3-12
```

**Recommendation:** Add a trivial smoke test that imports `mko_telebot.main` and asserts `main` is callable (optionally invoke it under `CliRunner` is overkill — import + callable check is enough). Keeps the shipping entry point guarded against accidental breakage.

---

### TST-005: `process_task` tests mock `process_messages` wholesale, masking fetch+forward integration

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `tests/test_monitor_forward.py`, `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** Every `TestProcessTask` test patches `mko_telebot.monitor_forward.process_messages` with an `AsyncMock` and then asserts only `mock_process.assert_awaited_once()` (plus arg count). This verifies the wiring of `process_task` → `process_messages` but exercises none of the real fetch/forward contract end-to-end. It is acceptable as a unit test of `process_task`, but the integration between `_fetch_messages` and `process_messages` (filtering `msg.id <= last_msg_id`, updating `last_msg_id`, album grouping through forwarding) is only partially covered by separate tests. Notably, the real `process_messages` forward side is well covered in `test_monitor.py`; the gap is that no test asserts `process_task` correctly passes the *filtered* new messages into the real `process_messages`.

**Evidence:** tests/test_monitor_forward.py:55-176 — `test_fetches_messages_and_processes_matches`, `test_updates_last_msg_id_after_processing`, `test_handles_flood_wait_error`, `test_handles_worker_busy_error`, `test_skips_already_processed_messages`, `test_handles_empty_message_list` all use `patch("mko_telebot.monitor_forward.process_messages", new_callable=AsyncMock)` and assert only on the mock.

**Recommendation:** Keep the mocked wiring tests, but add at least one test that uses the REAL `process_messages` (with `send_message`/`send_file` mocked at the client boundary, as `test_monitor.py` already does) so that `process_task` → `_fetch_messages` → real `process_messages` → real `forward_to_users` is exercised as one path. This catches contract drift between the two functions without a network call.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 3 |

## Mandatory Fixes

- **TST-001** — Fix the failing exclusion-query property test (`tests/test_parser.py:626-629`). The assertion uses `xyz` as a "non-matching" exemplar, but `xyz` matches the `X*` exclusion, so the production function correctly returns `False`. The test is wrong, not the code. Must be corrected to restore a green suite; do NOT alter `matcher.evaluate_query` to force the test green.

## Advisory Recommendations

- **TST-002** — Cover `_fetch_messages` RPCError → `TelegramServiceError` branch (monitor_forward.py:251-256).
- **TST-003** — Cover `build_sender_tag` `(OSError, ConnectionError, TimeoutError)` fallback (monitor_client.py:157-160).
- **TST-004** — Add a smoke test for the `main.py` console-script entry point (0% coverage).
- **TST-005** — Add one integration test exercising real `process_messages` through `process_task` rather than mocking it wholesale.

## Doc Updates Needed

None.
