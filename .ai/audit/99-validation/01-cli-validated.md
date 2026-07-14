---
name: 01-cli-validated
description: Validated audit findings for CLI Entry Point and Command Layer
validated: yes
validated_date: 2025-07-14
---

# Phase 01 Audit Findings - CLI Entry Point and Command Layer

## Findings

### CLI-001: KeyboardInterrupt message mismatch between code and documentation

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | src/mko_telebot/cli.py, docs/99-reference/cli-reference.md |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** Reclassified
> - **Detail:** The documentation incorrectly states "Monitoring stopped by user." but the actual code prints "Shutdown requested". The code message is clear and appropriate. Per validation rules, when code is correct and documentation is outdated, this is a DOC-UPDATE, not SPEC-DEVIATION.
> - **See also:** —

**Description:** The CLI code prints `Shutdown requested` on KeyboardInterrupt but the documentation specifies "Monitoring stopped by user."

**Evidence:**
- Source code (src/mko_telebot/cli.py:101): `console.print("[yellow]Shutdown requested[/yellow]")`
- Documentation (docs/99-reference/cli-reference.md:163): states "Monitoring stopped by user."
- Documentation (docs/99-reference/cli-reference.md:170): states "Monitoring stopped by user."

**Recommendation:** Update the documentation to match the code. Effort: trivial. Priority: recommended.

---

### CLI-002: Unused result from shutil.copy2 in init command

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/cli.py |
| **Classification** | advisory |

**Description:** The `shutil.copy2` call returns a path that is not captured. The basedpyright linter warns about unused call results.

**Evidence:**
- Source code (src/mko_telebot/cli.py:64): `shutil.copy2(item, target)` — return value discarded
- basedpyright output confirms: `reportUnusedCallResult` warning

**Recommendation:** Assign to underscore to indicate intentional discard. Effort: trivial. Priority: recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 2 |

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | CLI-002 |
| Reclassified | 1 | CLI-001 |
| Merged | 0 | — |
| Rejected | 0 | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| CLI-001 | SPEC-DEVIATION | DOC-UPDATE | Documentation incorrectly states "Monitoring stopped by user." but the actual code prints "Shutdown requested". The code implements the correct behavior; documentation needs to be updated. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | — |