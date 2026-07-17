# Phase 05 Audit Findings — External Integrations (Validated)

**Executor:** audit-executor  
**Template:** .kilo/commands/audit/phases/05-audit-integrations.md  
**Status:** complete  
**Validated:** yes  

---

## Findings

### INT-001: Unhandled permanent RPCError from forwarding crashes the task (not isolated per-channel)

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | CRITICAL |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` (`_send_with_retry`, `forward_to_users`), `src/mko_telebot/monitor.py` (`process_and_reschedule`, `main_loop`) |
| **Classification** | mandatory |

**Description:** In `_send_with_retry` (monitor_forward.py:125-131) a permanent `RPCError` subclass (e.g. `UnauthorizedError`, `ChatWriteForbiddenError`) is re-raised with `raise`. This propagates through `forward_to_users` → `process_messages` → `process_task` → `process_and_reschedule`. But `process_and_reschedule` only catches `TelegramServiceError` (monitor.py:68); `RPCError` is NOT a `TelegramServiceError`, so it propagates as an unhandled exception out of the per-task coroutine. That coroutine is launched via `asyncio.create_task(process_and_reschedule(...))` (monitor.py:131) with NO `add_done_callback` / `Task.exception()` handling, so the exception becomes an unretrieved Task exception. A single bad target on one channel (e.g. a chat the bot was kicked from) therefore crashes that task and pollutes the event loop with an unhandled-exception warning (noisy and error-prone on Python 3.14). Because there is no reconnect (see INT-007), the emit of an unrelated connection `RPCError` on any channel terminates forward work for that cycle with no recovery.

**Evidence:**
- monitor_forward.py:125-131 — `except RPCError as e: ... raise` re-raises the raw Telethon error.
- monitor.py:68 — `except TelegramServiceError as e:` — `RPCError` does not match this branch.
- monitor.py:131 — `asyncio.create_task(process_and_reschedule(...))` with no done-callback; `main_loop` `while True` (monitor.py:128) relies on the task completing cleanly.
- Tests confirm intent: test_monitor.py:948-958 (`test_still_raises_for_other_exceptions`) asserts non-`StateError` exceptions propagate, i.e. the design lets raw `RPCError` escape.

**Recommendation:** Catch `RPCError` inside `forward_to_users`/`process_messages`, wrap it in `TelegramServiceError` (or log-and-skip the failing target), so a single bad target does not abort the whole task. Add a `Task` exception sink (e.g. `add_done_callback` that logs and reschedules) in `main_loop` so any escaped exception cannot silently corrupt the loop. Effort: small. Priority: mandatory.

---

### INT-002: Fetch FloodWaitError returns [] and silently drops the whole scan window

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` (`_fetch_messages`), `src/mko_telebot/monitor.py` (`process_task`) |
| **Classification** | mandatory |

**Description:** In `_fetch_messages` (monitor_forward.py:241-244) a `FloodWaitError` during `client.iter_messages(...)` is caught, the code sleeps `e.seconds + random.uniform(10,15)`, and then `return []`. The caller `process_task` (monitor.py:271-274) sees an empty list and simply logs "no new messages found" — it does NOT retry the fetch after the wait. The entire scan window for that channel is therefore silently dropped whenever Telegram imposes a flood wait at fetch time. This is inconsistent with the send path, which retries up to `max_retries` (monitor_forward.py:102-123). Because `last_msg_id` is only updated when messages are returned (monitor.py:275), a flood-waited fetch also means the channel makes no progress until the next scheduled cycle.

**Evidence:**
- monitor_forward.py:241-244 — `except FloodWaitError as e: ... await asyncio.sleep(...); return []`.
- monitor.py:271-274 — `new_messages = await _fetch_messages(...)`; empty list → "no new messages found".
- Tests confirm: test_monitor_forward.py:102-118 (`test_handles_flood_wait_error`) only asserts `asyncio.sleep` is called and `process_messages` is patched — it never re-attempts the fetch.

**Recommendation:** After sleeping for the flood wait, retry `client.iter_messages(...)` (bounded, consistent with `max_retries`), rather than returning `[]`. At minimum, re-raise a `TelegramServiceError` so the channel is rescheduled instead of silently marked "no new messages". Effort: small. Priority: mandatory.

