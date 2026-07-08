---
name: 03-services-findings
description: Service Layer & Business Logic Audit Findings
agent: auditor
status: complete
validated: no
---

# Phase 03 Audit Findings — Service Layer & Business Logic

**Executor:** auditor
**Template:** `.ai/audit/templates/audit-findings.md`
**Status:** complete
**Validated:** no

---

## Findings

### SRV-001: Task class violates Single Responsibility by mixing data, state persistence, and entity resolution

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | mandatory |

**Description:** The `Task` class simultaneously serves three distinct responsibilities: (1) holding configuration state (channel_name, keywords, scan_interval), (2) resolving Telegram entities (resolve_targets_entities, resolve_channel_entity), and (3) managing persistent state (load_state, save_state, resolve_state_file). According to the audit checklist, "Task is a data container (dataclass), not a service." This mixing of concerns makes the class harder to test and maintain.

**Evidence:**
- `task.py` line 61-76: `resolve_targets_entities` contains Telegram client API calls
- `task.py` line 78-88: `resolve_channel_entity` contains Telegram client API calls
- `task.py` line 90-104: `resolve_state_file` contains filesystem I/O
- `task.py` lines 125-158: `load_state` and `save_state` contain async file I/O

**Recommendation:** Refactor Task to be a pure Pydantic dataclass with no methods. Move entity resolution to a separate service class (e.g., `TelegramResolver`). Move state persistence to a separate repository/service (e.g., `StateManager`). Effort: large — architectural restructuring required.

---

### SRV-002: Missing return type hints on public methods violate project coding standards

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Type** | SPEC-DEVIATION |
| **Severity** | MEDIUM |
| **Affected Modules** | src/mko_telebot/core/task.py, src/mko_telebot/monitor.py |
| **Classification** | mandatory |

**Description:** The project rules mandate "Type hints on all public functions." Several public methods lack return type annotations, including `Task.resolve_state_file()` and `monitor.build_message_link()`.

**Evidence:**
- `task.py` line 90: `def resolve_state_file(self):` — no return type hint
- `monitor.py` line 72: `def build_message_link(msg):` — no return type hint  
- `monitor.py` line 343: `def launcher():` — no return type hint

**Recommendation:** Add explicit return type hints to all public methods. `resolve_state_file` returns `None`; `build_message_link` returns `str | None`; `launcher` returns `None`. Effort: trivial.

---

### SRV-003: Audit phase references non-existent services (TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader)

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Type** | SPEC-DEVIATION |
| **Severity** | HIGH |
| **Affected Modules** | Audit phase specification |
| **Classification** | mandatory |

**Description:** The audit phase specification (lines 63, 98, 111, 121) explicitly audits services `TelegramService`, `PostProcessor`, `ImageCache`, `TelegramPoster`, and `GSheetsReader` that do not exist in the codebase. The project README describes "monitoring Telegram channels for new messages matching your keywords and forwards them automatically" — there is no Google Sheets integration. The actual codebase uses `Task` and module-level functions in `monitor.py` for Telegram operations. This indicates either the audit phase was copied from a different project or the services were planned but never implemented.

**Evidence:**
- Grep search for `class (TelegramService|PostProcessor|ImageCache|TelegramPoster|GSheetsReader)` returns no class definitions
- Grep search for `gspread|google|sheet` returns no results
- README describes a Telegram channel monitor, not Google Sheets publishing
- `monitor.py` uses functions like `forward_to_users`, `process_messages`, `process_task` instead of service classes

**Recommendation:** Update audit phase documentation to reflect actual codebase architecture. Either (a) remove these service checks if the project genuinely has no Google Sheets integration, or (b) document that these services are not yet implemented. Effort: trivial (documentation update).

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- SRV-001: Task class violates Single Responsibility by mixing data, state persistence, and entity resolution
- SRV-003: Audit phase references non-existent services (TelegramService, PostProcessor, ImageCache, TelegramPoster, GSheetsReader)

## Advisory Recommendations

- SRV-002: Missing return type hints on public methods violate project coding standards

## Doc Updates Needed

- SRV-003: Audit phase specification should document actual services or remove non-existent service checks

---