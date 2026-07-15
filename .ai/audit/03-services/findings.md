---
name: audit-findings
description: Phase 03 — Service Layer & Business Logic findings
agent: auditor
status: complete
validated: no
---

# Phase 03 Audit Findings — Service Layer & Business Logic

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/03-audit-services.md
**Status:** in-progress
**Validated:** no
**Mode:** problems-only

## Runtime Verification Summary

- **R1 Import:** All service modules import cleanly (`python -c` import of monitor, monitor_forward, monitor_client, core.task, core.matcher, core.channels → `IMPORT OK`).
- **R2 Lint/Type:** `ruff check` → exit 0 (all checks passed). `basedpyright` → 0 errors, **52 warnings** (mostly `reportExplicitAny` / `reportUnknownMemberType` from Telethon types). Exit code 1 due to warnings.
- **R3 Tests:** `pytest tests -q` → **353 passed, 0 failed**.
- **R4 Dead code:** No dead top-level service functions found. `create_client` and `run_monitor` are used by `cli.py` (`run` command). `build_sender_tag`/`build_message_link` used by `monitor_forward.py`. One redundant constructor path noted (SRV-006).

---

## Findings

### SRV-001: Channel is permanently dropped from monitoring on any exception in `process_task`

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/monitor.py`, `src/mko_telebot/monitor_forward.py` |
| **Classification** | mandatory |

**Description:** `process_and_reschedule` (the coroutine run for every channel cycle) is launched as an untracked `asyncio.create_task` from `main_loop`. Inside it, `await process_task(...)` is **not** wrapped in `try/except`:

```python
# monitor.py:57-68
async with lock:
    await process_task(task, client, settings)   # may raise
    try:
        await task.save_state()
    except StateError as e:
        ...
asyncio.create_task(reschedule_task(task, queue))  # never reached if process_task raised
```

`process_task` can raise. For example, `_fetch_messages` explicitly re-raises on a non-flood RPC error:

```python
# monitor_forward.py:230-237
except RPCError as e:
    logger.warning(...)
    await asyncio.sleep(5)
    raise TelegramServiceError(f"Failed to fetch messages for {task.channel_name}: {e}") from e
```

Other transient failures (e.g. non-RPC network errors inside `build_sender_tag`/`send_file`) also propagate. When `process_task` raises, the exception escapes `process_and_reschedule`; because that coroutine runs as an un-awaited `asyncio.Task`, the exception is only logged as *"Task exception was never retrieved"* and **line 68 (`reschedule_task`) is never reached**. The channel is therefore **never re-enqueued** and silently stops being monitored for the remainder of the process lifetime — with no user-visible error. A single transient `ServerError`/`TimedOut` permanently kills that channel's monitoring.

**Evidence:** monitor.py:57-68 (no guard around `process_task`); monitor_forward.py:230-237 (`raise TelegramServiceError`); monitor.py:126 (`create_task` not tracked).

**Recommendation:** Wrap the `process_task` call (and `save_state`) in `try/except` so the channel is **always** rescheduled even on failure, e.g. move `reschedule_task` into a `finally`, and re-enqueue the same `task` after logging the error. This keeps the channel alive across transient API errors.

---

### SRV-002: Fire-and-forget `asyncio.create_task` lacks supervision and shutdown handling

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | advisory |

**Description:** Both `process_and_reschedule` (monitor.py:126) and the inner `reschedule_task` (monitor.py:68) are spawned with `asyncio.create_task(...)` and never stored, awaited, or given a done-callback. Consequences:

1. Any exception raised inside them is silently discarded (see SRV-001) — no supervision.
2. On shutdown, `run_monitor`'s `finally` only calls `client.disconnect()` (monitor.py:144-145). It does **not** `await` pending scheduling/processing tasks. When the event loop is closed, in-flight tasks are cancelled mid-flight without cleanup logging, making shutdown behavior hard to reason about.

**Evidence:** monitor.py:68 (`create_task(reschedule_task(...))` detached); monitor.py:126 (`create_task(process_and_reschedule(...))` detached); monitor.py:142-145 (`finally` only disconnects).

**Recommendation:** Keep references to spawned tasks (e.g. a `set[asyncio.Task]` pruned via `add_done_callback`), log/propagate their exceptions, and `await asyncio.gather(...)` on the tracked set in `run_monitor`'s `finally` (with a timeout) so shutdown is graceful and failures are observable.

---

### SRV-003: Captionless media-only messages are silently dropped, contradicting documented forwarding behavior

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py`, `docs/00-overview/overview.md` |
| **Classification** | mandatory |

**Description:** `process_messages` gates the entire forward path on `msg_text` being non-empty:

```python
# monitor_forward.py:181-194
for album_id, content in msg_content.items():
    msg_text = "\n".join(content.get("text", []))
    if msg_text and (not task.keywords or any(search_match(msg_text, kw) for kw in task.keywords)):
        await forward_to_users(...)
```

When a message/album has media but **no body text and no caption**, `msg_text == ""` and the branch is skipped entirely — the media is never forwarded even though `content["media"]` was populated. This:

- Contradicts the documented behavior *"Media handling — Messages with media (including albums) are forwarded intact"* (overview.md:88) and *"photo/video posts ... are forwarded even when the body is empty"* (overview.md:81,125).
- Breaks the *"no keywords → forward everything"* contract implied by the `not task.keywords` branch: a channel configured without keywords still drops every captionless photo/video post.

