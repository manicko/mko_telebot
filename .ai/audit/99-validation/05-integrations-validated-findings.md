---
name: validated-findings
description: Phase 05 � External Service Integrations validated findings
agent: validator
status: complete
validated: yes
---

# Phase 05 Validated Findings � External Service Integrations

**Source:** `.ai/audit/05-integrations/findings.md`  
**Validation Date:** 2026-07-15  
**Validator:** validator agent

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 4 | INT-001, INT-002, INT-003, INT-004 |
| Reclassified | 1 | INT-005: BEST-PRACTICE -> SPEC-DEVIATION |
| Rejected | 1 | INT-006 |
| Merged | 0 | � |

---

## Approved Findings

### INT-001: `start_client()` catches the wrong exception types; real Telethon failures crash the process

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Classification** | mandatory |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `monitor_client.py:75-92` � `try: await client.start(...)` followed by `except (TelegramAuthError, TelegramServiceError)` only
- `TelegramClient.start()` raises Telethon's own exceptions: `RPCError` subclasses from `telethon.errors`, `ValueError` for 2FA, `OSError`, `ConnectionError`, `asyncio.TimeoutError`, etc.
- The custom exceptions `TelegramAuthError` and `TelegramServiceError` are defined in `core/errors.py` but are never raised by Telethon code

**Project Rule Violation:** Violates "never silently swallow errors" � exceptions escape unlogged, crashing the process instead of graceful `False` return.

**Architectural Impact:** HIGH � Real failures (bad credentials, unreachable API, 2FA prompts) crash the entire process. The `except` block is dead code that never executes in production.

**Recommendation:** In `monitor_client.py:start_client()`, catch Telethon's exception hierarchy directly — specifically `telethon.errors.RPCError` and its auth-related subclasses (`AuthKeyUnregisteredError`, `SessionPasswordNeededError`), plus `ValueError` (2FA), `OSError`, `ConnectionError`, `asyncio.TimeoutError` — and convert them into `TelegramAuthError` (auth/credential failures) or `TelegramServiceError` (connectivity/RPC failures), returning `False` on auth failure.

### INT-002: `build_sender_tag()` fallback never triggers for real `get_sender()` errors

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Classification** | advisory |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `monitor_client.py:124-148` � `try: await msg.get_sender()` followed by `except TelegramServiceError`
- `msg.get_sender()` (Telethon `Message.get_sender()`) raises Telethon exception types only, never `TelegramServiceError`
- The fallback path returning `""` is unreachable for any genuine `get_sender()` failure

**Analysis:** Same root cause as INT-001 � exception type mismatch. Any real `get_sender()` failure (network error, API issue) leaks raw Telethon traceback instead of the intended graceful fallback.

**Architectural Impact:** MEDIUM � Loss of graceful degradation for sender resolution.

**Recommendation Stands:** Catch real Telethon exception types for graceful fallback.

### INT-003: `_send_with_retry()` retries permanent `RPCError` subclasses

| Field | Value |
|-------|-------|
| **ID** | INT-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Classification** | advisory |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `monitor_forward.py:112-118` � `except (WorkerBusyTooLongRetryError, RPCError)` applies same retry logic to ALL `RPCError` subclasses
- Telethon error hierarchy: `RPCError` has permanent subclasses like `AuthKeyUnregisteredError`, `SessionExpiredError`, `UserIdInvalidError`, `PeerIdInvalidError` that will never succeed on retry
- Test `tests/test_monitor.py:436-449` uses generic `RPCError` and confirms all are retried, masking the issue

**Analysis:** The current implementation wastes backoff budget on errors that cannot be resolved by waiting. A dead session condition silently retries until exhaustion instead of being reported immediately.

**Architectural Impact:** MEDIUM � Delays failure detection, consumes resources on futile retries.

**Recommendation Stands:** Classify errors; only retry transient ones (`FloodWaitError`, `ServerError`, `TimedOut`).

### INT-004: Per-channel work launched via un-awaited `asyncio.create_task`; Telethon exceptions escape silently

| Field | Value |
|-------|-------|
| **ID** | INT-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Classification** | advisory |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `monitor.py:68` � `asyncio.create_task(reschedule_task(task, queue))` result never stored
- `monitor.py:126` � `asyncio.create_task(process_and_reschedule(...))` fire-and-forget pattern
- `monitor_forward.py:230-237` � `_fetch_messages` raises `TelegramServiceError` on RPCError
- `process_and_reschedule` line 57-68 has no try/except around `process_task` call

**Cross-Finding Relationship:** Duplicate of SRV-001/CLI-004 (channel dropped on exception). INT-004 correctly identifies the Telethon-specific manifestation but is fundamentally the same issue.

**Architectural Impact:** HIGH � Silent channel monitoring failures compromise operational reliability. Process supervisors cannot detect partial failures.

**Recommendation Stands:** See SRV-001/CLI-004 � wrap `process_task` in try/except and move `reschedule_task` to `finally`.

---

## Reclassified Findings

### INT-005: Dead/redundant `except TelegramServiceError` in `_fetch_messages()`

| Field | Value |
|-------|-------|
| **ID** | INT-005 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Status** | **RECLASSIFIED** (was BEST-PRACTICE) |

> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** This is a spec deviation because the code demonstrates intended layered error handling pattern (catch RPCError, re-raise TelegramServiceError, outer handler logs) that cannot function as designed due to Telethon never raising `TelegramServiceError`. The pattern is broken at the type level, not just a cleanup issue.
> - **See also:** INT-001, INT-002 � same exception-type mismatch pattern

**Evidence Verified:**
- `monitor_forward.py:206-242` � Try block contains only Telethon async iteration
- `monitor_forward.py:230-237` � `except RPCError` catches and immediately re-raises `TelegramServiceError(...)`
- `monitor_forward.py:239-241` � `except TelegramServiceError` would only catch a `TelegramServiceError` raised inside try, which Telethon never does
- `tests/test_monitor_forward.py:150-158` � Test mocks `TelegramServiceError` from `iter_messages`, confirming the branch exists only under artificial conditions

**Architectural Impact:** LOW � The unreachable branch adds confusion without runtime impact.

**Recommendation Stands:** Remove the unreachable `except TelegramServiceError` branch; raise once and let caller handle uniformly.

---

## Rejected Findings

### INT-006: `start_client()` has no 2FA/password or non-interactive code path for user accounts

| Field | Value |
|-------|-------|
| **ID** | INT-006 |
| **Severity** | MEDIUM |
| **Type** | ~~BEST-PRACTICE~~ [REJECTED] |
| **Status** | **REJECTED** |

> **Rejection reason:** Investigation shows the `is_user` flag correctly switches authentication mode. For 2FA accounts, Telethon raises `ValueError("Two-step verification is enabled...")` or `SessionPasswordNeededError` � these are Telethon-native behaviors, not missing project features. The operational requirement for first-run interactive login is inherent to user-account automation with 2FA. Adding a `password` field to `TelethonConfig` would create credential sprawl (api_hash, phone, password, bot_token) without strong ROI. **INT-001 (wrong exception types) must be fixed first** � currently 2FA errors crash the process anyway, so adding password support without fixing INT-001 would still crash. The finding conflates "feature missing" with "error handling broken." Fixing INT-001 makes 2FA errors detectable; the interactive-first-run requirement is documented by README note "Do not use your personal Telegram account for automation." Suggest documenting this limitation instead of adding password config.

**Evidence Verified:**
- `monitor_client.py:76-83` � No `code_callback` or `password` parameters passed to `client.start()`
- `core/telethon.py:168-198` � `TelethonConfig` has no `password` field
- README.md:269-270 warns "Do not use your personal Telegram account for automation"

---

## Cross-Finding Analysis

| Relationship | Detail |
|--------------|--------|
| **Same Root Cause** | INT-001, INT-002, INT-005 share the "exception type mismatch" root: Telethon raises its own exceptions, never the project's custom `TelegramAuthError`/`TelegramServiceError`. INT-005's dead branch is a direct consequence of this pattern. |
| **Duplicate Finding** | INT-004 duplicates SRV-001 and CLI-004 � same fire-and-forget task issue with same root cause and same fix. |
| **Dependency Chain** | INT-006 depends on INT-001: adding password support is pointless while real 2FA errors are not caught. |
| **Cross-Phase Conflict** | None. INT-004 aligns with SRV-001 (channel dropped on exception) and CLI-004 (un-awaited tasks). |

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 4 | INT-001, INT-002, INT-003, INT-004 |
| Reclassified | 1 | INT-005 |
| Rejected | 1 | INT-006 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| INT-006 | No 2FA/password support for user accounts | Operational requirement inherent to Telethon user auth; INT-001 must be fixed first; adds credential sprawl without ROI; existing README documentation covers limitation. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| INT-005 | BEST-PRACTICE | SPEC-DEVIATION | Dead code pattern reflects broken error-handling design, not just cleanup. |

---

## Required Fixes (Confirmed)

- **INT-001** (HIGH, SPEC-DEVIATION) � Critical: `start_client()` catches wrong exception types. Must fix before any other integrational changes.
- **INT-002** (MEDIUM, SPEC-DEVIATION) � `build_sender_tag()` exception handling unreachable.
- **INT-003** (MEDIUM, SPEC-DEVIATION) � Retry logic wastes resources on permanent errors.
- **INT-004** (MEDIUM, SPEC-DEVIATION) � Duplicate of SRV-001/CLI-004; see those findings for fix.

---

## Advisory Recommendations

- **INT-005** � Remove dead `except TelegramServiceError` branch in `_fetch_messages()`.

---

## Rollout Safety

1. **INT-001 must be implemented first** � all other exception-handling fixes depend on correct exception mapping.
2. **INT-003 should follow INT-001** � error classification requires knowing which errors are transient vs permanent.
3. **INT-004/SRV-001/CLI-004 are same issue** � fix once in `process_and_reschedule()`.
4. **No circular dependencies detected between findings.**
5. **Rollback feasibility:** Exception handling changes are localized; rollback is straightforward.

---

## Refinement Notes

- **INT-001** — Replaced ambiguous "or" recommendation with single actionable fix: catch Telethon exception hierarchy directly and map to project exceptions.
- **INT-002** — Recommendation unchanged (already singular).
- **INT-003** — Recommendation unchanged (already singular).
- **INT-004** — Recommendation unchanged (already singular).
- **INT-005** — Recommendation unchanged (already singular).
