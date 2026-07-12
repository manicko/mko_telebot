---
name: 03-services-validated
description: Validated audit findings for Service Layer & Business Logic
agent: validator
status: complete
validated: yes
---

# Phase 03 Validated Audit Findings — Service Layer & Business Logic

**Executor:** validator  
**Source:** .ai/audit/03-services/findings.md  
**Status:** complete  
**Validated:** yes

---

## Findings

### SRV-001: ~~Task class violates single responsibility principle with embedded business logic~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

> **Rejection reason:** The audit spec references an architecture with `TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader` — a design for Google Sheets integration that does not exist in this codebase. The current Task class follows the documented purpose in docs/00-overview/overview.md: "Per-channel state management." Task combines config data (from ChannelConfig) with entity resolution and state persistence, which is the intended design for this Telegram-only monitor. The spec describes a different architecture entirely.

**Description:** The `Task` class in `core/task.py` violates the single responsibility principle by combining configuration data with business logic. According to the audit spec (lines 127-130), Task should be "a data container (dataclass), not a service." However, the current implementation has:
- `resolve_targets_entities()` — Telegram API entity resolution logic
- `resolve_channel_entity()` — Telegram API entity resolution logic  
- `resolve_state_file()` — File system operations
- `set_offset_date()` — Date computation logic
- `load_state()` / `save_state()` — State persistence logic

This creates tight coupling between the Task model and external services (Telethon client, file system), making testing harder and violating the data/model separation guideline. The Task class should only hold data, with resolution and persistence logic moved to a dedicated service.

---

### SRV-002: ~~Task model missing documented fields (chat_id, topic_id, text, photos, count, max_count)~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

> **Rejection reason:** The audit spec fields (chat_id, topic_id, text, photos, count, max_count) describe a message/post container for Google Sheets integration. The actual `Task` class in this codebase is for channel monitoring configuration and state, as documented in overview.md. No spec, documentation, or config model references these fields. The current Task attributes (channel_name, forward_to, keywords, scan_interval, history_limit, overlap, last_msg_id) correctly serve the channel monitoring use case.

**Description:** According to the audit spec (lines 127-129), Task should carry "all required data: chat_id, topic_id, text, photos, chat_name, count, max_count." The current Task implementation (lines 24-61) has `channel_name`, `forward_to`, `keywords`, `scan_interval`, `history_limit`, `history_days`, `overlap`, `last_msg_id`, but is missing:
- `chat_id` (different from channel_name)
- `topic_id` (for Telegram forum topics)
- `text` (message content)
- `photos` (media attachments)
- `count` (processing count)
- `max_count` (limit for processing)

The Task as currently implemented serves a different purpose than what the spec describes — it's for channel monitoring configuration rather than message/post data. This is a functional mismatch in naming/expectation.

---

### SRV-003: ~~Missing status field for Task tracking~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

> **Rejection reason:** No specification, documentation, or config model in this codebase references a status field for Task. The audit spec requirement is from a design that doesn't match the actual project. The Task uses `last_msg_id` for state tracking, which is sufficient for the channel monitoring use case. Adding a status field would be speculative complexity without clear operational value.

**Description:** The audit spec requires "Task status tracking" with a status field (line 128), but the current Task implementation has no status field. The spec states Task should track success/failure status, but this functionality is absent.

---

### SRV-004: ~~Missing forum topic support (topic_id) in message forwarding~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | SRV-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Classification** | advisory |

> **Rejection reason:** While `topic_id` is a valid enhancement for Telegram forum topics, this feature is not documented in any project specification or configuration model. The current architecture works correctly for basic Telegram channel forwarding. Adding forum support would be an enhancement, not a spec deviation. The ROI is negative at this project scale — the feature doesn't exist in the product requirements.

**Description:** The audit spec requires "Topic/forum support — topic_id is passed correctly to send_message and send_file for forum topics" (line 119), but neither `monitor_forward.py` nor `channels.py` has any `topic_id` field or handling. The current implementation forwards messages to targets but cannot specify a forum topic within a chat.

