---
name: 06-data-flow-validated-findings
description: Validated audit findings — Data Flow & State Management
agent: validator
alwaysApply: false
---

# Phase 06 Validated Findings — Data Flow & State Management

**Validator:** validator  
**Source:** `.ai/audit/06-data-flow/findings.md`  
**Status:** validated

---

## Runtime Verification Log

- **R1 — RPCError handling in `_send_with_retry`:** `monitor_forward.py:125-131` confirmed to catch `RPCError` and re-raise the **bare telethon error**, not wrapped in `TelegramServiceError`.
- **R2 — Exception handling in `process_and_reschedule`:** `monitor.py:57-66` confirmed that `await process_task(...)` precedes `await task.save_state()` inside `async with lock`, and `except TelegramServiceError` (line 68) does NOT catch raw `RPCError`.
- **R3 — Multi-entity target resolution:** `task.py:151-153` confirmed to silently `continue` on list result without logging or error.
- **R4 — Channel-entity resolution contrast:** `task.py:205-211` confirmed to raise `TelegramServiceError` on list result, proving inconsistency.
- **R5 — Fire-and-forget task creation:** `monitor.py:131` confirmed that `asyncio.create_task(...)` returns a handle that is discarded.
- **R6 — Reschedule sleep ordering:** `monitor.py:28-35` confirmed queue.put happens only after sleep, risking cancelled channel loss.
- **R7 — CLI interrupt handling:** `cli.py:121-123` confirmed to raise `typer.Exit(code=130)` on `KeyboardInterrupt`.
- **R8 — Wildcard case-insensitivity:** Runtime verified `search_match('xyz', '-X*')` → `False` (xyz starts with x, matches X* under IGNORECASE), `search_match('abc', '-X*')` → `True` (abc does not start with x). Test invariant is incorrect.
- **R9 — `run_monitor` shutdown:** `monitor.py:150` confirmed to call `client.disconnect()` without awaiting it.

---

## Findings

### DF-001: Permanent RPCError during forwarding escapes all error handlers and skips state persistence (duplicate re-dispatch + crashed worker)

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | CRITICAL |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py`, `src/mko_telebot/monitor.py`, `src/mko_telebot/core/task.py` |
| **Classification** | mandatory |

**Description:** A single permanent Telegram RPC error while forwarding to one target corrupts the entire per-channel data-flow contract: the `last_msg_id` state is never persisted, so the next cycle re-fetches and re-forwards the whole overlap window (duplicate dispatch), and the worker task dies with an unhandled exception.

The flow breaks at three stacked hops:
1. `_send_with_retry` (`monitor_forward.py:125-131`) catches `RPCError` and does a raw `raise` — re-raising the **bare `telethon.errors.RPCError`**, not a `MkoTelebotError` subclass.
2. `process_messages` → `process_task` (`monitor_forward.py:263-280`) lets this exception bubble up to `process_and_reschedule` (`monitor.py:40-73`).
3. In `process_and_reschedule`, `await process_task(...)` is inside `async with lock:` (line 58-59). A permanent `RPCError` is **not** a `TelegramServiceError`, so the `except TelegramServiceError` (line 68) does not catch it. Execution leaves the `async with lock` block **before** `await task.save_state()` (line 62) is ever reached.

Because `process_and_reschedule` is launched as a fire-and-forget `asyncio.create_task` (`monitor.py:131`), the unhandled `RPCError` becomes an uncaught exception on that task (worker dies), while the `finally` (line 72) still re-queues the task. On the next pass `task.last_msg_id` was never written to disk, so every message in the window is re-fetched and re-forwarded → **duplicate alerts to users**.

**Evidence Verified:**
- `monitor_forward.py:125-131` — `except RPCError as e: ... raise` re-raises raw `RPCError` (telethon, not `MkoTelebotError`).
- `monitor.py:57-66` — `await process_task(...)` precedes `await task.save_state()` inside `async with lock`; the `except` only matches `TelegramServiceError`.
- `monitor.py:73` — `finally: asyncio.create_task(reschedule_task(task, queue))` re-queues even though `save_state()` was skipped.
- `core/task.py:355-379` — `save_state()` writes `{"last_id": self.last_msg_id}`; never reached on this path.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** The exception handling gap is real. Permanent RPC errors (e.g., `ChatWriteForbiddenError`, `UserIsBlockedError`) during message forwarding are not wrapped in `TelegramServiceError`, causing them to escape the `except TelegramServiceError` block in `process_and_reschedule`. This results in state not being persisted and the task being requeued with stale state, causing duplicate forwards. The fire-and-forget pattern compounds the issue.
> - **See also:** INT-001 (phase 05) describes the same issue; INT-001 is effectively the same finding.

**Recommendation:** Make `_send_with_retry` wrap the raised `RPCError` in a `TelegramServiceError`. Ensure `process_and_reschedule` attempts `save_state()` even on non-`TelegramServiceError` exceptions. Priority: mandatory.

---

### DF-002: Forward targets that resolve to multiple entities are silently dropped (undetected missed forwards)

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/task.py`, `src/mko_telebot/monitor_forward.py` |
| **Classification** | mandatory |

**Description:** When a configured forward target (`forward_to` entry) resolves via `client.get_entity` to a **list** instead of a single Entity, that target is dropped with no log, no error, and no state impact. Downstream, `forward_to_users` (`monitor_forward.py:149`) iterates `task.forward_to_entities`; the dropped target is simply never in that list, so the message is **never forwarded to it** — a silent data-loss / missed-forward with zero operator visibility.

