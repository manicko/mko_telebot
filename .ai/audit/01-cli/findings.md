---
name: 01-cli
description: CLI Entry Point and Command Layer Audit
executor: auditor
status: complete
validated: no
problems-only: true
---

# Phase 01 Audit Findings - CLI Entry Point and Command Layer

## Findings

### CLI-001: KeyboardInterrupt message mismatch between code and documentation

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/cli.py, docs/99-reference/cli-reference.md |
| **Classification** | advisory |

**Description:** The CLI code prints Shutdown requested on KeyboardInterrupt but the documentation specifies Monitoring stopped by user.

**Evidence:**
- Source code (src/mko_telebot/cli.py:101): console.print([yellow]Shutdown requested[/yellow])
- Documentation (docs/99-reference/cli-reference.md:163): states Monitoring stopped by user.
- Documentation (docs/99-reference/cli-reference.md:170): states Monitoring stopped by user.

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

**Description:** The shutil.copy2 call returns a path that is not captured. The basedpyright linter warns about unused call results.

**Evidence:**
- src/mko_telebot/cli.py:64: Warning from basedpyright: reportUnusedCallResult

**Recommendation:** Assign to underscore to indicate intentional discard. Effort: trivial. Priority: recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 2 |

## Advisory Recommendations

- CLI-001: Update documentation to match code for KeyboardInterrupt message
- CLI-002: Assign shutil.copy2 result to underscore to suppress linter warning

---