---

### SRV-005: Audit spec describes non-existent Google Sheets integration architecture

| Field | Value |
|-------|-------|
| **ID** | SRV-005 |
| **Severity** | MEDIUM |
| **Type** | DOC-UPDATE |
| **Affected Modules** | .kilo/commands/audit/phases/03-audit-services.md |
| **Classification** | advisory |

**Description:** The audit spec explicitly lists service classes that audit (line 63): "Service classes (TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader)". However, none of these classes exist in the codebase. The current codebase has a simpler architecture with just Task, monitor_forward, monitor_client, and monitor modules. This indicates the spec references an outdated/larger design that was never implemented.

**Evidence:**
- Audit spec line 63: Lists TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader
- Codebase grep search returns no matches for these class names
- Current architecture uses `monitor_forward.py` for message processing and forwarding
- Current architecture has no Google Sheets integration (GSheetsReader)
- Current architecture has no image caching or processing (ImageCache)
- docs/00-overview/overview.md confirms: Task is "Per-channel state management," no mention of Google Sheets

**Recommendation:** Update the audit spec to accurately reflect the actual service architecture: message processing logic in `monitor_forward.py`, client wrapper in `monitor_client.py`, and channel configuration Task in `core/task.py`. The Google Sheets integration appears to be from a different project scope.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- None

## Advisory Recommendations

- SRV-005: Update audit spec to reflect actual service architecture (MEDIUM priority)

## Doc Updates Needed

- SRV-005: Update audit spec to document actual architecture (Task, monitor_forward, monitor_client) without references to non-existent services

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | SRV-005 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 4 | SRV-001, SRV-002, SRV-003, SRV-004 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| SRV-001 | Task class violates single responsibility principle | Spec describes Google Sheets architecture; actual code follows overview.md "Per-channel state management" |
| SRV-002 | Task model missing documented fields | Spec fields describe message containers; Task is channel config holder per actual design |
| SRV-003 | Missing status field for Task tracking | No spec/config/doc references this field; last_msg_id sufficient for use case |
| SRV-004 | Missing forum topic support (topic_id) | Feature enhancement, not spec requirement; no product requirement for forum support |

### Merged Findings

- None

### Reclassified Findings

- None

---

## Implementation Recommendations for SRV-005: Audit Spec Update

The audit spec at `.kilo/commands/audit/phases/03-audit-services.md` requires the following specific changes to reflect the actual architecture documented in `docs/00-overview/overview.md`:

### Change 1: Update Service Classes Line (Line 63)

**Current:**
```markdown
Service classes (TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader), Task model, business logic, data transformations.
```

**Replace with:**
```markdown
Task model, message processing functions in monitor_forward.py, client wrapper in monitor_client.py, and monitoring orchestration in monitor.py.
```

### Change 2: Update Single Responsibility Checks (Lines 73-76)

**Current:**
```markdown
| Each class has one reason to change | `ImageCache` handles only image caching. `PostProcessor` handles only post extraction. `TelegramPoster` handles only Telegram API communication. |
| No god classes | No single class handles config loading, data fetching, image processing, AND posting. |
| Separation of concerns | Image processing is separate from post processing, which is separate from Telegram communication. |
```

**Replace with:**
```markdown
| Each module has focused functions | `monitor_forward.py` handles message processing and forwarding logic only. `monitor_client.py` handles client creation and authentication only. `monitor.py` handles orchestration (loop, scheduling) only. |
| No god modules | No single module handles config loading, message processing, AND client management. |
| Separation of concerns | Entity resolution in Task, message processing in monitor_forward, client management in monitor_client. |
```

### Change 3: Remove Image Processing Dimension (Lines 87-98)

**Delete lines 87-98 entirely** — The "Image Processing Correctness" dimension describes ImageCache which does not exist in this codebase.

### Change 4: Update Post Processing Correctness (Lines 100-109)

