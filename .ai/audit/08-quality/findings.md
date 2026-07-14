# Phase 08 Audit Findings — Code Quality, Security & Maintainability

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### QLT-001: Type checker errors in test files

| Field | Value |
|-------|-------|
| **ID** | QLT-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | tests/test_monitor.py, tests/test_monitor_forward.py, tests/test_parser.py, tests/test_task.py |
| **Classification** | advisory |

**Description:** The basedpyright type checker reports 75 errors and 645 warnings in the test files. The primary issues are:
- Type mismatches between MagicMock and expected generic types (e.g., `list[MagicMock]` cannot be assigned to `list[Message]`)
- Missing type stubs for telethon.errors causing Any types to propagate
- Unused parameters (mock_sleep, mock_sender_tag, mock_message_link) in multiple tests
- Unused variables in test functions

These type errors indicate that the tests use MagicMock extensively without proper type annotations, undermining the type safety benefits of the project.

**Evidence:**
- `tests/test_monitor.py:516:32` - Argument of type "list[MagicMock]" cannot be assigned to parameter "messages" of type "list[Message]" in function "process_messages"
- `tests/test_parser.py:283:13` - Argument of type "None" cannot be assigned to parameter "query" of type "str" in function "parse_query"
- 75 total errors, 645 warnings from basedpyright across test files

**Recommendation:** Add type annotations to mock objects or use TypedMock/AsyncMock with proper generic parameters. Consider using pytest-asyncio's typing support or mypy's `type: ignore` comments for unavoidable cases. The `Sequence` type parameter issue suggests using `Sequence[ASTNode]` instead of `list[ASTNode]` in ASTNode constructors for better covariance.

---

### QLT-002: Private function accessed in tests violates encapsulation

| Field | Value |
|-------|-------|
| **ID** | QLT-002 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | tests/test_monitor_forward.py, tests/test_parser.py |
| **Classification** | advisory |

**Description:** Test files access private/protected functions (`_send_with_retry`, `_peek`, `_consume`, `_parse_term`) directly, which violates encapsulation and couples tests to implementation details. This makes refactoring harder and tests more brittle.

**Evidence:**
- `tests/test_monitor_forward.py:12:41` - `_send_with_retry` is private and used outside of the module
- `tests/test_parser.py:140:23` - `_peek` is protected and used outside of the class
- `tests/test_parser.py:152:22` - `_consume` is protected and used outside of the class
- `tests/test_parser.py:250:25` - `_parse_term` is protected and used outside of the class

**Recommendation:** Make tested functions public or restructure tests to test behavior through public APIs only. Alternatively, keep private functions but add `# pragma: no cover` or `# type: ignore[reportPrivateUsage]` with explanations that these are intentional white-box tests.

---

### QLT-003: Unreachable code in tests

| Field | Value |
|-------|-------|
| **ID** | QLT-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_monitor_forward.py |
| **Classification** | advisory |

**Description:** Several test functions contain unreachable code after return statements, indicating test logic issues or incomplete test refactoring.

**Evidence:**
- `tests/test_monitor_forward.py:116:17` - Code is unreachable
- `tests/test_monitor_forward.py:133:17` - Code is unreachable
- `tests/test_monitor_forward.py:153:17` - Code is unreachable

**Recommendation:** Review and remove unreachable code paths. These may indicate assertion errors where test logic exits early but subsequent code was not removed.

---

### QLT-004: Unused imports in core modules

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** The `random` import in `task.py` is used for `random.uniform()` calls, but `random` is also imported in `monitor.py` and `monitor_forward.py` for the same purpose. No truly unused imports were found in production code.

**Evidence:** All imports in production code are used. The basedpyright warnings about `Any` types in tests are from `typing import Any` in `monitor_forward.py` line 9, which IS used for the `msg_media` parameter annotation.

**Recommendation:** No action needed - imports are used. However, consider whether the Any type in `msg_media: list[Any] | None` should be more specific.

---

### QLT-005: Missing type stubs for telethon.errors causing cascading Any types

| Field | Value |
|-------|-------|
| **ID** | QLT-005 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | tests/test_monitor.py, tests/test_monitor_forward.py, tests/test_task.py |
| **Classification** | advisory |

**Description:** The telethon.errors module lacks type stubs, causing all error handling code to propagate `Any` types. This undermines type safety throughout the codebase wherever telethon errors are caught or handled.

**Evidence:**
- `tests/test_monitor.py:423:14` - Stub file not found for "telethon.errors"
- `tests/test_monitor_forward.py:9:6` - Stub file not found for "telethon.errors"
- `tests/test_task.py:11:6` - Stub file not found for "telethon.errors"

**Recommendation:** Create type stubs for telethon.errors or use `pyright --ignoreexternal` to suppress these warnings. Consider adding `# pyright: reportMissingTypeStubs=false` to test files specifically, or contribute stubs to the telethon package.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 2 |

## Mandatory Fixes

None - all findings are advisory.

## Advisory Recommendations

1. QLT-001: Address type checker errors in tests for better type safety
2. QLT-002: Review private function access in tests for encapsulation
3. QLT-003: Remove unreachable code in tests
4. QLT-004: Consider more specific typing instead of Any where possible
5. QLT-005: Address missing telethon type stubs or suppress warnings

## Doc Updates Needed

None