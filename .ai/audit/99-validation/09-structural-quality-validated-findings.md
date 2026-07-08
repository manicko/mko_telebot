---
name: 09-structural-quality
description: Structural code quality audit findings — validated
agent: validator
alwaysApply: false
---

# Phase 09 Audit Findings — Structural Code Quality (Validated)

**Executor:** validator  
**Template:** `.ai/audit/templates/audit-findings.md`  
**Source:** `.ai/audit/09-structural-quality/findings.md`  
**Status:** validated  
**Date:** 2026-07-08

---

## Findings

### STR-001: `search_match` function exceeds complexity and length thresholds

| Field | Value |
|-------|-------|
| **ID** | STR-001 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | mandatory |

**Description:** The `search_match` function (line 325) has cyclomatic complexity of 15 (rank C), exceeding the recommended threshold of 10. The function is 77 lines long, significantly exceeding the 50-line recommended maximum. It also contains 7 return statements, exceeding the 3-return threshold. Nesting depth is 4, exceeding the threshold of 3. This function handles query parsing, exclusion checking, inclusion checking, and exception handling all in one place, making it difficult to test in isolation and prone to bugs.

**Evidence (verified):**
```
src\mko_telebot\core\parser.py
    F 325:0 search_match - C (15)
    Ruff C901: complexity 13 (ruff's metric differs slightly from McCabe)
```
- Line count: 77 lines (325-401).
- Nesting depth: 4 (try → for → for → if).
- 7 return statements at lines 354, 357, 368, 377, 387, 391, 401.
- Cyclomatic complexity (McCabe): 15 (verified via AST analysis).

**Recommendation:** Extract the inclusion and exclusion checking logic into separate private helper functions (e.g., `_check_exclusions`, `_check_inclusions`). This would reduce the main function to orchestration logic with lower complexity, improve testability of individual matching components, and follow the single-responsibility principle.

---

### STR-002: `_tokenize` method has excessive nesting depth

| Field | Value |
|-------|-------|
| **ID** | STR-002 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | mandatory |

**Description:** The `_tokenize` method (line 105) in the `PatternParser` class has nesting depth of 7, far exceeding the recommended threshold of 3. The method uses a while loop with multiple nested if/elif branches for character parsing, creating "arrow code" that is hard to follow and maintain.

**Evidence (verified):**
- Nesting depth: 7-8 (verified via AST analysis). The `elif` chain in Python AST is represented as nested `If` nodes in each other's `orelse`, so `while → if/elif/elif/elif/elif/elif → else → while` reaches depth 7.
- Lines 120-141 contain the deeply nested while loop with multiple elif branches.

**Recommendation:** Refactor to use early returns or extract character handling into helper methods. Consider converting the while loop with character-by-character branching into a dispatch table or state machine pattern. Effort: medium.

---

### STR-003: `process_messages` function exceeds nesting threshold

| Field | Value |
|-------|-------|
| **ID** | STR-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | advisory |

**Description:** The `process_messages` function (line 175) has nesting depth of 4, exceeding the recommended threshold of 3. The function nests a for loop inside the try block, then has nested if statements inside that loop for media caption handling.

**Evidence (verified):**
- Nesting depth: 4. Lines 188-201 show `for msg in messages:` → `try:` → `if getattr(msg, "media", None):` → `if getattr(msg.media, "caption", None):`.
- Verified by AST analysis.

**Recommendation:** Extract message content extraction logic into a helper function to reduce nesting. Effort: small. Priority: recommended.

---

### STR-004: `forward_to_users` function slightly exceeds length threshold

| Field | Value |
|-------|-------|
| **ID** | STR-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | advisory |

**Description:** The `forward_to_users` function (line 121) is 52 lines long, slightly exceeding the 50-line recommended maximum. While close to the threshold, the function combines caption building, media sending logic, and error handling in a single unit.

**Evidence (verified):**
- Line count: 52 lines (121-172). Nesting depth: 3 (acceptable).
- Verified by AST analysis.

