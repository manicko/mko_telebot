---
name: 03-services-validated
description: Validated audit findings for Service Layer & Business Logic
agent: validator
status: validated
validated: yes
---

# Phase 03 Audit Findings — Service Layer & Business Logic (Validated)

**Executor:** auditor
**Validator:** validator
**Status:** validated
**Validated:** yes

---

## Findings

### SRV-001: ~~Task class contains business logic methods, violating single responsibility~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | mandatory |

> **Rejection reason:** The audit specification incorrectly assumes Task should be a pure dataclass based on generic rules, but the actual Task implementation and project architecture are aligned. The project overview (overview.md) documents Task as "Per-channel state management and entity resolution", which matches the implemented methods. The Task class follows composition pattern where it owns its lifecycle operations (entity resolution for its channel, state persistence for its run). Separating these would add unnecessary indirection without clear benefit for this project scale. The code works correctly and matches the documented architecture in docs/00-overview/overview.md.

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
- `core/task.py:106-122` - `set_offset_date` sets `self.offset_date = None` at line 108, then `self.offset_date = datetime.now(UTC) - timedelta(days=days)` at line 118, and returns at line 122
- `core/task.py:122` - Returns `self.offset_date` which is immediately reassigned by caller

**Recommendation:** Either return the value and remove the internal assignment, or remove the return and just keep internal assignment. The current dual assignment is confusing and error-prone. Effort: trivial.

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed the redundant assignment pattern. Method sets `self.offset_date` internally (lines 108, 118) while also returning it for assignment in `__init__` (line 56). This is a minor code quality issue that doesn't affect functionality but introduces cognitive overhead. The code works correctly but could be simplified.
> - **See also:** —

---

### SRV-003: ~~Referenced service classes (ImageCache, TelegramPoster, GSheetsReader, PostProcessor) do not exist in codebase~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py (missing classes), .kilo/commands/audit/phases/03-audit-services.md |
| **Classification** | mandatory |

> **Rejection reason:** The audit specification references ImageCache, TelegramPoster, GSheetsReader, PostProcessor, and TelegramService classes that are irrelevant to this project's actual scope. This project is a "Telegram classified monitor" for keyword-based message monitoring and forwarding - it has no Google Sheets integration, no image caching/resizing requirements, and no "post extraction" pipeline. The audit specification appears to describe a different project (possibly a poster/scheduler application) and does not apply to mko_telebot. The current procedural architecture in monitor.py correctly implements the documented functionality in docs/00-overview/overview.md (lines 36-37, 52-73). No specification or model references these classes.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 0 |

---

## Advisory Recommendations

- SRV-002: set_offset_date method has redundant self-assignment and returns value unnecessarily

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | SRV-002 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 2 | SRV-001, SRV-003 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| SRV-001 | Task class contains business logic methods, violating single responsibility | Audit spec assumes pure dataclass but project overview documents Task as "Per-channel state management and entity resolution" - the implementation matches documented architecture |
| SRV-003 | Referenced service classes (ImageCache, TelegramPoster, GSheetsReader, PostProcessor) do not exist in codebase | Audit spec describes features irrelevant to this project (Google Sheets, image caching, post extraction); current procedural architecture in monitor.py correctly implements documented functionality |

### Reclassified Findings

No findings reclassified.

### Architectural Observations

1. **Audit specification misalignment**: The Phase 03 audit specification (03-audit-services.md) references service classes and features that do not apply to mko_telebot's actual scope. This caused two findings to be flagged that are not relevant to the current codebase.

2. **Working architecture**: The current Task class appropriately owns its lifecycle operations (entity resolution, state persistence). This is a valid architectural choice for a monitoring tool where tasks need to manage their own state.

3. **Minor code quality issue**: SRV-002 identifies a real but low-impact code redundancy in `set_offset_date`. The dual assignment pattern is confusing but does not cause functional issues.

---

## Cross-Phase Analysis

### Dependency Chains

- **CFG-002** (Config phase) affects `Task.__init__` in `task.py` - the same file as SRV-002. Both findings relate to Task initialization but address different issues: CFG-002 concerns missing defaults merging, SRV-002 concerns redundant offset_date assignment. No conflict.

- **SEC-003** (Security phase) references `task.py:resolve_state_file` which is part of Task's state management. This is a defense-in-depth concern for the same code path but addresses different security aspects than SRV-001.

### Cross-Phase Conflicts

None detected. All Phase 03 findings are independent of other phases. The rejected findings (SRV-001, SRV-003) reference code patterns that do not conflict with other audit phases.