---

### INT-003: Contradictory Telegram flood-wait handling policy is implicit

| Field | Value |
|-------|-------|
| **ID** | INT-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_client.py` (`create_client`), `src/mko_telebot/monitor_forward.py`, `src/mko_telebot/core/task.py` |
| **Classification** | advisory |

**Description:** Telethon clients have a built-in `flood_sleep_threshold` (default 60s) that automatically sleeps on `FloodWaitError` and retries. This project never sets `flood_sleep_threshold` on the `TelegramClient` (monitor_client.py:52-62), so the default auto-sleep is active, AND the code also manually catches `FloodWaitError` everywhere (`_fetch_messages`, `task.resolve_targets_entities`, `task.resolve_channel_entity`, `_send_with_retry`) with its own sleep + (often) custom backoff (`_calculate_retry_delay`, monitor_forward.py:28-41). The two policies conflict: Telethon may auto-sleep on a sub-threshold wait while the manual handler ALSO sleeps, doubling wait time and producing inconsistent behavior. The effective policy is implicit and undocumented.

**Evidence:**
- monitor_client.py:52-62 — `TelegramClient(...)` constructed without `flood_sleep_threshold` (default applies).
- monitor_forward.py:108-114, 241-243 — manual `FloodWaitError` handling with custom sleeps.
- core/task.py:161-175, 215-229 — manual `FloodWaitError` handling in entity resolution.

**Recommendation:** Make the policy explicit. Either set `flood_sleep_threshold=0` on the client and own all flood-wait handling manually (recommended for predictable backoff), or remove the manual handlers and rely on Telethon. Document the chosen policy. Effort: small. Priority: recommended.

---

### INT-004: 2FA (SessionPasswordNeededError) for user accounts is "handled" by failing to start with no recovery

| Field | Value |
|-------|-------|
| **ID** | INT-004 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/monitor_client.py` (`start_client`), `src/mko_telebot/monitor.py` (`run_monitor`), `src/mko_telebot/core/telethon.py` (`TelethonConfig`), `src/mko_telebot/settings/telethon_config.yaml` |
| **Classification** | mandatory |

**Description:** `start_client` (monitor_client.py:92-94) catches `SessionPasswordNeededError` and returns `False` — same as a plain auth failure. `run_monitor` (monitor.py:152-153) then raises `TelegramAuthError("Telegram authentication failed")`, terminating the process. For `is_user: true` (the shipped default, telethon_config.yaml:13), Telegram frequently requires a 2FA password, so the default configuration path is non-functional for any 2FA-protected account. There is no `password` field in `TelethonConfig`/`ClientConfig` (core/telethon.py:168-198) and no documentation of this limitation. A user following the template will get a hard auth failure with no actionable guidance.

**Evidence:**
- monitor_client.py:92-94 — `except (AuthKeyUnregisteredError, SessionPasswordNeededError, ValueError) as e: ... return False`.
- monitor_client.py:80-86 — `client.start(phone=...)` with no `password=` argument.
- monitor.py:152-153 — `else: raise TelegramAuthError(...)`.
- core/telethon.py:168-198 — `TelethonConfig` has no 2FA password field.
- settings/telethon_config.yaml:13 — `is_user: true` default; no password key.
- docs/11-guides/configuration.md — no mention of 2FA password requirement for user accounts.

**Recommendation:** Either (a) add a `password` field to `TelethonConfig`, pass it to `client.start(password=...)`, and document the 2FA flow; or (b) if 2FA is explicitly unsupported, fail fast with a clear message naming the 2FA requirement and document the limitation in docs/11-guides/configuration.md and the schema. Effort: small. Priority: mandatory.

---

### INT-005: build_sender_tag swallows transient connection errors but still returns '' (silent author loss)

