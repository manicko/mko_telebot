---
name: 03-services-audit-findings
description: Audit findings for service layer and business logic phase
agent: auditor
status: complete
validated: no
---

# Phase 03 Audit Findings — Service Layer & Business Logic

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### SRV-001: Task class violates single responsibility principle with embedded business logic

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** The `Task` class in `core/task.py` violates the single responsibility principle by combining configuration data with business logic. According to the audit spec (lines 127-130), Task should be "a data container (dataclass), not a service." However, the current implementation has:
- `resolve_targets_entities()` — Telegram API entity resolution logic
- `resolve_channel_entity()` — Telegram API entity resolution logic  
- `resolve_state_file()` — File system operations
- `set_offset_date()` — Date computation logic
- `load_state()` / `save_state()` — State persistence logic

This creates tight coupling between the Task model and external services (Telethon client, file system), making testing harder and violating the data/model separation guideline. The Task class should only hold data, with resolution and persistence logic moved to a dedicated service.

**Evidence:**
- `task.py` lines 63-78: `resolve_targets_entities()` contains Telegram API resolution with error handling
- `task.py` lines 80-90: `resolve_channel_entity()` contains Telegram API resolution with error handling
- `task.py` lines 92-106: `resolve_state_file()` contains file system path operations
- `task.py` lines 126-159: State persistence methods with file I/O

**Recommendation:** Refactor Task to be a pure Pydantic BaseModel/dataclass with only data attributes. Move entity resolution methods to a `TelegramService` class and state persistence to a dedicated `StateStore` class. This separates concerns and follows the pattern established in docs/00-overview/overview.md where Task is described as "Per-channel state management" but the implementation exceeds that scope.

**Effort:** medium
**Priority:** recommended

---

### SRV-002: Task model missing documented fields (chat_id, topic_id, text, photos, count, max_count)

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** According to the audit spec (lines 127-129), Task should carry "all required data: chat_id, topic_id, text, photos, chat_name, count, max_count." The current Task implementation (lines 24-61) has `channel_name`, `forward_to`, `keywords`, `scan_interval`, `history_limit`, `history_days`, `overlap`, `last_msg_id`, but is missing:
- `chat_id` (different from channel_name)
- `topic_id` (for Telegram forum topics)
- `text` (message content)
- `photos` (media attachments)
- `count` (processing count)
- `max_count` (limit for processing)

The Task as currently implemented serves a different purpose than what the spec describes — it's for channel monitoring configuration rather than message/post data. This is a functional mismatch in naming/expectation.

**Evidence:**
- Audit spec lines 127-129: Lists expected Task fields including chat_id, topic_id, text, photos, count, max_count
- `task.py` lines 45-61: Actual Task attributes — no chat_id, topic_id, text, photos, count, max_count

**Recommendation:** Either update the audit spec to match the actual Task purpose (configuration state), or refactor Task to include the documented fields if they represent the intended design. Based on the actual codebase usage, Task appears to be a channel monitoring configuration holder, not a message container.

**Effort:** small
**Priority:** recommended

---

### SRV-003: Missing status field for Task tracking

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** The audit spec requires "Task status tracking" with a status field (line 128), but the current Task implementation has no status field. The spec states Task should track success/failure status, but this functionality is absent.

**Evidence:**
- Audit spec line 128: "Task status tracking — Task has a status field to track success/failure."
- `task.py` lines 23-61: No status field defined in Task class

**Recommendation:** Add a status field to Task using a StrEnum to track processing states (PENDING, PROCESSING, COMPLETED, FAILED). This provides visibility into task execution status for debugging and monitoring.

**Effort:** small
**Priority:** recommended

---

### SRV-004: Missing forum topic support (topic_id) in message forwarding

| Field | Value |
|-------|-------|
| **ID** | SRV-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor_forward.py, src/mko_telebot/core/channels.py |
| **Classification** | advisory |

**Description:** The audit spec requires "Topic/forum support — topic_id is passed correctly to send_message and send_file for forum topics" (line 119), but neither `monitor_forward.py` nor `channels.py` has any `topic_id` field or handling. The current implementation forwards messages to targets but cannot specify a forum topic within a chat.

**Evidence:**
- Audit spec line 119: "Topic/forum support — topic_id is passed correctly to send_message and send_file for forum topics."
- `monitor_forward.py` lines 71-76: `send_message` and `send_file` calls have no topic_id parameter
- `channels.py` ChannelConfig: No topic_id field defined

**Recommendation:** Add `topic_id` field to `ChannelConfig` and `Task`, and pass it to `send_message` and `send_file` calls when forwarding. Telethon supports forum topics via the `topic_id` parameter.

**Effort:** small
**Priority:** recommended

---

### SRV-005: Missing service classes referenced in audit spec

| Field | Value |
|-------|-------|
| **ID** | SRV-005 |
| **Severity** | MEDIUM |
| **Type** | DOC-UPDATE |
| **Affected Modules** | .kilo/commands/audit/phases/03-audit-services.md |
| **Classification** | advisory |

**Description:** The audit spec explicitly lists service classes to audit (line 63): "Service classes (TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader)". However, none of these classes exist in the codebase. The current codebase has a simpler architecture with just Task, monitor_forward, monitor_client, and monitor modules. This indicates the spec references an outdated/larger design that was never implemented.

**Evidence:**
- Audit spec line 63: Lists TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader
- Codebase grep search for these class names returns no matches
- Current architecture uses `monitor_forward.py` for message processing and forwarding
- Current architecture has no Google Sheets integration (GSheetsReader)
- Current architecture has no image caching or processing (ImageCache)

**Recommendation:** Update the audit spec to accurately reflect the actual service architecture: message processing logic in `monitor_forward.py`, client wrapper in `monitor_client.py`, and channel configuration Task in `core/task.py`. If these features are intended for future versions, document them as future work.

**Effort:** small
**Priority:** recommended

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 4 |
| LOW | 0 |

## Advisory Recommendations

- SRV-001: Task class violates single responsibility principle with embedded business logic (HIGH priority)
- SRV-002: Task model missing documented fields (chat_id, topic_id, text, photos, count, max_count) (MEDIUM priority)
- SRV-003: Missing status field for Task tracking (MEDIUM priority)
- SRV-004: Missing forum topic support (topic_id) in message forwarding (MEDIUM priority)
- SRV-005: Missing service classes referenced in audit spec (MEDIUM priority)

## Doc Updates Needed

- SRV-005: Update audit spec to reflect actual service architecture (monitor_forward.py, monitor_client.py, Task)