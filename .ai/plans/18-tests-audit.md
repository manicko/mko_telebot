# Audit Report: Basedpyright Type Check for Test Files

**Date:** 2026-07-12
**Tool:** basedpyright
**Files audited:**
- tests/test_cli.py
- tests/test_config.py
- tests/test_config_reader.py
- tests/test_logging.py
- tests/test_parser.py
- tests/test_monitor.py
- tests/test_monitor_forward.py
- tests/test_task.py
- tests/test_errors.py
- tests/conftest.py

**Summary:**
- **Total errors:** 75
- **Total warnings:** 480
- **Total notes:** 0

---

## Critical Errors (Type Safety Violations)

### 1. test_config_reader.py - Type Argument Errors

#### 1.1 SecretStr Type Mismatches
**Location:** lines 446, 450, 454, 460, 464, 468, 472, 480, 488, 491, 498, 500, 508, 517, 572, 573, 586, 587, 599, 600, 612, 613, 627, 629, 640, 642, 643, 652, 654, 655, 665, 667, 668, 678, 680, 681, 693, 694, 707, 716, 724, 725

**Error:** `Argument of type "LiteralString" cannot be assigned to parameter "api_hash" of type "SecretStr"`

**Description:** Tests pass raw string values to `ClientConfig` constructor instead of wrapping them in `SecretStr`. Similar issues with `phone_or_token` and proxy parameters.

**Severity:** HIGH - Test code violates production type contracts.

---

#### 1.2 ProxyConfig Type Mismatches
**Location:** lines 573, 587, 600, 613, 643, 655, 668, 681, 716, 725

**Error:** `Argument of type "dict[str, str | int]" cannot be assigned to parameter "proxy" of type "ProxyConfig | None"`

**Description:** Tests pass plain dictionaries instead of proper `ProxyConfig` model instances.

---

#### 1.3 Missing Type Annotations in Helper Function
**Location:** test_parser.py lines 558, 565, 577, 587

**Error:** Missing parameter type annotations for `build_function` pytest helper.

**Details:** Parameters `matcher`, `text`, `query`, `expected` lack type hints causing `reportUnknownParameterType` and `reportMissingParameterType`.

---

### 1.4 test_task.py - history_days Type Mismatch
**Location:** test_task.py:121

**Error:** `Cannot assign to attribute "history_days" for class "Task"` - Literal['not_a_number'] not assignable to int | None.

**Severity:** MEDIUM - Test code validates but violates type constraints.

---

### 2. test_monitor.py - Generic Variance Errors

#### 2.1 Message Type Variance
**Location:** lines 516, 535, 557, 584, 605, 629, 652, 671, 689, 708

**Error:** `Argument of type "list[MagicMock]" cannot be assigned to parameter "messages" of type "list[Message]"`

**Description:** Tests pass MagicMock objects where Message instances are expected. Suggested fix: use `Sequence[Message]` (covariant) in production code signature.

**Severity:** MEDIUM - Mock type incompatibility.

---

#### 2.2 Queue Type Variance
**Location:** lines 728, 743, 758, 858, 907, 956, 1005, 1033, 1053, 1070

**Error:** `Argument of type "Queue[MagicMock]" cannot be assigned to parameter "queue" of type "Queue[Task]"`

**Description:** Tests use `Queue[MagicMock]` for Task queues. Same variance issue as messages.

---

### 3. test_parser.py - ASTNode Attribute Access Issue

#### 3.1 Invalid Attribute Access
**Location:** line 437

**Error:** `Cannot access attribute "value" for class "ASTNode"`

**Description:** Code attempts to access `.value` attribute on ASTNode, which doesn't exist.

---

#### 3.2 None Passed to Required String Parameter
**Location:** line 283

**Error:** `Argument of type "None" cannot be assigned to parameter "query" of type "str"`

**Description:** `parse_query(None)` called where string required.

---

#### 3.3 ASTNode List Variance
**Location:** test_parser.py:413

**Error:** `Argument of type "list[ExactMatch]" cannot be assigned to parameter "elements" of type "list[ASTNode]"`

**Description:** Same variance issue as Message/Queue - `list` invariant prevents subclass substitution.

---

## Major Warning Categories

### 4. reportAny (Dynamic Mock Types)

**Files affected:** test_monitor.py (100+ occurrences), test_monitor_forward.py, test_task.py, test_config_reader.py

**Pattern:** Mock object attributes typed as `Any` due to dynamic nature of `unittest.mock.MagicMock`.