| Field | Value |
|-------|-------|
| **ID** | INT-005 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/monitor_client.py` (`build_sender_tag`) |
| **Classification** | advisory |

**Description:** `build_sender_tag` (monitor_client.py:119-160) calls `await msg.get_sender()`. On `RPCError` (line 152-155) or `OSError`/`ConnectionError`/`TimeoutError` (line 157-160) it logs and returns `""`. For transient network errors this is the wrong behavior: the whole forward caption loses the `Author:` tag even though a short retry would likely succeed. The result is silent degradation — forwards go out without sender attribution, and the only trace is a debug/exception log, not a surfaced failure. The forwarding path (`forward_to_users`, monitor_forward.py:146) does not retry sender resolution.

**Evidence:**
- monitor_client.py:152-155 — `except RPCError as e: logger.exception(...); return ""`.
- monitor_client.py:157-160 — `except (OSError, ConnectionError, TimeoutError) as e: ... return ""`.
- monitor_forward.py:146 — `sender_tag = await build_sender_tag(msg)` used once; no retry.

**Recommendation:** For transient errors, retry `get_sender()` with small backoff before falling back to `""`, or re-raise so the item is retried in the send path. At minimum, distinguish transient vs permanent errors in logging so silent author loss is observable. Effort: small. Priority: recommended.

---

### INT-006: FloodWaitError during target/channel entity resolution aborts channel init for all resolvable targets

| Field | Value |
|-------|-------|
| **ID** | INT-006 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/core/task.py` (`resolve_targets_entities`, `resolve_channel_entity`) |
| **Classification** | advisory |

**Description:** In `resolve_targets_entities` (task.py:161-175) and `resolve_channel_entity` (task.py:215-229), a `FloodWaitError` is caught, the code sleeps, and then immediately `raise TelegramServiceError(...)` — it does NOT retry the `get_entity` call. Per-target, a single flood wait aborts resolution of that target (and for the channel entity, aborts the entire channel at monitor startup, see monitor.py:122 `except TelegramServiceError: continue`). At startup this means a channel whose entity resolution hits a flood wait is silently dropped from monitoring entirely. This is inconsistent with the send path which retries up to `max_retries`.

**Evidence:**
- task.py:161-175 — `except FloodWaitError as e: ... await asyncio.sleep(...); raise TelegramServiceError(...)`.
- task.py:215-229 — identical pattern for `resolve_channel_entity`.
- monitor.py:122-124 — `except TelegramServiceError as e: logger.error(...); continue` drops the channel for the rest of the process lifetime.
- Tests confirm: test_task.py:306-310 and test_task.py:406-412 assert the handler sleeps then re-raises `TelegramServiceError` (the buggy behavior is locked by tests).

**Recommendation:** Retry `get_entity` after the flood wait (bounded retry), consistent with the send path, instead of raising immediately. Effort: small. Priority: recommended.

---

### INT-007: Client lifecycle: disconnect not awaited; no reconnect on dropped connection