**Recommendation:** Extract caption building logic into a separate helper function (e.g., `_build_caption`) to improve modularity. Effort: trivial. Priority: recommended.

---

### STR-005: ~~Average cyclomatic complexity exceeds threshold~~ [REJECTED]

> **Rejection reason:** The finding's methodology is flawed. The evidence states "2 blocks (classes, functions, methods) analyzed" with an average complexity of 14.0. However, the actual codebase contains **69 functions/methods** across all source files, with a true average complexity of **3.2** (sum 222 ÷ 69 blocks). The claim of 14.0 is based on analyzing only the two most complex functions, which is not a representative sample. The recommendation is already covered by STR-001 and STR-002. A separate finding for average complexity adds no actionable value.

| Field | Value |
|-------|-------|
| **ID** | STR-005 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | All source files |
| **Classification** | advisory |

**Original description:** The average cyclomatic complexity across the project is 14.0 (rank C), exceeding the recommended threshold of ≤5. While individual simple functions are fine, the overall codebase complexity is elevated due to the `search_match` function.

---

### STR-006: ~~parser.py is a god module~~ [REJECTED]

> **Rejection reason:** The file is 333 non-blank lines of coherent and self-contained code (AST dataclasses + parser class + tree functions). The recommendation to split into `parser_ast.py` and `parser.py` would introduce cross-module import overhead without proportional benefit at this project scale. The file follows single-responsibility: it is a single text-pattern parsing module. No other module in the codebase exceeds 200 lines, so there is no systemic large-file problem. The 300-line threshold is a guideline, and 333 lines of well-organized, focused code do not warrant a split.

| Field | Value |
|-------|-------|
| **ID** | STR-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | advisory |

**Original description:** The `parser.py` file is 333 lines long, exceeding the 300-line recommended maximum for source files. The file contains both the AST node dataclasses, the `PatternParser` class, and standalone functions `ast_to_regex`, `patterns_for_node`, and `search_match`.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 2 |
| LOW | 0 |

## Mandatory Fixes

- STR-001: Refactor `search_match` function to reduce complexity and length
- STR-002: Refactor `_tokenize` method to reduce nesting depth

## Advisory Recommendations

- STR-003: Reduce nesting in `process_messages` function
- STR-004: Extract caption building from `forward_to_users`

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 4 | STR-001, STR-002, STR-003, STR-004 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 2 | STR-005, STR-006 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| STR-005 | Average cyclomatic complexity exceeds threshold | Flawed methodology: only 2 of 69 blocks analyzed. True average complexity is 3.2, not 14.0. No actionable value beyond STR-001 and STR-002. |
| STR-006 | parser.py is a god module | 333 non-blank lines of focused, coherent code. Split would add import overhead with no proportional benefit at this project scale. No other module exceeds 200 lines. |

### Merged Findings

None.

### Reclassified Findings

None.

---

## Warnings

- **Metric accuracy:** STR-005's claim of 14.0 average cyclomatic complexity from 2 blocks is misleading. The true average across all 69 functions/methods is 3.2. Future audits should verify metric collection methodology.
- **Line count definition:** STR-006 reports 333 lines (non-blank code). The total file is 401 lines including blanks. Both metrics are valid for different purposes, but consistency in future audits is recommended.

## Required Fixes

- STR-001: Refactor `search_match` in `src/mko_telebot/core/parser.py` (complexity 15, 77 lines, 7 returns)
- STR-002: Refactor `_tokenize` in `src/mko_telebot/core/parser.py` (nesting depth 7-8)

## Advisory Recommendations

- STR-003: Extract message content extraction from `process_messages` in `src/mko_telebot/monitor.py`
- STR-004: Extract caption building from `forward_to_users` in `src/mko_telebot/monitor.py`

## Rollout Analysis

No rollout concerns. These are code quality findings with no breaking changes, dependency chains, or deployment sequencing issues.