**Additional reportExplicitAny issues:**
- test_task.py:23, 25 - Explicit `Any` type usage in override patterns
- test_monitor_forward.py:56 - Explicit `Any` in type annotations

---

### 5. reportUnusedParameter

**Files affected:** test_monitor.py, test_monitor_forward.py, test_logging.py

**Unused parameters found:**
- test_monitor.py:389, 398, 408, 420, 437, 449, 453, 465, 483, 507, 508, 509, 526, 527, 528, 544, 545, 546, 571, 572, 573, 580, 581, 582, 593, 594, 595, 614, 615, 616, 640, 641, 662, 663, 664, 680, 681, 682

**Severity:** LOW - Dead code in fixtures, should be cleaned.

---

### 6. reportUnusedVariable

**File affected:** test_parser.py, test_task.py

**Unused variables:**
- test_parser.py:182, 203, 210, 228, 236, 243, 256, 262, 268, 297, 304, 311, 318, 324, 337, 342, 348, 356 (exclusions)
- test_task.py:241, 253 (content), 560 (args)

**Severity:** LOW - Test code that could be simplified.

---

### 7. reportUnusedCallResult

**Files affected:** All test files

**Pattern:** Function return values ignored (e.g., `Path(...)` result, `int` returned by model methods).

**Severity:** LOW - Acceptable in test context where calls are made for side effects.

---

### 8. reportMissingTypeStubs

**File affected:** test_monitor.py (line 423, 440, 456, 472), test_monitor_forward.py (line 9)

**Issue:** Missing type stubs for `telethon.errors` module.

**Severity:** INFO - External library limitation.

---

### 9. reportPrivateUsage

**File affected:** test_parser.py

**Private methods accessed in tests:**
- `_peek` (lines 140, 147)
- `_consume` (lines 152, 159, 166)
- `_parse_term` (line 250)

**Severity:** LOW - Tests accessing private implementation details.

---

### 10. reportUnreachable

**File affected:** test_monitor_forward.py

**Unreachable code:**
- line 114, 131, 151 (code after return/raise)

**Severity:** MEDIUM - Logic errors in test cases.

---

### 11. reportUnknownArgumentType & reportUnknownLambdaType

**File affected:** test_parser.py

**Locations:** lines 25, 37, 43

**Issue:** Lambda functions passed to `builds()` (pytest conjecture) have unknown parameter types.

---

## Recommendations

### Immediate Actions (HIGH Priority)

1. **test_config_reader.py:446-780** - Wrap string values in `SecretStr()` before passing to `ClientConfig` constructor to match production type signature.

2. **test_parser.py:558-587** - Add type annotations to the `build_function` helper function in test_parser.py.

3. **test_parser.py:437** - Fix attribute access on ASTNode or correct the test expectation.

4. **test_parser.py:283** - Do not pass `None` to `parse_query()` where `str` is required.

5. **test_monitor_forward.py:114,131,151** - Remove unreachable code branches.

### Best Practice Improvements (MEDIUM Priority)

6. **Consider variance changes in production code:**
   - Change `list[Message]` to `Sequence[Message]` in `process_messages` signature
   - Change `list[ASTNode]` to `Sequence[ASTNode]` in AST parser
   - Change `Queue[Task]` to covariant alternative for test compatibility

7. **Remove unused fixture parameters** in test_monitor.py and test_monitor_forward.py (mock_sender_tag, mock_message_link, mock_sleep).

8. **Remove unused variables** in test_parser.py (exclusions, inclusions in parametrize decorators).

### Observations (LOW Priority - Acceptable in Tests)

9. `reportAny` warnings are expected in test files using `MagicMock` - these do not indicate production code issues.

10. `reportUnusedCallResult` for `Path(...)` and model method calls are typical in tests.

---

## Files Not Showing Issues

- tests/test_config.py - No type errors
- tests/test_errors.py - No type errors
- tests/conftest.py - No type errors

---

## Error Distribution by File

| File | Errors | Warnings | Total |
|------|--------|----------|-------|
| test_config_reader.py | 28 | 48 | 76 |
| test_monitor.py | 33 | 300+ | 333 |
| test_parser.py | 4 | 60+ | 64 |
| test_monitor_forward.py | 0 | 20+ | 20 |
| test_task.py | 1 | 15+ | 16 |
| test_cli.py | 0 | 3 | 3 |
| test_logging.py | 0 | 4 | 4 |

---

*Report generated by basedpyright analyzer*