---
name: 03-services-findings
description: Service Layer & Business Logic audit findings
agent: auditor
alwaysApply: false
---

# Phase 03 Audit Findings — Service Layer & Business Logic

**Executor:** auditor  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** complete  
**Validated:** no

---

## Findings

### SRV-001: Task class contains business logic methods, violating single responsibility

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | mandatory |

**Description:** The `Task` class in `core/task.py` is documented as a "pure data container (dataclass)" in the audit specification (lines 129-130), but the actual implementation includes multiple async methods that perform significant business logic: `resolve_targets_entities`, `resolve_channel_entity`, `resolve_state_file`, `load_state`, and `save_state`. This violates the single responsibility principle - `Task` serves both as a data holder and as an entity responsible for Telethon API resolution and file I/O operations.

**Evidence:**
- `core/task.py:61-76` - `resolve_targets_entities` performs async Telethon API calls (`client.get_entity`)
- `core/task.py:78-88` - `resolve_channel_entity` performs async Telethon API calls
- `core/task.py:90-104` - `resolve_state_file` performs filesystem operations with `utils.ensure_path_exists`
- `core/task.py:125-142` - `load_state` performs async file I/O with `aiofiles`
- `core/task.py:146-157` - `save_state` performs async file I/O with `aiofiles`
- The class is NOT a dataclass (no `@dataclass` decorator), confirming it was intended to be a data model

**Recommendation:** Extract the entity resolution and state persistence logic into separate service classes (e.g., `EntityResolver`, `StateManager`) or keep them as module-level functions. The `Task` class should remain a pure data container with attributes only. Effort: medium.

---

### SRV-002: set_offset_date method has redundant self-assignment and returns value unnecessarily

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** The `set_offset_date` method in `Task` class has two issues: (1) it redundantly assigns to `self.offset_date` both in the method body and via return value assignment in `__init__`, and (2) it returns the value even though the return value is never used meaningfully. The `__init__` calls `self.offset_date = self.set_offset_date()` at line 56, but `set_offset_date` already sets `self.offset_date` internally at line 118.

**Evidence:**
- `core/task.py:56` - `self.offset_date = self.set_offset_date()` - assigns return value to same attribute
- `core/task.py:108-118` - `set_offset_date` sets `self.offset_date = None` and later `self.offset_date = datetime.now(UTC) - timedelta(days=days)`
- `core/task.py:122` - Returns `self.offset_date` which is immediately reassigned by caller

**Recommendation:** Either return the value and remove the internal assignment, or remove the return and just keep internal assignment. The current dual assignment is confusing and error-prone. Effort: trivial.

---

### SRV-003: Referenced service classes (ImageCache, TelegramPoster, GSheetsReader, PostProcessor) do not exist in codebase

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py (missing classes), .kilo/commands/audit/phases/03-audit-services.md |
| **Classification** | mandatory |

**Description:** The audit specification explicitly references five service classes that do not exist in the codebase:
- `ImageCache` - documented as handling image caching and resizing (references at lines 63, 73, 93-96)
- `TelegramPoster` - documented as handling Telegram API communication (references at lines 63, 115-121)
- `GSheetsReader` - documented as Google Sheets integration (references at lines 63, 27)
- `PostProcessor` - documented for post extraction (references at lines 63, 100-109, 28)
- `TelegramService` - documented for main service orchestration (references at line 28)

The current architecture has a `monitor.py` module with procedural functions instead of these service classes.

**Evidence:**
- `.kilo/commands/audit/phases/03-audit-services.md:63` - Lists "TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader" as service classes
- `.kilo/commands/audit/phases/03-audit-services.md:73` - Checks `ImageCache handles image caching only`
- `.kilo/commands/audit/phases/03-audit-services.md:93-96` - References `ImageCache.resize_image()`, `cleanup_unused()`, cache key determinism
- `.kilo/commands/audit/phases/03-audit-services.md:115-121` - Checks `TelegramPoster` retry logic, delay handling
- `grep` search for `class ImageCache`, `class TelegramPoster`, `class GSheetsReader`, `class PostProcessor`, `class TelegramService` in `src/` returns no matches
- `src/mko_telebot/monitor.py` contains only standalone functions: `create_client`, `start_client`, `build_message_link`, `build_sender_tag`, `forward_to_users`, `process_messages`, `process_task`, `reschedule_task`, `process_and_reschedule`, `main_loop`, `run_monitor`

**Recommendation:** Either implement the documented service architecture (extract classes from monitor.py) or update the specification documents to accurately reflect the current procedural architecture. The current code works but doesn't match the documented design. Effort: large (re-architecture) or medium (documentation update).

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- SRV-001: Task class contains business logic methods, violating single responsibility
- SRV-003: Referenced service classes (ImageCache, TelegramPoster, GSheetsReader, PostProcessor) do not exist in codebase

## Advisory Recommendations

- SRV-002: set_offset_date method has redundant self-assignment and returns value unnecessarily

---