### DF-004: Fire-and-forget background tasks have no supervision (root enabler of DF-001)

| Field | Value |
|-------|-------|
| **ID** | DF-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** All long-running units are launched with `asyncio.create_task` and never
awaited: `process_and_reschedule` (`monitor.py:126`), the nested `reschedule_task`
(`monitor.py:68`), and the client-disconnect path. No `Task` reference is retained and no
`add_done_callback`/`gather` wrapper catches failures. Consequences: (a) an exception inside
any background task produces only a "Task exception was never retrieved" warning and is
otherwise invisible; (b) on Ctrl+C / shutdown, in-flight tasks are cancelled without a
graceful drain, and any task not yet re-queued is silently lost. This is the structural
cause of DF-001 (an unhandled channel error disappears instead of being logged + recovered).

**Evidence:** `monitor.py:68`, `monitor.py:126`, `monitor.py:145` — all `create_task(...)`
call sites without result storage or done-callback.

**Recommendation:** Keep a strong reference to each created task (e.g. a `Set[Task]` pruned
in a done-callback) and install a callback that logs exceptions and re-schedules the channel.
On shutdown, `await` cancellation of tracked tasks (or cancel + `asyncio.gather(...,
return_exceptions=True)`) so the loop drains before `client.disconnect()`.
**Priority:** recommended.

---

### DF-005: Ambiguous forward targets are silently dropped during entity resolution

| Field | Value |
|-------|-------|
| **ID** | DF-005 |
| **Severity** | LOW |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** In `resolve_targets_entities`, if `client.get_entity(ent)` returns a list
(multiple matches for an ambiguous identifier), the code does `if isinstance(result, list):
continue` (`task.py:77-78`). The target is dropped with no warning, so forwards to that
target are silently skipped for every matching message. Combined with DF-002 (cursor still
advances), the message is marked processed even though one configured destination never
received it.

**Evidence:** `task.py:77-78` — `if isinstance(result, list): continue` with no log.

**Recommendation:** Log a WARNING naming the ambiguous target and either pick the first
entity (documented choice) or fail the channel setup explicitly, rather than silently
dropping it.
**Priority:** recommended.

---

### DF-006: Global lock serializes all channels, making one slow channel delay every other

| Field | Value |
|-------|-------|
| **ID** | DF-006 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py, src/mko_telebot/monitor_forward.py |
| **Classification** | advisory |

**Description:** `process_and_reschedule` holds a single `asyncio.Lock` around the entire
`process_task` (`monitor.py:57-58`), so only one channel is fetched/forwarded at a time.
Forwarding adds `random.uniform(5, 10)` s of sleep per target (`monitor_forward.py:146`)
plus retry backoff sleeps. With several channels, a single slow channel (many matches,
multiple targets, retries) blocks the global lock and inflates the effective scan interval
for all other channels, increasing the chance of missing time-sensitive posts.

**Evidence:** `monitor.py:57` (`async with lock:`), `monitor_forward.py:146` (+ per-target
sleep), `monitor_forward.py:110,118` (retry sleeps).

**Recommendation:** Verify Telethon client concurrency guarantees; if sequential sends are
safe (they are for distinct `send_*` calls), scope the lock to shared-state writes only (the
`last_msg_id`/state update) or run per-channel processing concurrently and serialize just the
state-persist step. This keeps per-channel cadence independent.
**Priority:** recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 3 |
| LOW | 1 |

## Mandatory Fixes

- **DF-001** (HIGH) — Fetch-time RPCError permanently removes a channel from monitoring.
- **DF-002** (HIGH) — Forward failures still advance `last_msg_id`, permanently losing posts.
- **DF-003** (MEDIUM) — Caption-less media posts never forwarded, contradicts docs.

## Advisory Recommendations

- **DF-004** (MEDIUM) — Supervise fire-and-forget background tasks (root cause of DF-001).
- **DF-005** (LOW) — Log/surface ambiguous forward targets instead of dropping silently.
- **DF-006** (LOW) — Avoid global serialization of per-channel processing.

## Doc Updates Needed

- **DF-001** — overview.md "RPCError … retries with exponential backoff" implies fetch errors
  are retried; they are fatal to the channel instead.
- **DF-003** — overview.md:81/88 imply media is forwarded "intact"; caption-less media is
  dropped.
