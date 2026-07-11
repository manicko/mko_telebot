---
name: Phase 09 Audit Findings — Structural Code Quality
description: Structural code quality audit for complexity, length, nesting, and control flow
agent: auditor
alwaysApply: false
---

# Phase 09 Audit Findings — Structural Code Quality

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### STR-001: Critical Nesting Depth in _tokenize

| Field | Value |
|-------|-------|
| **ID** | STR-001 |
| **Severity** | CRITICAL |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `_tokenize` method in PatternParser class has a maximum nesting depth of 7, far exceeding the recommended limit of 3. This method contains deeply nested conditionals for character classification and token building.

**Evidence:**
```
src\mko_telebot\core\parser.py:105 _tokenize - nesting depth 7
```

**Recommendation:** Refactor the character classification logic: extract special character handling into helper methods and use a dispatch table or early returns. Effort: medium.

---

### STR-002: High Cyclomatic Complexity in search_match

| Field | Value |
|-------|-------|
| **ID** | STR-002 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `search_match` function has cyclomatic complexity of 15 (rank C), exceeding threshold of 10. Spanning 77 lines with nesting depth 4 and 7 return statements, this function handles parsing, exclusion checking, inclusion evaluation, and error handling together.

**Evidence:**
```
src\mko_telebot\core\parser.py
    F 325:0 search_match - C (15)
```

**Recommendation:** Split into `parse_query` and `evaluate_query` functions. Use a single return at end. Effort: medium.

---

### STR-003: High Cyclomatic Complexity in forward_to_users

| Field | Value |
|-------|-------|
| **ID** | STR-003 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `forward_to_users` function has cyclomatic complexity of 12 (rank C), exceeding threshold of 10. It has 6 parameters, 65 lines, nesting depth 4, and uses `for...else` anti-pattern.

**Evidence:**
```
src\mko_telebot\monitor.py
    F 120:0 forward_to_users - C (12)
    nesting depth 4, 65 lines, 6 parameters
```

**Recommendation:** Extract `build_caption` and `send_with_retry` helpers; replace `for...else` with explicit flag. Effort: medium.

---

### STR-004: High Cyclomatic Complexity in process_messages

| Field | Value |
|-------|-------|
| **ID** | STR-004 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `process_messages` function has cyclomatic complexity of 13 (rank C), exceeding threshold of 10. With nesting depth 4, it combines message grouping, keyword matching, and forwarding concerns.

**Evidence:**
```
src\mko_telebot\monitor.py
    F 187:0 process_messages - C (13)
```

**Recommendation:** Extract `group_album_messages` helper to separate grouping from matching logic. Effort: medium.

---

### STR-005: File Exceeds Maximum Length (parser.py)

| Field | Value |
|-------|-------|
| **ID** | STR-005 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `parser.py` file spans 401 lines, exceeding the 300-line threshold for god modules. Contains AST nodes, PatternParser class, and matcher functions.

**Evidence:**
```
src\mko_telebot\core\parser.py - 401 lines total
```

**Recommendation:** Split into `ast_nodes.py`, `parser.py`, and `matcher.py`. Effort: medium.

---

### STR-006: File Exceeds Maximum Length (monitor.py)

| Field | Value |
|-------|-------|
| **ID** | STR-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `monitor.py` file spans 356 lines, exceeding the 300-line threshold. Contains client creation, message processing, forwarding, scheduling, and main loop.

**Evidence:**
```
src\mko_telebot\monitor.py - 356 lines total
```

**Recommendation:** Split into `forwarding.py` and `client.py` modules. Effort: medium.

---

### STR-007: Multiple Issues in patterns_for_node

| Field | Value |
|-------|-------|
| **ID** | STR-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `patterns_for_node` function has 6 return statements and nesting depth 4, making control flow harder to follow.

**Evidence:**
```
src\mko_telebot\core\parser.py:290 patterns_for_node - 6 return statements, nesting depth 4
```

**Recommendation:** Use single return at end with accumulated results. Effort: small.

---

### STR-008: Multiple Issues in ast_to_regex

| Field | Value |
|-------|-------|
| **ID** | STR-008 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `ast_to_regex` function has 5 return statements, exceeding the recommended limit of 3.

**Evidence:**
```
src\mko_telebot\core\parser.py:249 ast_to_regex - 5 return statements
```

**Recommendation:** Consolidate to single return pattern. Effort: trivial.

---

### STR-009: for...else Anti-pattern

| Field | Value |
|-------|-------|
| **ID** | STR-009 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `forward_to_users` function uses `for...else` at lines 151-182. The `else` clause executes when the loop completes without hitting `break`, which is confusing and error-prone.

**Evidence:**
```python
for attempt in range(max_tries):
    try:
        await client.send_file(...) or await client.send_message(...)
        break
    except FloodWaitError as e:
        wait_time = e.seconds + random.uniform(5, 10) + (2 ** attempt)
        await asyncio.sleep(wait_time)
    except RPCError as e:
        wait_time = (2 ** attempt) + random.uniform(0, 3)
        await asyncio.sleep(wait_time)
else:
    logger.error("Failed to send...")
```

**Recommendation:** Replace with explicit success flag for clearer control flow. Effort: trivial.

---

### STR-010: UTF-8 BOM in File

| Field | Value |
|-------|-------|
| **ID** | STR-010 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/__init__.py |
| **Classification** | advisory |

**Description:** The `core/__init__.py` file contains a UTF-8 BOM character (U+FEFF), causing radon analysis to fail with "invalid non-printable character" error.

**Evidence:**
```
src\mko_telebot\core\__init__.py
    ERROR: invalid non-printable character U+FEFF (<unknown>, line 1)
```

**Recommendation:** Remove the BOM character from `core/__init__.py`. Effort: trivial.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 3 |
| MEDIUM | 1 |
| LOW | 4 |

---

## Mandatory Fixes

None - all findings are advisory code quality improvements.

---

## Advisory Recommendations

1. **CRITICAL:** Refactor `_tokenize` method (nesting depth 7) using early returns
2. **HIGH:** Split `search_match`, `forward_to_users`, `process_messages` to reduce complexity
3. **MEDIUM:** Split `parser.py` (401 lines) and `monitor.py` (356 lines) into smaller modules
4. **LOW:** Consolidate return statements in `patterns_for_node` and `ast_to_regex`
5. **LOW:** Replace `for...else` with explicit flag in `forward_to_users`
6. **LOW:** Remove UTF-8 BOM from `core/__init__.py`