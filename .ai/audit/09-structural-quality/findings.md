---
name: 09-structural-quality
description: Structural Code Quality Audit
executor: auditor
template: .ai/audit/templates/audit-findings.md
status: complete
validated: no
---

# Phase 09 Audit Findings — Structural Code Quality

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### STR-001: Function `forward_to_users` has complexity and nesting exceeding thresholds

| Field | Value |
|-------|-------|
| **ID** | STR-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | advisory |

**Description:** The `forward_to_users` function at line 23 has cyclomatic complexity of 12 (rank C), nesting depth of 4, and 62 non-blank lines in the body (excluding signature and docstring), exceeding both the target CC ≤10, nesting depth ≤3, and function length ≤50. The function also has 6 parameters (exceeding the target ≤5). The complexity stems from nested control flow: a `for` loop over targets containing a `for` loop for retries, with `if/else` branches inside, wrapped in a `try/except` block with two exception handlers, and a `for...else` clause for the retry loop failure case.

**Evidence:** `radon cc src/ -a -nc` output:
```
src\mko_telebot\monitor_forward.py
    F 23:0 forward_to_users - C (12)
```

The function structure (lines 65-110) shows nesting depth 4:
- Line 65: `for target in task.forward_to_entities:` - depth 1
- Line 68: `for attempt in range(max_tries):` - depth 2
- Line 69: `try:` - depth 3
- Line 70: `if msg_media:` - depth 4

The `for...else` anti-pattern at line 104 runs when all retry attempts are exhausted:
```python
for attempt in range(max_tries):
    try:
        ...
        break
    except FloodWaitError as e:
        ...
    except RPCError as e:
        ...
else:  # This runs if no break occurred (all retries exhausted)
    logger.error(...)
```

**Recommendation:** Extract the retry logic into a separate async helper function `_send_with_retry(client, target, caption, msg_media, max_tries)` to isolate the retry loop. This reduces nesting depth and makes the retry behavior testable in isolation. Replace the `for...else` with explicit success tracking via a boolean flag for clarity. Bundle `msg_text` and `msg_media` into a single content object to reduce parameter count.

### STR-002: Function `process_messages` has cyclomatic complexity rank C (12)

| Field | Value |
|-------|-------|
| **ID** | STR-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | advisory |

**Description:** The `process_messages` function at line 113 has cyclomatic complexity of 12 (rank C). It performs two distinct operations: (1) grouping messages by album ID, and (2) checking each group for keyword matches and forwarding. The nested `if` inside the `for` loop (lines 142-146) that checks for media caption shows a nesting depth of 3 (for msg -> if getattr(msg, "media") -> if getattr(msg.media, "caption")).

**Evidence:** `radon cc src/ -a -nc` output:
```
src\mko_telebot\monitor_forward.py
    F 113:0 process_messages - C (12)
```

**Recommendation:** Extract the message grouping logic into a helper function `_group_messages_by_album(messages)` to separate the grouping concern from the forwarding concern. This splits the function into two smaller, more focused functions.

### STR-003: Average cyclomatic complexity exceeds threshold (12.0 vs target ≤5)

| Field | Value |
|-------|-------|
| **ID** | STR-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot |
| **Classification** | advisory |

**Description:** The project-wide average cyclomatic complexity is 12.0 (rank C), exceeding the target of ≤5. This indicates the codebase, while not severely complex, has room for improvement in keeping functions simple. The audit found no functions with rank D or worse (≥21), which is positive.

**Evidence:** `radon cc src/ -a -nc` output:
```
Average complexity: C (12.0)
```

**Recommendation:** Continue the pattern of extracting helper functions. The current complexity is manageable but should be monitored as the codebase grows.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 1 |

## Mandatory Fixes

None

## Advisory Recommendations

- STR-001: Refactor `forward_to_users` to extract retry logic into helper function and reduce parameter count
- STR-002: Extract message grouping logic from `process_messages` into helper function
- STR-003: Monitor cyclomatic complexity as codebase grows