`resolve_targets_entities` (`task.py:145-155`) contains the defect:
```python
result = await client.get_entity(ent)
if isinstance(result, list):
    continue   # <- no logger.*, no raise, nothing
entities.append(result)
```

**Evidence Verified:**
- `core/task.py:151-153` — `if isinstance(result, list): continue` with no logging or error.
- `core/task.py:205-211` — contrast: the channel-entity path *does* raise `TelegramServiceError` on a list result.
- `monitor_forward.py:149` — `for target in task.forward_to_entities:` iterates only what survived resolution.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** The inconsistency is confirmed. When a target identifier is ambiguous (e.g., username shared across user and channel), Telethon may return a list. The forward target path discards this silently while the channel entity path raises an error. This creates an operational blind spot where configured targets may be permanently ignored.

**Recommendation:** Either take the first element of the list or raise `TelegramServiceError` on ambiguity. At minimum, add `logger.warning` naming the offending target. Priority: mandatory.

---

### DF-003: Fire-and-forget monitoring tasks are untracked and never drained on shutdown (in-flight state loss / permanently stalled channel)

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py`, `src/mko_telebot/cli.py` |
| **Classification** | advisory |

**Description:** Every per-channel unit of work is created with `asyncio.create_task(...)` and the returned handle is discarded (`monitor.py:131` and in the `finally` at `monitor.py:73`). Nothing tracks these tasks, and the shutdown path never awaits them. Two data-integrity gaps follow:

1. **Lost in-memory state on interrupt.** On `KeyboardInterrupt`, `asyncio.run` cancels all tasks. A `process_and_reschedule` that has just finished `process_task` (updating `task.last_msg_id` in memory) but is awaiting inside `save_state()` is cancelled before the state file is flushed → duplicate forwards on restart.
2. **Permanently stalled channel.** `reschedule_task` sleeps `task.scan_interval + random.uniform(10,30)` *before* `queue.put(task)`. If cancelled during sleep, the channel is never re-queued.

**Evidence Verified:**
- `monitor.py:131` — `asyncio.create_task(...)` handle discarded.
- `monitor.py:72-73` — `finally: asyncio.create_task(...)` handle discarded.
- `monitor.py:28-35` — queue.put happens only after sleep.
- `cli.py:121-123` — `except KeyboardInterrupt` raises `typer.Exit`.

> **Validation Note:**
> - **Action:** Validated with reduction
> - **Detail:** The described issues are real. However, per project guidelines favoring simplicity, a full task tracker may be overengineering. The minimal fix (move `queue.put` before sleep in `reschedule_task`) is recommended to prevent stalled channels, while documenting that in-flight state may be lost on hard interrupt is acceptable for this project scope.

**Recommendation:** Move `queue.put(task)` before the sleep in `reschedule_task` to prevent stalled channels on cancellation. Consider documenting the fire-and-forget design as intentional. Priority: recommended (simpler fix) / advisory.

---

### DF-004: Failing property test asserts wrong result for exclusion-only wildcard query (test vs production-code conflict)

| Field | Value |
|-------|-------|
| **ID** | DF-004 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | `tests/test_parser.py` |
| **Classification** | advisory |

**Description:** `tests/test_parser.py::test_property_no_crash_generated` fails. The falsifying example is `search_match('xyz', '"-X*"')` which the test expects to be `True`, but the matcher returns `False`. This is **correct production behavior**: `X*` matches words starting with `X` (case-insensitive). `xyz` starts with `x` which matches `X` under `re.IGNORECASE`. So `-X*` correctly *excludes* `xyz` and returns `False`. The test invariant is over-broad.

**Evidence Verified:**
- Runtime: `search_match('xyz','-X*')` → `False`; `search_match('abc','-X*')` → `True`.
- `matcher.py:106` — `_check_patterns_match` uses `re.IGNORECASE | re.UNICODE`.
- `matcher.py:39-44` — Wildcard pattern generates regex with word boundaries and `[^\s]*`.
- `tests/test_parser.py:629` — incorrect assertion inside `if query_content.startswith("-")` block.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Production code behavior is correct. The test's invariant "exclusion-only queries should return True for non-matching text" is too broad. `xyz` **does match** `X*` under case-insensitive matching, so `False` is the correct result. The fix is in the test, not the code. Per the project rule "production code is king," this finding is properly classified as DOC-UPDATE.

**Recommendation:** Fix the test to use text that genuinely does not match the exclusion pattern (e.g., `abc` instead of `xyz` for `-X*`). Document the explicit contract for case-insensitive wildcards. Priority: advisory.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 4 | DF-001, DF-002, DF-003, DF-004 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None.

### Merged Findings

No merged findings in this phase.

### Reclassified Findings

None.

---

## Rollout Analysis

### Dependencies

- DF-001 and DF-002 are independent; both can be implemented in any order.
- DF-003's minimal fix (put-before-sleep) is independent but should follow DF-001/002 for consistency.

### Sequencing Concerns

DF-001 (RPCError wrapping) should be implemented first to ensure state persistence on errors. DF-002 (multi-entity handling) can follow independently.

### Architectural Risks

- DF-001 requires wrapping telethon exceptions; ensure all `RPCError` subclasses are covered.
- The fire-and-forget pattern is intentional per project guidelines; adding task tracking may introduce unnecessary complexity.