**Current:**
```markdown
### 4. Post Processing Correctness

| Check | Description |
|-------|-------------|
| Filter logic is correct | Rows are filtered by the configured column and value. Rows where the filter column is out of range are included (not silently dropped). |
| Photo extraction handles both cases | Photo column content is handled whether it is a directory path (multiple photos) or a single file path. |
| Max photos limit is enforced | `max_photos` is applied to limit the number of photos per post. |
| Empty posts handled | Posts with no text and no photos are handled gracefully (not sent as empty messages). |
```

**Replace with:**
```markdown
### 4. Message Processing Correctness

| Check | Description |
|-------|-------------|
| Keyword filter logic is correct | Messages are filtered by configured keyword patterns. Album messages are grouped by grouped_id before keyword check. |
| Media handling is correct | Messages with media (including albums) are correctly identified and forwarded. |
| Duplicate prevention | Messages with id <= last_msg_id are skipped to prevent re-forwarding. |
| Empty messages handled | Messages with no text and no media are skipped (early return in process_messages). |
```

### Change 5: Update Telegram Posting Checks (Lines 111-120)

**Current:**
```markdown
### 5. Telegram Posting Correctness

| Check | Description |
|-------|-------------|
| Retry logic works | `FloodWaitError`, `SlowModeWaitError`, and other transient errors trigger retries with appropriate backoff. |
| Non-retryable errors fail fast | Permanent errors (e.g., chat not found) do not trigger infinite retries. |
| Posts are shuffled | Post order is randomized before sending (if configured). |
| Delay between posts is respected | `delay_minutes` is converted to seconds and applied between posts. |
| Topic/forum support | `topic_id` is passed correctly to `send_message` and `send_file` for forum topics. |
```

**Replace with:**
```markdown
### 5. Forwarding Correctness

| Check | Description |
|-------|-------------|
| Retry logic works | `FloodWaitError` and `RPCError` trigger retries with exponential backoff and jitter. |
| Non-retryable errors fail fast | Errors after max_retries are logged and task continues to next target. |
| Delay between targets is respected | Random delay (5-10s) between target deliveries prevents rate limiting. |
| Source link and sender included | Forwarded messages include t.me link and sender attribution. |
```

### Change 6: Update Task Model Integrity (Lines 123-131)

**Current:**
```markdown
### 6. Task Model Integrity

| Check | Description |
|-------|-------------|
| Task carries all required data | The `Task` model includes chat_id, topic_id, text, photos, chat_name, count, max_count. |
| Task status tracking | Task has a status field to track success/failure. |
| No business logic in Task | Task is a data container (dataclass), not a service. |
```

**Replace with:**
```markdown
### 6. Task Model Integrity

| Check | Description |
|-------|-------------|
| Task carries all required data | The `Task` model includes channel_name, forward_to, keywords, scan_interval, history_limit, history_days, overlap, last_msg_id, offset_date, state_file. |
| Task state tracking | Task tracks last_msg_id for duplicate prevention and offset_date for time-windowed scans. |
| Entity resolution integrated | Task includes entity resolution methods (resolve_channel_entity, resolve_targets_entities) as per overview.md design. |
```

### Change 7: Update Evidence Requirements (Lines 77, 87)

**For Single Responsibility (Line 77), update:**
```markdown
**Evidence required:** Read each service class...
```
to:
```markdown
**Evidence required:** Read monitor_forward.py, monitor_client.py, monitor.py. Verify each module has focused functions without cross-cutting concerns.
```

**For Post Processing (Line 109), update:**
```markdown
**Evidence required:** Read `PostProcessor.get_posts()`...
```
to:
```markdown
**Evidence required:** Read `process_messages()` and `forward_to_users()` in monitor_forward.py. Verify keyword matching, album grouping, and retry logic.
```

### Change 8: Update Evidence Requirements (Lines 121)

**For Telegram Posting (Line 121), update:**
```markdown
**Evidence required:** Read `TelegramPoster` and the posting loop.
```
to:
```markdown
**Evidence required:** Read `forward_to_users()` in monitor_forward.py. Verify FloodWaitError and RPCError handling, exponential backoff, and caption assembly.
```