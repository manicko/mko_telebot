# Phase 06 Audit Findings — End-to-End Data Flow

**Executor:** auditor
**Template:** `.ai/audit/templates/audit-findings.md`
**Status:** complete
**Validated:** no

---

## Findings

### DF-001: Permanent RPCError during forwarding escapes all error handlers and skips state persistence (duplicate re-dispatch + crashed worker)

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | CRITICAL |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py`, `src/mko_telebot/monitor.py`, `src/mko_telebot/core/task.py` |
| **Classification** | mandatory |

**Description:** A single permanent Telegram RPC error while forwarding to one target corrupts the entire per-channel data-flow contract: the `last_msg_id` state is never persisted, so the next cycle re-fetches and re-forwards the whole overlap window (duplicate dispatch), and the worker task dies with an unhandled exception.

The flow breaks at three stacked hops:
1. `forward_to_users` (`monitor_forward.py:149-158`) calls `_send_with_retry` per target. On a non-transient error, `_send_with_retry` (`monitor_forward.py:125-131`) catches `RPCError` and does a raw `raise` — re-raising the **bare `telethon.errors.RPCError`**, not a `MkoTelebotError` subclass.
2. `process_messages` → `process_task` (`monitor_forward.py:263-280`) lets this exception bubble up to `process_and_reschedule` (`monitor.py:40-73`).
3. In `process_and_reschedule`, `await process_task(...)` is inside `async with lock:` (line 58-59). A permanent `RPCError` is **not** a `TelegramServiceError`, so the `except TelegramServiceError` (line 68) does not catch it. Execution leaves the `async with lock` block **before** `await task.save_state()` (line 62) is ever reached.

Because `process_and_reschedule` is launched as a fire-and-forget `asyncio.create_task` (`monitor.py:131`), the unhandled `RPCError` becomes an uncaught exception on that task (worker dies), while the `finally` (line 72) still re-queues the task. On the next pass `task.last_msg_id` was never written to disk, so every message in the window `max(1, last_msg_id - overlap + 1) .. ` is re-fetched and re-forwarded → **duplicate alerts to users**.

**Evidence:**
- `monitor_forward.py:125-131` — `except RPCError as e: ... raise` re-raises raw `RPCError` (telethon, not `MkoTelebotError`).
- `monitor.py:57-66` — `await process_task(...)` precedes `await task.save_state()` inside `async with lock`; the `except` only matches `TelegramServiceError`.
- `monitor.py:73` — `finally: asyncio.create_task(reschedule_task(task, queue))` re-queues even though `save_state()` was skipped.
- `core/task.py:355-379` — `save_state()` writes `{"last_id": self.last_msg_id}`; never reached on this path.

**Recommendation:** Make `process_and_reschedule` resilient to non-`TelegramServiceError` exceptions so state is always persisted before a channel is re-queued. Concretely: (a) wrap the `process_task` call so that, on any exception, `save_state()` is still attempted (or at minimum the failure is logged and the task is not silently rescheduled with stale state), and (b) convert the permanent `RPCError` in `_send_with_retry` into a `TelegramServiceError` so it is handled uniformly by the existing `except` chain. Priority: mandatory — this loses data (duplicates forwards) and crashes a worker on the first hard RPC failure (e.g. `ChatWriteForbiddenError`, `UserIsBlockedError`).

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
Telethon's `get_entity` may return a `list` when the identifier is ambiguous (e.g. a username shared across a user and a channel, or a resolved peer that maps to multiple inputs). The `continue` discards the entire resolved set for that target. There is no `logger.warning`, no `StateError`, and (unlike the channel-entity path at `task.py:205-211`) no conversion to a `TelegramServiceError`. The data-flow consequence is that a configured target can be permanently ignored for the lifetime of the process without anyone noticing.

**Evidence:**
- `core/task.py:151-153` — `if isinstance(result, list): continue` with no logging or error.
- `core/task.py:205-211` — contrast: the channel-entity path *does* raise `TelegramServiceError` on a list result, proving the drop at `:152` is inconsistent with the rest of the module.
- `monitor_forward.py:149` — `for target in task.forward_to_entities:` consumes only what survived resolution.

**Recommendation:** Decide and document the contract for multi-entity resolution (e.g. take the first element, or raise `TelegramServiceError` if ambiguity is unacceptable), then emit at minimum a `logger.warning` naming the offending target. Do not leave it as a silent `continue`. Priority: mandatory — it produces undetected missed forwards to configured targets.

---

### DF-003: Fire-and-forget monitoring tasks are untracked and never drained on shutdown (in-flight state loss / permanently stalled channel)

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py`, `src/mko_telebot/cli.py` |
| **Classification** | advisory |

**Description:** Every per-channel unit of work is created with `asyncio.create_task(...)` and the returned `Task` handle is **discarded** (`monitor.py:131` and in the `finally` at `monitor.py:73`). Nothing tracks these tasks, and the shutdown path never awaits or cancels-and-requeues them. Two concrete data-integrity gaps follow:

