# Phase 08 Audit Findings - Code Quality, Security & Maintainability

**Executor:** auditor
**Validator:** validator
**Template:** .ai/audit/templates/audit-findings.md
**Status:** validated
**Validated:** yes

---

## Findings

### QLT-001: ~~Cross-layer import violation in models.py~~ [REJECTED]

> **Rejection reason:** The architecture is correct per specification. SPEC.md section 4.2 explicitly documents `GoogleScope` as a `StrEnum` defined in `gsheets_reader.py` (line 159-168). `GoogleScope` is a type annotation for the `scopes` field in `GoogleSheetsConfig` - this is a data model type reference, not a service-layer cross-import. The AGENTS.md layer rule ("No cross-layer imports") applies to service-layer internals, not type definitions used in Pydantic models. The spec-defined architecture and public API exports both `GSheetsReader` and `GoogleScope` together from `core/__init__.py`.

---

### QLT-002: ~~Unused method `get_all_range_names()` in production code~~ [REJECTED]

> **Rejection reason:** Per the mandatory "dead code" validation rules, checked SPEC.md, Pydantic models, and config templates. The `get_all_range_names()` method is not referenced in any specification or config template. It exists solely for test coverage. Removing it provides minimal maintenance benefit while risking future utility. The method is documented, has a test, and could serve as convenience API for consumers who need to enumerate ranges. The ROI is negative - removing working code creates churn without meaningful maintenance improvement.

---

### QLT-003: ~~Unused property `settings` in TelepostConfigReader~~ [MERGED]

> **Validation Note:**
> - **Action:** merged
> - **Detail:** This finding duplicates CLI-001 from Phase 01. Both findings concern the same exact property (`settings` property in `TelepostConfigReader`, lines 257-270) that is documented as "intended for future use" but never consumed. CLI-001 already validated this as a dead code issue.
> - **See also:** CLI-001 (Phase 01)

---

### QLT-004: Blind exception handling in telegram_poster.py

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telepost/core/telegram_poster.py |
| **Classification** | advisory |

**Description:** The `get_chat_name` method catches a bare `Exception` which violates best practices. While it provides graceful degradation, it can mask unexpected errors and make debugging difficult.

**Evidence:**
- src/mko_telepost/core/telegram_poster.py:68 - `except Exception as e:`

**Recommendation:** Catch specific Telethon exceptions (e.g., `ValueError`, specific API errors) rather than bare `Exception`. If broad catching is necessary, at minimum log the full exception type name for debugging.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

None - all findings are advisory.

## Advisory Recommendations

- QLT-004: Blind exception handling (MEDIUM)

## Doc Updates Needed

None

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | QLT-004 |
| Reclassified | 0 | — |
| Merged | 1 | QLT-003 → CLI-001 |
| Rejected | 2 | QLT-001, QLT-002 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| QLT-001 | Cross-layer import violation in models.py | The architecture is correct per specification. SPEC.md explicitly documents `GoogleScope` as defined in `gsheets_reader.py`. This is a type annotation reference, not a service-layer cross-import. The AGENTS.md layer rule applies to service internals, not Pydantic model types. |
| QLT-002 | Unused method `get_all_range_names()` | The method provides documented convenience API with test coverage. SPEC.md does not reference it, but it's not "dead code" - it could serve future consumers. Removal creates churn without meaningful maintenance benefit. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| QLT-003 | CLI-001 (Phase 01) | Both findings concern the identical unused `settings` property in `TelepostConfigReader`. CLI-001 already validated this as a dead code issue. No need for duplicate reporting. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | No reclassifications required |