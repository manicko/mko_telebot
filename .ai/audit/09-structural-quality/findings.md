---
name: 09-structural-quality
description: Structural code quality audit findings
agent: auditor
alwaysApply: false
---

# Phase 09 Audit Findings — Structural Code Quality

**Executor:** auditor  
**Template:** `.ai/audit/templates/audit-findings.md`  
**Status:** complete  
**Validated:** no

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

**Description:** The `search_match` function (line 325) has cyclomatic complexity of 15 (rank C), exceeding the recommended threshold of 10. The function is 77 lines long, significantly exceeding the 50-line recommended maximum. It also contains 4 return statements, exceeding the 3-return threshold. Nesting depth is 4, exceeding the threshold of 3. This function handles query parsing, exclusion checking, inclusion checking, and exception handling all in one place, making it difficult to test in isolation and prone to bugs.

**Evidence:**
```
src\mko_telebot\core\parser.py
    F 325:0 search_match - C (15)
```
Line count: 77 lines (325-401). Nesting depth: 4. Multiple return statements at lines 354, 357, 368, 377, 387, 391, 401 (7 exit points).

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

**Evidence:** Nesting depth: 7 (measured via AST analysis). Lines 120-141 contain deeply nested while loop with multiple elif branches.

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

**Evidence:** Nesting depth: 4. Lines 188-201 show `for msg in messages:` → `try:` → `if getattr(msg, "media", None):` → `if getattr(msg.media, "caption", None):`.

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

**Evidence:** Line count: 52 lines (121-172). Nesting depth: 3 (acceptable).

**Recommendation:** Extract caption building logic into a separate helper function (e.g., `_build_caption`) to improve modularity. Effort: trivial. Priority: recommended.

---

### STR-005: Average cyclomatic complexity exceeds threshold

| Field | Value |
|-------|-------|
| **ID** | STR-005 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | All source files |
| **Classification** | advisory |

**Description:** The average cyclomatic complexity across the project is 14.0 (rank C), exceeding the recommended threshold of ≤5. While individual simple functions are fine, the overall codebase complexity is elevated due to the `search_match` function.

**Evidence:**
```
2 blocks (classes, functions, methods) analyzed.
Average complexity: C (14.0)
```

**Recommendation:** Refactor the `search_match` and `_tokenize` functions as described in STR-001 and STR-002. This would significantly reduce the average complexity. Effort: small-medium. Priority: recommended.

---

### STR-006: parser.py is a god module

| Field | Value |
|-------|-------|
| **ID** | STR-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | advisory |

**Description:** The `parser.py` file is 333 lines long, exceeding the 300-line recommended maximum for source files. The file contains both the AST node dataclasses, the `PatternParser` class, and standalone functions `ast_to_regex`, `patterns_for_node`, and `search_match`.

**Evidence:** Line count: 333 lines.

**Recommendation:** Split into two modules: `parser_ast.py` (AST nodes and `ast_to_regex`) and `parser.py` (parser class and search logic). This follows the single-responsibility principle for modules. Effort: medium. Priority: recommended.

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
- STR-005: Reduce average cyclomatic complexity
- STR-006: Split `parser.py` into smaller modules