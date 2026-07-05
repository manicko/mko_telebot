---
name: audit-config-validated
description: Validated findings for configuration and Pydantic models
agent: validator
alwaysApply: false
---

# Phase 02 Audit Findings — Configuration and Pydantic Models

**Executor:** auditor
**Validator:** validator
**Template:** .ai/audit/templates/audit-findings.md
**Status:** validated
**Validated:** yes

---

## Findings

### CFG-001: Documentation claims chats field has impossible default value

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | HIGH |
| **Type** | DOC-UPDATE |
| **Affected Modules** | docs/99-reference/config-reference.md |
| **Classification** | advisory |

**Description:** The configuration reference documentation (line 239) claims chats has default value ChatsConfig(chats=[ChatConfig(chat_id=0)]). However, this default is impossible because ChatConfig.chat_id=0 raises ValidationError (lines 301-312 of models.py reject 0 as placeholder value). The code has ... (required) on the chats field (line 377-378), meaning no default exists and users must provide a valid chat configuration.

**Evidence:**
- docs/99-reference/config-reference.md line 239: States chats default is ChatsConfig(chats=[ChatConfig(chat_id=0)])
- src/mko_telepost/core/models.py line 377-378: chats: ChatsConfig = Field(..., description="...") - Required, no default
- src/mko_telepost/core/models.py lines 301-312: chat_id=0 validation rejects placeholder values
- docs/SPEC.md line 137 correctly documents chats as required with no default

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed the documentation error in config-reference.md. The default value shown is technically impossible (chat_id=0 is rejected). The SPEC.md correctly documents this as required. This is a documentation bug requiring correction.
> - **See also:** CLI-003 and CLI-004 in Phase 01 share root cause (incorrect configuration examples in user-facing docs)

---

## Cross-Phase Analysis

| Finding Pair | Conflict? | Relationship |
|--------------|-----------|--------------|
| CFG-001 + CLI-003 | No conflict | Both document incorrect configuration values; CFG-001 is config-reference.md, CLI-003 is README.md |
| CFG-001 + CLI-004 | No conflict | Both document incorrect configuration structure; CFG-001 is chats default, CLI-004 is posts: section |
| CLI-003 + CLI-004 | Merged | Both stem from the same root cause: outdated README configuration example |

**No cross-phase conflicts detected.** All configuration-related findings are consistent and validate the same underlying issue: documentation incorrectly describes configuration schema.

---

## Rollout Safety Assessment

**Dependency Chain:** Fixing CFG-001 is independent - no code changes required, only documentation update to config-reference.md line 239.

**Rollout Risk:** Low. This is a pure documentation fix. No code changes, no migration needed, no backward compatibility concerns.

**Sequencing:** Can be applied at any time. Recommended to coordinate with CLI-003 and CLI-004 fixes (README.md) to ensure consistent user-facing documentation.

**Hidden Dependencies:** None detected. The chats field is validated at Pydantic model construction; the fix only affects documentation.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 0 |
| LOW | 0 |

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | CFG-001 |
| Reclassified | 0 |
| Merged | 0 |
| Rejected | 0 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| — | — | No findings rejected |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | No findings merged |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| CFG-001 | SPEC-DEVIATION | DOC-UPDATE | Code correctly implements required chats field. Documentation incorrectly describes a default that cannot exist. The code behavior is correct; only documentation needs correction. |

---

## Warnings

- **Architectural Risk:** None. This is a pure documentation fix.
- **Documentation Inconsistency:** config-reference.md shows incorrect defaults while SPEC.md is accurate.

---

## Required Fixes

- docs/99-reference/config-reference.md line 239: Change Required column from no to yes and remove the impossible default value ChatsConfig(chats=[ChatConfig(chat_id=0)]).

---

## Advisory Recommendations

- Coordinate documentation fixes across README.md (CLI-003, CLI-004) and config-reference.md (CFG-001) to ensure consistent user experience.
- Consider adding validation test to verify all documented defaults actually work in code.
