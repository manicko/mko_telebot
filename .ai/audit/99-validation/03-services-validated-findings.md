---
name: validated-findings
description: Phase 03 — Service Layer & Business Logic validated findings
agent: validator
status: complete
validated: yes
---

# Phase 03 Validated Findings — Service Layer & Business Logic

**Executor:** validator  
**Source:** .ai/audit/03-services/findings.md  
**Validation Date:** 2026-07-15

## Runtime Verification Summary

- **R1 Import:** Confirmed — all modules import cleanly.
- **R2 Lint/Type:** **CONFIRMED** — `ruff check` exits 0; `basedpyright` reports 43 warnings (reduced from 52), all type warnings are `reportExplicitAny` or Telethon-related. Exit code 1 due to warnings only.
- **R3 Tests:** 353 passed (confirmed via pytest).
- **R4 Dead code:** Confirmed — no dead top-level functions. SRV-006 `last_msg_id` parameter exists but is always overwritten by `load_state()`.

---

## Findings

### SRV-001: Channel is permanently dropped from monitoring on any exception in `process_task`

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Classification** | mandatory |

**Validation:** ✅ **CONFIRMED**

**Evidence Verified:**
- `monitor.py:57-68`: `process_task` is called inside `async with lock:` block with no try/except wrapper
- `monitor_forward.py:230-237`: `TelegramServiceError` is explicitly raised for non-flood RPC errors
- `monitor.py:126`: `process_and_reschedule` spawned via `asyncio.create_task` without awaiting or done-callback

**Architectural Impact:** Critical reliability issue. When `process_task` raises, the coroutine exits before `reschedule_task` is called, permanently removing that channel from monitoring.

**Recommendation:** Wrap `process_task` in try/except and reschedule in finally. This is a required fix.

---

### SRV-002: Fire-and-forget `asyncio.create_task` lacks supervision and shutdown handling

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Classification** | advisory |

**Validation:** ✅ **CONFIRMED**

**Evidence Verified:**
- `monitor.py:68`: `asyncio.create_task(reschedule_task(...))` — no reference stored, no done-callback
- `monitor.py:126`: `asyncio.create_task(process_and_reschedule(...))` — no reference stored
- `monitor.py:144-145`: `finally` only calls `client.disconnect()` without awaiting pending tasks

**Architectural Impact:** Without task tracking, exceptions in spawned tasks are only visible as "Task exception was never retrieved" warnings. Shutdown is not graceful for in-flight operations.

**Recommendation:** Maintain a set of spawned tasks and await them on shutdown with timeout.

---

### SRV-003: Captionless media-only messages are silently dropped, contradicting documented forwarding behavior

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Classification** | mandatory |

**Validation:** ✅ **CONFIRMED**

**Evidence Verified:**
- `monitor_forward.py:181-184`: Condition `if msg_text and (...)` skips when `msg_text == ""`
- `docs/00-overview/overview.md:81`: "Keyword matching is evaluated against both the message body and the media caption."
- `docs/00-overview/overview.md:88`: "Media handling — Messages with media (including albums) are forwarded intact"
- `tests/test_monitor.py:669-673`: Test `test_skips_messages_without_text` asserts messages without text are skipped (note: test uses no media)

**Analysis:** The code condition `if msg_text and (not task.keywords or any(...))` means:
1. When `msg_text == ""` (no text, no caption), the condition is False, skipping forward
2. Media with a caption is handled correctly (caption goes into `msg_text` via `_group_messages_by_album` line 69)
3. There is no test covering media-only with empty keywords (would expose the spec-deviation)

**Recommendation:** Update `process_messages` to forward captionless media when `keywords` is empty: change condition to `(msg_text and keyword_match) or (content["media"] and not task.keywords)`.

---

### SRV-004: `search_match` swallows all parse/runtime errors and silently disables a misconfigured keyword

| Field | Value |
|-------|-------|
| **ID** | SRV-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Classification** | advisory |

**Validation:** ✅ **CONFIRMED**

**Evidence Verified:**
- `matcher.py:172-182`: Broad `except Exception` returns `False` after logging
- No keyword validation at config load time in `TelepostConfigReader.validate()` or Pydantic validators

**Architectural Impact:** Misspelled or malformed keywords in config silently fail to match, undermining trust in filtering. The project rule "never silently swallow errors" applies — this should fail at startup.

**Recommendation:** Validate keywords at config-load time via Pydantic validator in `ChannelConfig`.

---

### SRV-005: Type-safety degradation in the service layer (`Any`/`Unknown` leakage)

| Field | Value |
|-------|-------|
| **ID** | SRV-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Classification** | advisory |

**Validation:** ✅ **CONFIRMED**

**Evidence Verified:**
- `monitor_forward.py:42`: `dict[int | None, dict[str, Any]]` return type explicit
- `monitor_forward.py:78`: `list[Any] | None` parameter type explicit
- `monitor_forward.py:126`: `list[Any]` parameter explicit
- All `reportExplicitAny` warnings are generated by these explicit annotations
- Telethon's missing type stubs compound the issue but the explicit `Any` is a valid concern

**Architectural Impact:** Low severity. The `Any` types prevent static checking of the message pipeline. Recommendation to use TypedDict or narrow types is valid but requires Telethon stub analysis.

**Recommendation:** Consider TypedDict for message grouping or add `# pyright: ignore` surgically if types are unavoidable.

---

### SRV-006: Redundant `Task.__init__(last_msg_id=...)` seeding path never used by callers

| Field | Value |
|-------|-------|
| **ID** | SRV-006 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Classification** | advisory |

**Validation:** ✅ **CONFIRMED**

**Evidence Verified:**
- `task.py:48`: `last_msg_id: int = 0` parameter exists
- `task.py:63`: `self.last_msg_id = last_msg_id or 0` initializes from parameter
- `task.py:166`: `self.last_msg_id = max(self.last_msg_id, state.get("last_id", 0))` overwrites on load
- `monitor.py:104`: `Task(config=channel_settings)` omits the parameter

**Architectural Impact:** Low. The parameter provides future flexibility for test seeding or state recovery, but introduces ambiguity. The parameter is not currently used.

**Recommendation:** Either document the intended use or remove. Keep as advisory.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 6 | SRV-001, SRV-002, SRV-003, SRV-004, SRV-005, SRV-006 |
| Reclassified | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None.

### Cross-Phase Conflicts

None detected.

### Rollout Safety Issues

None detected at validation time.

---

## Required Fixes (Confirmed)

- **SRV-001** — Wrap `process_task` call in `process_and_reschedule` with try/finally to ensure channel rescheduling on all error paths.
- **SRV-003** — Update `process_messages` to forward captionless media when `keywords` is empty (change condition to check `content["media"]` when no keywords).

---

## Advisory Recommendations

- **SRV-002** — Supervise fire-and-forget tasks and await them on shutdown (MEDIUM).
- **SRV-004** — Validate keyword syntax at config load instead of silently disabling bad keywords at runtime (MEDIUM).
- **SRV-005** — Consider TypedDict for message grouping to narrow `Any` types (LOW).
- **SRV-006** — Confirm or remove the unused `last_msg_id` constructor seed (LOW).

---

## Doc Updates Needed

- **SRV-003** — `docs/00-overview/overview.md` (lines 81, 88, 125) states media/albums are *"forwarded intact"*, but code currently drops captionless media-only posts. Update docs or code to align.