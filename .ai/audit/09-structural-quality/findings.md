---
name: 09-structural-quality-findings
description: Structural code quality audit findings for mko_telebot
status: complete
validated: no
---

# Phase 09 Audit Findings — Structural Code Quality

**Executor:** auditor
**Template:** `.ai/audit/templates/audit-findings.md`
**Status:** complete
**Validated:** no

---

## Findings

### STR-001: Functions Exceeding 50 Line Limit in `monitor_forward.py`

| Field | Value |
|-------|-------|
| **ID** | STR-001 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** Three functions in `monitor_forward.py` exceed the recommended 50-line limit: `_send_with_retry` (63 lines), `process_task` (62 lines), and `forward_to_users` (57 lines). These functions combine multiple concerns (retry logic, message processing, state management) making them harder to test in isolation and maintain. The `_send_with_retry` function handles three different exception types with similar retry logic that could be consolidated.

**Evidence:** Function line counts:
- `_send_with_retry`: lines 24-87, 63 total lines (3 exception handlers with duplicated backoff logic)
- `process_task`: lines 196-257, 62 total lines (message fetching, error handling, forwarding, state updates)
- `forward_to_users`: lines 89-145, 57 total lines (caption building, iteration over targets)

**Recommendation:** Extract `_send_with_retry` into smaller functions by consolidating the retry logic for each exception type into a single handler. Extract the state persistence logic from `process_task` into the Task class. **effort: large** **priority: recommended**

---

### STR-002: High Cyclomatic Complexity in `process_messages`

| Field | Value |
|-------|-------|
| **ID** | STR-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** The `process_messages` function at line 148 has cyclomatic complexity rank C (score: 11), exceeding the recommended threshold of 10. This function handles multiple responsibilities: message grouping, content extraction, keyword matching, and forwarding orchestration. The complexity stems from nested loops (for msg in messages, for album_id in msg_content.items) combined with conditional logic for text/media handling and keyword matching.

**Evidence:** Radon output shows `F 148:0 process_messages - C (11)`. Average complexity across project is C (11.0), also exceeding the target of B (≤5).

**Recommendation:** Extract the message grouping logic into a dedicated helper function (`_group_messages_by_album`) and consider extracting the forward decision logic. This would reduce cognitive load and improve testability. **effort: medium** **priority: recommended**

---

### STR-003: Nesting Depth in `PatternParser._parse_term`

| Field | Value |
|-------|-------|
| **ID** | STR-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | advisory |

**Description:** The `PatternParser._parse_term` method (line 156) has cyclomatic complexity rank B (7) with nesting depth of 3 levels in the GROUP_START handling branch. The method checks `if tok`, then `if tok[0] == "GROUP_START"`, then has nested `if tok` for GROUP_END handling (line 176), creating an arrow-code pattern that is harder to follow.

**Evidence:** Radon: `M 156:4 PatternParser._parse_term - B (7)`. Nesting analysis: `if tok[0] == "GROUP_START"` (level 1) → nested `if (tok := self._peek())` (level 2) for GROUP_END. The method spans 26 lines with conditional nesting.

**Recommendation:** Refactor `_parse_term` to use guard clauses for early returns, extracting group parsing into `_parse_group()` method. This reduces nesting and improves clarity. **effort: small** **priority: recommended**

---

### STR-004: Nested Loops and Conditionals in `apply_defaults_to_channels`

| Field | Value |
|-------|-------|
| **ID** | STR-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/channels.py` |
| **Classification** | advisory |

**Description:** The `apply_defaults_to_channels` method (line 125) has cyclomatic complexity rank B (7) with nesting depth of 3+ levels. The method iterates over channels, then fields, then has nested if-elif conditions checking `default_factory` and `current_val`, creating a nested structure that is hard to follow and maintain.

**Evidence:** Radon: `M 125:4 ChannelsConfig.apply_defaults_to_channels - B (7)`. Nesting analysis shows: for channel loop (level 1) → for field loop (level 2) → if/elif chain (level 3). The method spans 24 lines (125-148) with deeply nested control flow.

**Recommendation:** Extract the per-field default application logic into a helper method `_apply_field_defaults(channel, defaults_data)`. This reduces nesting depth and makes the logic more testable. **effort: small** **priority: recommended**

---

### STR-006: Elevated Complexity in `_tokenize` Method

| Field | Value |
|-------|-------|
| **ID** | STR-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | advisory |

**Description:** The `PatternParser._tokenize` method (line 40) has cyclomatic complexity rank B (9), approaching the threshold. The method uses an if-elif-else chain inside a while loop, creating multiple branches that are hard to extend. Adding new token types would require modifying this central method, violating the open-closed principle.

**Evidence:** Radon: `M 40:4 PatternParser._tokenize - B (9)`. The method spans 38 lines (40-78) with a while loop containing 5 branches (GROUP_START, GROUP_END, OR, EXCLUDE, TERM) plus whitespace handling. This creates a maintenance bottleneck for the parser.

**Recommendation:** Consider using a dispatch table mapping character types to token-creation functions. Extract the INNER while loop for TERM parsing into `_tokenize_term(q, start, i)`. **effort: medium** **priority: recommended**

---

### STR-005: Multiple Return Points in `_check_patterns_match`

| Field | Value |
|-------|-------|
| **ID** | STR-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/matcher.py` |
| **Classification** | advisory |

**Description:** The `_check_patterns_match` function (line 91) has 4 return statements, violating the single-exit-point best practice. The function returns early at line 102 (empty patterns), inside the loop at lines 105 and 107 for failure cases, and at line 108 for success. While the function is short, multiple return points create non-linear control flow.

**Evidence:** Lines 91-108 show: early return at line 102 (empty patterns), loop with returns at lines 105 and 107, and final return at line 108. Total of 4 return statements.

**Recommendation:** Use a single return with a result flag: `matched = True; for pat in patterns: if not pat or not re.search(...): matched = False; break; return matched`. **effort: trivial** **priority: recommended**

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 4 |
| LOW | 1 |

## Advisory Recommendations

- STR-001: Refactor `_send_with_retry`, `process_task`, `forward_to_users` in monitor_forward.py to reduce line counts
- STR-002: Extract message grouping logic from `process_messages` to reduce complexity
- STR-003: Refactor `PatternParser._parse_term` to reduce nesting using guard clauses
- STR-004: Extract field default logic in `ChannelsConfig.apply_defaults_to_channels`
- STR-005: Consolidate return points in `_check_patterns_match`
- STR-006: Refactor `PatternParser._tokenize` to use dispatch pattern for extensibility

---