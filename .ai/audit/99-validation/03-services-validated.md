---
name: 03-services-validated
description: Validated audit findings for Service Layer & Business Logic
validated: yes
validated_date: 2026-07-14
---

# Phase 03 Audit Findings - Service Layer & Business Logic

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** yes

---

## Findings

### SRV-001: Media captions excluded from keyword matching

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Verified in monitor_forward.py lines 174-178: text is extracted via `msg.message`, media is collected via `msg.media`, but media captions are never extracted for keyword matching. Messages with only media (no text) but with a caption containing keywords would not be forwarded. This is a real bug that limits functionality.
> - **See also:** —

**Description:** Messages with media (photos/videos) that have captions containing matching keywords are not forwarded if msg.message is empty. The process_messages function only collects msg.message for keyword matching text, ignoring msg.media.caption entirely.

**Evidence:**
- src/mko_telebot/monitor_forward.py:174-175: Only msg.message is collected for text
- src/mko_telebot/monitor_forward.py:177-178: Media is collected but caption is ignored
- tests/test_monitor.py:39 sets media.caption = None for testing

**Recommendation:** Include media captions in the keyword matching text by extracting msg.media.caption alongside msg.message.

---

### SRV-002: Empty keywords list prevents all forwarding

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** CRITICAL: Documentation at docs/11-guides/configuration.md:149 states "An empty list forwards all messages" but the implementation does the opposite. Line 183 in monitor_forward.py uses `any(search_match(msg_text, kw) for kw in task.keywords)` which returns False when keywords is empty. This is a SPEC-DEVIATION - code does not match documented behavior.
> - **See also:** —

**Description:** When a channel has an empty keywords list, any() on line 183 always evaluates to False, preventing all message forwarding.

**Evidence:**
- src/mko_telebot/monitor_forward.py:183: Uses any() on keywords list
- docs/11-guides/configuration.md:149: States "An empty list forwards all messages"
- Runtime: any(False for x in []) returns False

**Recommendation:** Either treat empty keywords as forward all or reject empty keywords during validation.

---

### SRV-003: Proxy types not using StrEnum as required by project rules

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/telethon.py |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** Merged
> - **Detail:** This finding duplicates CFG-001 from Phase 02 exactly. Same issue: proxy_type uses plain str instead of StrEnum. Merging into CFG-001 to avoid duplicate work.
> - **See also:** CFG-001 (Phase 02)

> **Merged into:** CFG-001 (Phase 02) - Proxy types not using StrEnum as required by project rules

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 1 |
| LOW | 0 |

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | SRV-001, SRV-002 |
| Reclassified | 0 | — |
| Merged | 1 | SRV-003 → CFG-001 |
| Rejected | 0 | — |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| — | — | — |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| SRV-003 | CFG-001 (Phase 02) | Duplicate finding: both identify the same proxy_type StrEnum violation in telethon.py. Keeping CFG-001 as the canonical reference. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | — |

---

## Cross-Phase Conflict Check

No cross-phase conflicts detected between Phase 03 findings and Phases 01-02 validated findings.

## Rollout Safety Assessment

All findings in this phase are isolated to `monitor_forward.py` or `telethon.py` with no identified dependency chains or rollout risks.