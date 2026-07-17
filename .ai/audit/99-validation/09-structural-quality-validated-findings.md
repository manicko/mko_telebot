# Phase 09 Validated Findings — Structural Quality

**Validator:** validator  
**Source:** `.ai/audit/09-structural-quality/findings.md`  
**Status:** validated

---

## Runtime Verification Log

- **R1 — File length (task.py):** `uv run radon raw src/mko_telebot/core/task.py` → LOC: 380, LLOC: 122, Blank: 206 (54% blank). Confirmed.
- **R2 — Complexity (task.py):** Longest function `resolve_targets_entities` is 63 statements. MI rank: A (60.93). Confirmed.
- **R3 — Complexity (parser.py):** `_tokenize` depth=4, CC=9 (B); `parse` depth=4, CC=6 (B). MI rank: A (58.20). Confirmed.
- **R4 — Complexity (cli.py init):** `init` function CC=12 (C rank). Confirmed.
- **R5 — Complexity (monitor_forward.py):** `process_messages` CC=24 (B rank). Confirmed.

---

## Findings Validation

### STR-003: `core/task.py` is the only file approaching the file-length budget (380 lines)

| Field | Value |
|-------|-------|
| **ID** | STR-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/task.py` |
| **Classification** | advisory |

**Evidence Verified:**
- `src/mko_telebot/core/task.py` has 380 lines total, the largest file in the project.
- Radon reports 206 blank lines (54% blank), so logical content is 174 lines.
- MI rank is A at 60.93.
- Functions are within budget: `resolve_targets_entities` (63 lines), `load_state` (39 lines).
- The file aggregates entity resolution (`resolve_targets_entities`, `resolve_channel_entity`, `resolve_state_file`), state persistence (`load_state`, `save_state`, `set_offset_date`), and config/offset math.

> **Validation Note:**
> - **Action:** Validated (BEST-PRACTICE)
> - **Detail:** Finding correctly identifies that `task.py` (380 lines) is the largest source file. Per project rule "small modules and functions give higher ROI in maintenance", splitting state-persistence helpers into a `core/state.py` module would align with the architecture. However, the functions are small and MI rank is A, so no urgent action is required. The recommendation is appropriately advisory/low priority.

**Recommendation:** No urgent action required. If the `Task` class keeps growing, prefer splitting state-persistence helpers (`load_state`/`save_state`/`resolve_state_file`) into a `core/state.py` module rather than letting `task.py` cross 400+ lines. This preserves the "small modules" principle.

---

### STR-004: Depth-4 nesting in parser `PatternParser` helpers is acceptable but worth noting

| Field | Value |
|-------|-------|
| **ID** | STR-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | advisory |

**Evidence Verified:**
- `_tokenize` (lines 55-93) reaches nesting depth 4. The deepest level is the inner `while` loop reading a TERM until a special character.
- `parse` (lines 112-138) also reaches nesting depth 4 due to `while` → `if EXCLUDE` → nested `if excl` chain.
- Both functions have B-rank CC (9 and 6 respectively) but MI rank is A (58.20).
- Neither uses "arrow code" — both use early returns and are readable.

> **Validation Note:**
> - **Action:** Validated (BEST-PRACTICE)
> - **Detail:** Verified: `_tokenize` and `parse` are the deepest nesting points in the codebase. The nesting is intentional for the recursive-descent parser structure. The recommendation to extract `_read_term(q, i)` helper if complexity rises further is aligned with the project's modularization principle. Current state is acceptable.

**Recommendation:** No change required now. If parser complexity keeps rising, consider extracting the TERM-reading inner loop in `_tokenize` into a `_read_term(q, i)` helper to flatten the nesting to depth 3 and make the scanner trivially testable.

---

## Cross-Phase Analysis

No cross-phase conflicts detected. The findings in this phase do not conflict with other phases.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | STR-003, STR-004 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None — all presented findings (STR-003, STR-004) were validated as correct.

### Merged Findings

None — no duplicate root causes identified in this phase.

### Reclassified Findings

None — all findings correctly classified.

---

## Rollout Analysis

### Dependencies

- STR-003 and STR-004 are independent recommendations. Neither depends on another finding.

### Sequencing Concerns

None — these are advisory recommendations with no enforcement dependencies.

### Architectural Risks

- None significant. Both findings describe well-structured code with acceptable complexity metrics. The recommendations are preventive rather than corrective.