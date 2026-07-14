# Phase 07 Audit Findings — Test Quality

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### TST-001: No direct tests for core/utils.py ensure_path_exists function

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/utils.py |
| **Classification** | advisory |

**Description:** The `ensure_path_exists()` function in `core/utils.py` is only tested indirectly through mocking in `test_task.py` (line 151 mocks it to force an error). There are no direct unit tests verifying the function's behavior with real file system operations - no tests for successful directory creation, file parent directory creation, or error handling with actual permissions.

**Evidence:** 
- `src/mko_telebot/core/utils.py` contains `ensure_path_exists()` (25 lines, handles path creation with error handling)
- Only reference in tests is mocking it: `tests/test_task.py:151` patches it with `side_effect=ValueError("Cannot create")`
- No test file directly imports or tests `ensure_path_exists` with real file operations

**Recommendation:** Add a dedicated test file (e.g., `tests/test_utils.py`) with tests for:
- Directory creation when path has no suffix (is directory)
- Parent directory creation when path has a suffix (is file)
- Successful return when path already exists
- Error handling for permission denied scenarios

### TST-002: No direct tests for core/matcher.py internal functions

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/matcher.py |
| **Classification** | advisory |

**Description:** The matcher module has 4 internal functions (`ast_to_regex`, `patterns_for_node`, `evaluate_query`, `_check_patterns_match`) that implement the core pattern matching logic. No tests directly target these functions - testing is only done through `search_match()` integration tests. This means bugs in regex generation or pattern evaluation could go undetected if they happen to produce a passing boolean result.

**Evidence:**
- `src/mko_telebot/core/matcher.py` lines 15-108 define `ast_to_regex`, `patterns_for_node`, `evaluate_query`, `_check_patterns_match`
- `tests/test_parser.py` tests `search_match` through `conftest.py` fixture but has no tests for:
  - Regex patterns generated from exact match / wildcard / or-operation nodes
  - Word boundary handling in regex patterns
  - Pattern combination for sequences
  - Exclusion pattern evaluation
- Grep finds no test references to `ast_to_regex`, `patterns_for_node`, `evaluate_query`, or `_check_patterns_match`

**Recommendation:** Add tests in `tests/test_matcher.py` to verify:
- `ast_to_regex` produces correct regex patterns for each AST node type
- Word boundary handling for patterns (leading/trailing `*` affects boundaries)
- `patterns_for_node` correctly flattens sequence nodes
- `evaluate_query` processes exclusions before inclusions correctly

### TST-003: No tests for PathResolver class in core/paths.py

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/paths.py |
| **Classification** | advisory |

**Description:** The `PathResolver` class provides utility methods (`resolve`, `ensure_dir`, `ensure_file_parent`) that are not covered by tests. While `AppPaths` model gets indirect coverage through other tests, the `PathResolver` class itself has no test coverage.

**Evidence:**
- `src/mko_telebot/core/paths.py` lines 27-76 define `PathResolver` class with 3 methods
- Grep for `PathResolver` in tests returns no matches

**Recommendation:** Add tests for `PathResolver.resolve()` with relative paths, absolute paths, and home directory expansion. Add tests for `ensure_dir()` creating nested directories and `ensure_file_parent()` handling parent creation.

### TST-004: No tests for _merge_dicts internal function in core/config.py

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/config.py |
| **Classification** | advisory |

**Description:** The `_merge_dicts()` function handles recursive dictionary merging for config overlay. It is tested indirectly through the `test_telethon_config_overlay_config_defaults` test in `test_config_reader.py`, but edge cases like deeply nested structures, empty overlays, or merging lists are not explicitly tested.

**Evidence:**
- `src/mko_telebot/core/config.py` lines 78-94 define `_merge_dicts`
- Only test coverage is via merged config integration tests
- No direct unit tests for the merge behavior

**Recommendation:** Add unit tests for `_merge_dicts` covering:
- Deeply nested dictionary merging
- Overlay value taking precedence for non-dict values
- Empty base/overlay edge cases
- Non-dict values replacing dict values

### TST-005: No tests for main.py entry point

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/main.py |
| **Classification** | advisory |

**Description:** The `main()` function in `main.py` is a trivial wrapper calling `app()`, but there is no test verifying the entry point works. This is a minor oversight since CLI tests cover the Typer app extensively.

**Evidence:**
- `src/mko_telebot/main.py` lines 6-8 define `main()` 
- No test imports or calls `main()` directly

**Recommendation:** Add a simple test in `tests/test_main.py` or extend `test_cli.py` to verify `main()` can be called without error.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 3 |

## Mandatory Fixes

None

## Advisory Recommendations

- TST-001: Add tests for `ensure_path_exists()` in `tests/test_utils.py`
- TST-002: Add tests for matcher internal functions in `tests/test_matcher.py`
- TST-003: Add tests for `PathResolver` class in `tests/test_paths.py`
- TST-004: Add tests for `_merge_dicts` edge cases
- TST-005: Add test for `main()` entry point

## Doc Updates Needed

None