| Field | Value |
|-------|-------|
| **ID** | INT-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py` (`run_monitor`), `src/mko_telebot/monitor_client.py` |
| **Classification** | advisory |

**Description:** Two lifecycle concerns:
1. `run_monitor` (monitor.py:150) calls `client.disconnect()` without `await` inside a `finally`. Telethon's `disconnect()` is a coroutine; calling it without `await` schedules it but does not guarantee cleanup completes before process exit. This can leave the `.session` file not cleanly flushed on shutdown.
2. The monitor loop has no reconnect/health-check logic. If the connection drops mid-run (network blip), Telethon raises on the next API call; with INT-001 unresolved this crashes the whole process. A lightweight reconnect-on-`ConnectionError` wrapper around the per-task work would improve operational reliability.

**Evidence:**
- monitor.py:150 — `finally: client.disconnect()` (no `await`).
- monitor.py:128-133 — `while True` loop has no connection health check; `process_task` relies on the single long-lived client.

**Recommendation:** Use `await client.disconnect()` in `run_monitor`'s `finally`, and add a bounded reconnect attempt (or at least a `try/except ConnectionError` that logs and reschedules) around `process_task` so transient disconnects don't kill the daemon. Effort: small. Priority: recommended.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 7 | All findings confirmed |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Validated Findings

| ID | Original Type | Validation Note |
|----|---------------|-----------------|
| INT-001 | RUNTIME-ERROR | Confirmed — `RPCError` (not subclass of `TelegramServiceError`) propagates unhandled through `process_and_reschedule` → `asyncio.create_task()` without exception handling. Test `test_still_raises_for_other_exceptions` explicitly validates this behavior. Critical architectural gap. |
| INT-002 | RUNTIME-ERROR | Confirmed — `_fetch_messages` returns `[]` after flood wait sleep without retry. Inconsistent with `_send_with_retry` which has bounded retry logic. Test `test_handles_flood_wait_error` documents the current behavior but not the expected retry. |
| INT-003 | BEST-PRACTICE | Confirmed — `TelegramClient` created without explicit `flood_sleep_threshold`, while manual handlers exist in `_send_with_retry`, `_fetch_messages`, and `task.py`. Policy is implicit and potentially double-sleeps. Documentation recommends explicit configuration. |
| INT-004 | SPEC-DEVIATION | Confirmed — `is_user: true` is the shipped default (telethon_config.yaml:13), but `SessionPasswordNeededError` is caught and treated as generic auth failure. No `password` field in `TelethonConfig`. Configuration guide makes no mention of 2FA requirements. |
| INT-005 | RUNTIME-ERROR | Confirmed — `build_sender_tag` catches and silently returns `""` on transient connection errors. Forwarding path uses sender tag once without retry. Silent degradation of forwarded message quality. |
| INT-006 | RUNTIME-ERROR | Confirmed — Entity resolution raises `TelegramServiceError` immediately after flood wait sleep without retry. Inconsistent with send path retry policy. Tests lock in the buggy behavior. |
| INT-007 | BEST-PRACTICE | Confirmed — `client.disconnect()` is not awaited (not a `TelegramServiceError` subclass, so not caught). No reconnect logic in monitor loop. Operational reliability concern. |

### Rollout Analysis

**Critical Dependencies:**
- INT-001 fix must precede INT-007 for full error resilience (task crashing → no reconnect)
- INT-003 policy decision should be made before modifying INT-002 or INT-006 retry logic
- INT-004 introduces new field (`password`) → requires config schema update

**Cross-Phase Relationship:**
- SRV-002 (services) addressed graceful shutdown via signal handlers — REJECTED (out of scope per spec)
- INT-001/INT-007 address runtime error resilience within existing fire-and-forget pattern — VALIDATED
- These are complementary: SRV-002 = shutdown handling, INT-001/INT-007 = error handling. No conflict.

**Unsafe Execution Sequences:**
- If INT-004 adds password field but `run_monitor` disconnect remains unawaited, session files may be corrupted during auth flow restart
- INT-002 retry logic alone without INT-001 capture could cause cascading flood waits if raw `RPCError` interrupts iteration

### Warnings

- **Architectural risk:** The `asyncio.create_task()` in `main_loop` (monitor.py:131) creates fire-and-forget tasks. Without done-callbacks, any unhandled exception becomes an unretrieved Task exception. This pattern is fragile and error-prone.
- **Rollout risk:** INT-006 and INT-002 entity resolution failures permanently drop channels from monitoring at startup. Recovery requires process restart.
- **Documentation inconsistency:** Configuration guide (docs/11-guides/configuration.md) documents `is_user` default as `true` but does not warn about 2FA requirement for user accounts.

### Required Fixes

- **INT-001** (CRITICAL): Wrap/intercept permanent `RPCError` from forwarding so a single channel/target failure does not terminate the entire monitor process. Add Task exception sink in `main_loop`.
- **INT-002** (HIGH): Retry message fetch after FloodWait instead of returning `[]` and silently dropping the scan window.
- **INT-004** (HIGH): Handle 2FA (`SessionPasswordNeededError`) for `is_user` accounts or fail fast with an explicit, documented message.

### Advisory Recommendations

- **INT-003** (MEDIUM): Set `flood_sleep_threshold=0` on client to own all flood-wait handling manually, or remove manual handlers. Document the chosen policy.
- **INT-005** (MEDIUM): Distinguish transient vs permanent errors in `build_sender_tag` logging. Consider retry on transient errors.
- **INT-006** (MEDIUM): Retry `get_entity` after FloodWait in entity resolution instead of raising immediately.
- **INT-007** (LOW): `await client.disconnect()` in `run_monitor`'s `finally`, and add reconnect wrapper around per-task work.