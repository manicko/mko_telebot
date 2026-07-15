# Phase 05 — External Service Integrations — Findings

**Auditor:** auditor agent
**Date:** 2026-07-15
**Source:** `.kilo/commands/audit/phases/05-audit-integrations.md`
**Mode:** problems_only

---

### INT-001: `start_client()` catches the wrong exception types; real Telethon failures crash the process

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/monitor_client.py` |
| **Classification** | mandatory |

**Description:** `start_client()` wraps the `client.start()` call in `except TelegramAuthError / TelegramServiceError`. However, Telethon's `client.start()` never raises these custom project exceptions — it raises its own hierarchy (`RPCError` subclasses, `ValueError` for 2FA, `OSError`, `ConnectionError`, etc.). As a result, the `except` blocks are dead code: real failures such as bad credentials, an unreachable Telegram API, or a required 2FA password raise uncaught exceptions that crash the entire process instead of returning `False` for a graceful failure. Worse, the surrounding unit tests (e.g. `tests/test_monitor.py:273-287`) inject the custom exception types, so they "pass" while masking the bug and giving a false sense of robustness.

**Evidence:**
- `monitor_client.py:75-92` — `try: await client.start(...)` followed by `except (TelegramAuthError, TelegramServiceError)`.
- Telethon `client.start()` raises `telethon.errors.*` / `ValueError` / `OSError`, never the project's custom exceptions.

**Recommendation:** Map real Telethon exceptions to the project's `TelegramAuthError`/`TelegramServiceError` (or catch the Telethon hierarchy explicitly) so auth/service failures reliably return `False`. Update `test_monitor.py` to assert against real Telethon exception behavior. Effort: small. Priority: must fix.

---

### INT-002: `build_sender_tag()` fallback never triggers for real `get_sender()` errors

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** `build_sender_tag()` wraps `get_sender()` in `except TelegramServiceError` to fall back to an empty/unknown sender tag. Because Telethon raises only Telethon exception types, this `except` branch is unreachable — the empty-sender fallback is dead code. Any genuine `get_sender()` failure leaks a raw Telethon traceback instead of the intended graceful fallback.

**Recommendation:** Catch the real Telethon exception types (or the project's mapped exception) so the fallback path actually executes. Effort: trivial. Priority: recommended.

---

### INT-003: `_send_with_retry()` retries permanent `RPCError` subclasses

| Field | Value |
|-------|-------|
| **ID** | INT-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** `_send_with_retry()` applies the same backoff/retry loop to *all* `RPCError` subclasses, including permanent ones (e.g. banned, peer-invalid, dead/invalid session). Retrying these wastes backoff budget, delays failure surfacing, and never recovers — a dead session condition is silently retried indefinitely rather than reported.

**Recommendation:** Classify `RPCError` subclasses; only retry transient errors (e.g. `FloodWaitError`, `ServerError`, `TimedOut`). Surface permanent errors immediately. Effort: small. Priority: recommended.

---

### INT-004: Per-channel work launched via un-awaited `asyncio.create_task`; Telethon exceptions escape silently

| Field | Value |
|-------|-------|
| **ID** | INT-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | advisory |

**Description:** `monitor.py` launches per-channel processing via `asyncio.create_task(...)` without retaining the handle or attaching a done-callback. When a Telethon exception escapes inside that task, it is never retrieved, logged only as a "Task exception was never retrieved" warning, and the affected channel is effectively dropped from monitoring with no operator visibility.

**Recommendation:** Track spawned tasks and attach exception handling/diagnostics (see also SRV-002 / CLI-004). Effort: small. Priority: recommended.

---

### INT-005: Dead/redundant `except TelegramServiceError` in `_fetch_messages()`

| Field | Value |
|-------|-------|
| **ID** | INT-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** In `_fetch_messages`, the `except RPCError` branch (monitor_forward.py:230-237) catches the error and immediately `raise TelegramServiceError(...)`. The subsequent `except TelegramServiceError` (monitor_forward.py:239-241) can therefore only be reached if `TelegramServiceError` were raised *directly* inside the `try` (the `client.iter_messages`/`async for` block) — but those only raise Telethon exceptions, not the custom type. The branch is unreachable dead code that gives a false impression of layered handling and confuses maintainers.

**Evidence:**
- `monitor_forward.py:230-241` — `except RPCError ... raise TelegramServiceError(...)` immediately followed by `except TelegramServiceError`.

**Recommendation:** Remove the unreachable `except TelegramServiceError` branch; if a local catch is desired, raise the `TelegramServiceError` once and let `monitor.py:117` handle it uniformly. Effort: trivial. Priority: recommended.

---

### INT-006: `start_client()` has no 2FA/password or non-interactive code path for user accounts

| Field | Value |
|-------|-------|
| **ID** | INT-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_client.py` |
| **Classification** | advisory |

**Description:** `is_user=True` auth calls `client.start(phone=...)` with no `code_callback` and no `password`. On first login with 2FA enabled, Telethon raises `ValueError("Two-step verification is enabled...")` (telethon/client/auth.py:220) — uncaught here (see INT-001), so the process crashes. With no session yet authorized and no `code_callback` supplied, Telethon falls back to a blocking `input()` prompt (auth.py:100-103), which hangs forever in a headless/background deployment. There is also no way to supply the login code or 2FA password from config for unattended operation. The `is_user` flag *does* correctly switch phone vs bot-token auth, so this is an operational gap rather than a switching bug.

**Evidence:**
- `monitor_client.py:76-83` — `client.start(phone=...)` / `client.start(bot_token=...)` with no `code_callback`/`password`.
- `telethon/client/auth.py:100-103` (default `input()`-based `code_callback`) and `:220` (2FA `ValueError`).

**Recommendation:** For user mode, support loading the 2FA `password` from settings (passed through `api_hash`-like `SecretStr`) and provide a `code_callback`/interactive flow that is documented; detect 2FA `ValueError`/`SessionPasswordNeededError` and surface a clear actionable message. Worst case, document that first-run interactive login is required and that 2FA accounts need additional setup. Effort: small–medium. Priority: recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 4 |
| LOW | 1 |

## Mandatory Fixes

- **INT-001** — `start_client()` error handling is ineffective (catches wrong exception types); invalid credentials / unreachable API crash the process instead of a graceful failure. Must fix.

## Advisory Recommendations

- **INT-002** — `build_sender_tag()` fallback never triggers for real Telethon errors.
- **INT-003** — Stop retrying permanent `RPCError` subclasses in `_send_with_retry()`.
- **INT-004** — Stop swallowing per-channel task exceptions via un-awaited `asyncio.create_task`.
- **INT-005** — Remove unreachable `except TelegramServiceError` in `_fetch_messages()`.
- **INT-006** — Add 2FA/password and non-interactive login support for user accounts.

## Doc Updates Needed

- Update `docs/SPEC.md` / integration docs to state that `start_client()` failures (bad credentials, API unreachable, 2FA) are handled gracefully and logged; current docs imply a `False` return that the implementation cannot produce for real Telethon errors (ties to INT-001, INT-006).
