# Phase 03 Audit Findings - Service Layer & Business Logic

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

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

**Description:** Messages with media (photos/videos) that have captions containing matching keywords are not forwarded if msg.message is empty. The process_messages function only collects msg.message for keyword matching text, ignoring msg.media.caption entirely.

**Evidence:**
- src/mko_telebot/monitor_forward.py:174-175: Only msg.message is collected for text
- src/mko_telebot/monitor_forward.py:177-178: Media is collected but caption is ignored
- tests/test_monitor.py:39 sets media.caption = None for testing

**Recommendation:** Include media captions in the keyword matching text by extracting msg.media.caption alongside msg.message.

### SRV-002: Empty keywords list prevents all forwarding

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | mandatory |

**Description:** When a channel has an empty keywords list, any() on line 183 always evaluates to False, preventing all message forwarding.

**Evidence:**
- src/mko_telebot/monitor_forward.py:183: Uses any() on keywords list
- Runtime: any(False for x in []) returns False

**Recommendation:** Either treat empty keywords as forward all or reject empty keywords during validation.

### SRV-003: Proxy types not using StrEnum as required by project rules

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/telethon.py |
| **Classification** | advisory |

**Description:** proxy_type field uses plain str with validator instead of StrEnum per project rule #10.

**Evidence:**
- src/mko_telebot/core/telethon.py:26: proxy_type: str = Field(...)
- src/mko_telebot/core/telethon.py:45-46: valid_types = set of strings

**Recommendation:** Create ProxyType StrEnum for proxy_type field.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- SRV-001: Media captions excluded from keyword matching
- SRV-002: Empty keywords list prevents all forwarding

## Advisory Recommendations

- SRV-003: Proxy types not using StrEnum as required by project rules