1. **Lost in-memory state on interrupt.** `run_monitor` (`monitor.py:136-152`) `finally` only does `client.disconnect()`; it does not await pending `process_and_reschedule` / `reschedule_task` tasks. On `KeyboardInterrupt`, `asyncio.run` cancels all tasks (`cli.py:121-123` catches it and exits 130). A `process_and_reschedule` that has just finished `process_task` (updating `task.last_msg_id` in memory) but is awaiting inside `save_state()` (or inside the `asyncio.sleep` of `reschedule_task`) is cancelled before the state file is flushed → the updated `last_msg_id` is lost → next run replays the overlap window (duplicate forwards).
2. **Permanently stalled channel.** `reschedule_task` (`monitor.py:21-37`) sleeps `task.scan_interval + random.uniform(10,30)` *before* `queue.put(task)`. If its task is cancelled during that sleep (interrupt, or the event loop tearing down), the channel is **never re-queued** and stops being monitored until a full restart — a silent data-flow gap for that source.

**Evidence:**
- `monitor.py:131` — `asyncio.create_task(process_and_reschedule(task, client, queue, lock, settings))` handle discarded.
- `monitor.py:72-73` — `finally: asyncio.create_task(reschedule_task(task, queue))` handle discarded.
- `monitor.py:149-151` — `finally: client.disconnect()` only; no task drain.
- `cli.py:119-123` — `except KeyboardInterrupt: raise typer.Exit(code=130)`; `asyncio.run` then cancels remaining tasks.
- `monitor.py:29,33-35` — `reschedule_task` puts to queue only *after* the long sleep, so cancellation mid-sleep drops the channel.

**Recommendation:** Keep a set of in-flight task handles (or, simpler, do the `queue.put` in `reschedule_task` *before* the sleep so a cancelled sleep still leaves the channel queued). On shutdown, `run_monitor` should await pending tasks with a timeout and ensure `save_state()` has completed. Priority: recommended — the project guidelines favor simplicity, so the cheapest fix (reorder the put-before-sleep and track handles for a graceful drain) avoids overengineering while closing the duplicate-replay and stalled-channel gaps.

---

### DF-004: Failing property test asserts wrong result for exclusion-only wildcard query (test vs production-code conflict)

| Field | Value |
|-------|-------|
| **ID** | DF-004 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | `tests/test_parser.py` |
| **Classification** | advisory |

**Description:** `tests/test_parser.py::test_property_no_crash_generated` fails (1 failed in the full suite; the rest pass). The falsifying example is `search_match('xyz', '"-X*"')` which the test expects to be `True`, but the matcher returns `False`. This is **correct production behavior**: per the documented wildcard contract (`'*'` → `[^\s]*`, case-insensitive via `re.IGNORECASE | re.UNICODE`), `X*` matches any word beginning with `X`; `xyz` begins with `x` which matches `X` under `re.IGNORECASE`. So `-X*` correctly *excludes* `xyz` and returns `False`. The test's invariant ("exclusion-only queries should return True for non-matching text") is itself wrong for this input. Verified that genuinely non-matching text (`abc`, `zzz`, `foo bar`) against `-X*` correctly returns `True`. Per the project rule "production code is king," the test assertion is the defect, not the matcher.

**Evidence:**
- Runtime: `search_match('xyz','-X*')` → `False`; `search_match('abc','-X*')` → `True`.
- `matcher.py:106` — `_check_patterns_match` uses `re.IGNORECASE | re.UNICODE` flags.
- `matcher.py:40-44` — Wildcard pattern `X*` generates regex `\bX[^\s]*\b` with case-insensitive matching.
- `tests/test_parser.py:629` — `assert matcher("xyz", query) is True` inside the `if query_content.startswith("-")` block.
- See also SRV-001 (phase 03) which flags the same wildcard `[^\s]*` + case-insensitive over-matching as a doc/contract concern.

**Recommendation:** Fix the test to use a text that genuinely does not start with `X` (e.g. assert `matcher("abc", "-X*") is True` and `matcher("xyz", "-X*") is False`), or remove the over-broad invariant. Do not "fix" the matcher, as its current semantics are self-consistent and documented. Document the explicit contract that `X*` matches case-insensitively and that exclusion-only queries return True only for text that truly does not match the exclusion.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 1 |

## Mandatory Fixes

- **DF-001** (CRITICAL): Permanent RPCError during forwarding escapes all error handlers → `save_state()` skipped → lost `last_msg_id` → duplicate re-dispatch on next cycle; also crashes the worker task.
- **DF-002** (HIGH): Forward targets resolving to multiple entities are silently dropped with no log/error → undetected missed forwards.

## Advisory Recommendations

- **DF-003** (MEDIUM): Fire-and-forget process/reschedule tasks are untracked and never drained on shutdown → in-flight `last_msg_id` saves can be lost → duplicate replays; cancelled mid-sleep channel is never re-queued.
- **DF-004** (LOW): Failing property test asserts an incorrect result for exclusion-only wildcard query; the matcher is correct per its documented contract. Fix the test, not the code.

## Doc Updates Needed

- **DF-002** (`[DOC-UPDATE]`): Document the explicit behavior when a forward target resolves to multiple entities (currently silently dropped).
- **DF-004** (`[DOC-UPDATE]`): Document the wildcard + case-insensitive contract and the exclusion-only return semantics so test expectations stay aligned with production behavior.