**Evidence:** monitor_forward.py:181 (`if msg_text and ...`); docs/00-overview/overview.md:81, 88, 125.

**Recommendation:** Base the forward decision on whether the group carries **matchable content OR media**, not solely on `msg_text`. E.g. forward when `(msg_text and keyword_match) or (content["media"] and not task.keywords)`. When keywords are set and a media-only post has no caption, it is correct to skip; when no keywords are set, media-only posts should still be forwarded.

---

### SRV-004: `search_match` swallows all parse/runtime errors and silently disables a misconfigured keyword

| Field | Value |
|-------|-------|
| **ID** | SRV-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/matcher.py` |
| **Classification** | advisory |

**Description:** `search_match` wraps parsing/evaluation in a broad `except Exception` that logs and returns `False`:

```python
# matcher.py:172-183
try:
    inclusions, exclusions = parse_query(query)
    return evaluate_query(text, inclusions, exclusions)
except Exception as e:
    logger.exception(f"Error while evaluating search_match for query '{query}': {e}")
    return False
```

A single malformed keyword in the **config** (e.g. an unbalanced parenthesis, a dangling `-`) causes that keyword to **never match anything, forever**, with only a debug-level exception in the log. The operator gets no startup warning and no config-validation failure — the filter silently becomes ineffective. This violates the project rule *"never silently swallow errors"* in spirit (the failure is logged but invisible to the user) and undermines trust in filtering.

**Evidence:** matcher.py:172-183 (broad `except Exception` → `return False`).

**Recommendation:** Validate every keyword at config-load time by parsing it once (in `validate()` / `TelepostConfigReader`) and raising `ConfigError` on invalid syntax, so bad keywords fail fast before monitoring starts. Keep the runtime `try/except` only as a last-resort guard, not the primary error path.

---

### SRV-005: Type-safety degradation in the service layer (`Any`/`Unknown` leakage)

| Field | Value |
|-------|-------|
| **ID** | SRV-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** `basedpyright` reports 52 warnings across the service modules, concentrated in `monitor_forward.py`: `reportExplicitAny` (public `forward_to_users(msg_media: list[Any])`, `process_messages`, return `dict[str, Any]`), `reportUnknownMemberType`/`reportUnknownArgumentType` (Telethon `Message` attributes accessed via `getattr`). The project rules mandate *"Type Safety Everywhere"* with strict typing. Untyped `Any` on public forwarding APIs defeats static checking of the core message pipeline and hides real attribute mistakes.

**Evidence:** monitor_forward.py:42 (`dict[int | None, dict[str, Any]]`), :78/126 (`list[Any] | None`), :188-190 (`reportAny` on `msg`/`msg_media`); full basedpyright output 0 errors / 52 warnings.

**Recommendation:** Narrow the `Any` usage — model the grouped-message payload as a small `@dataclass`/`TypedDict` instead of `dict[str, Any]`, and annotate `Message`/`Entity` from `telethon.tl.custom.message`/`telethon.hints` (or use `# pyright: ignore` surgically with a comment explaining why) so the public API surface is type-checked.

---

### SRV-006: Redundant `Task.__init__(last_msg_id=...)` seeding path never used by callers

| Field | Value |
|-------|-------|
| **ID** | SRV-006 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/task.py`, `src/mko_telebot/monitor.py` |
| **Classification** | advisory |

**Description:** `Task.__init__` accepts `last_msg_id: int = 0`, but the only caller (`monitor.py:104`, `Task(config=channel_settings)`) never supplies it, so it is always `0` and is immediately overwritten by `load_state()` (task.py:166). The constructor seeding path is dead in practice. Per the project's Dead Code Policy this is future-proofing rather than obvious dead code, but the purpose should be confirmed.

**Evidence:** task.py:48 (param `last_msg_id: int = 0`), task.py:63 (`self.last_msg_id = last_msg_id or 0`), task.py:166 (overwritten by `load_state`); monitor.py:104 (caller omits the arg).

**Recommendation:** Investigate whether the seedable `last_msg_id` is intended for tests/external seeding. If not, drop the parameter and initialize `last_msg_id = 0` directly; if yes, document the intended use so it is not mistaken for dead code.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 2 |

## Mandatory Fixes

- **SRV-001** — Channel permanently dropped from monitoring on any exception in `process_task` (HIGH, correctness/reliability).
- **SRV-003** — Captionless media-only messages silently dropped, contradicting documented forwarding behavior (MEDIUM, SPEC-DEVIATION).

## Advisory Recommendations

- **SRV-002** — Supervise fire-and-forget tasks and await them on shutdown (MEDIUM).
- **SRV-004** — Validate keyword syntax at config load instead of silently disabling bad keywords at runtime (MEDIUM).
- **SRV-005** — Replace `Any`/`Unknown` leakage in the forwarding API with typed payloads (LOW).
- **SRV-006** — Confirm or remove the unused `last_msg_id` constructor seed (LOW).

## Doc Updates Needed

- **SRV-003** — `docs/00-overview/overview.md` (lines 81, 88, 125) states media/albums are *"forwarded intact"*; clarify that captionless media-only posts are currently dropped, or update after the code fix.

---

