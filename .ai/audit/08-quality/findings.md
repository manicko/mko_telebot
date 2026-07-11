# Phase 08 Audit Findings — Code Quality, Security & Maintainability

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### QLT-001: Missing type hints on public function parameters

| Field | Value |
|-------|-------|
| **ID** | QLT-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py`, `src/mko_telebot/core/task.py` |
| **Classification** | advisory |

**Description:** Several public functions are missing type hints on parameters. Per project rules (type hints on all public functions), parameters `msg`, `msg_text`, `msg_media`, and `messages` should have explicit type annotations.

**Evidence:**
- `monitor.py:90`: `async def build_sender_tag(msg)` — missing type hint
- `monitor.py:120`: `async def forward_to_users(msg, msg_text, msg_media, ...)` — missing type hints
- `monitor.py:187`: `async def process_messages(messages, ...)` — missing type hint
- `task.py:61`: `async def resolve_targets_entities(self, client)` — missing type hint
- `task.py:78`: `async def resolve_channel_entity(self, client)` — missing type hint

These functions accept Telethon types but use untyped parameters, which reduces static analysis effectiveness.

**Recommendation:** Add type hints using `from typing import Any` for Telethon types that lack stubs, or import proper types. `Any` is acceptable for external library types without type stubs.

---

### QLT-002: Unused functions in core/utils.py

| Field | Value |
|-------|-------|
| **ID** | QLT-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/utils.py` |
| **Classification** | advisory |

**Description:** Two functions in `core/utils.py` are defined but never called. The module also duplicates the `resolve_path` function that already exists in `core/config.py`.

**Evidence:**
- `utils.py:12-36`: `list_files_in_directory()` — no callers found
- `utils.py:96-109`: `load_config()` — no callers found
- `utils.py:112-133`: `merge_dicts()` — no callers found (private `_merge_dicts` in config.py:78 is used instead)
- `utils.py:60-93`: `resolve_path()` — duplicates config.py:27-47 with different behavior

Note: `ensure_path_exists` at utils.py:39 IS used (task.py:94).

These functions are orphaned and consume maintenance overhead without providing value.

**Recommendation:** Investigate purpose of these functions. Either remove them or add usage documentation explaining their intended use. Consider removing in favor of the private `_merge_dicts` in config.py which is actively used.

---

### QLT-003: Unused dependency pydantic-settings

| Field | Value |
|-------|-------|
| **ID** | QLT-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `pyproject.toml` |
| **Classification** | advisory |

**Description:** The `pydantic-settings` package is listed in dependencies but not imported or used anywhere in the source code. The project uses plain `BaseModel` from pydantic instead of `BaseSettings`.

**Evidence:**
- `pyproject.toml:20`: `pydantic-settings>=2` in dependencies
- Grep search for `pydantic_settings` or `BaseSettings` returns no matches in source code

**Recommendation:** Remove `pydantic-settings` from dependencies to reduce attack surface and installation size. If settings functionality is needed later, it can be added back.

---

### QLT-004: Duplicate path resolution functions across modules

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/utils.py:60-93`, `src/mko_telebot/core/config.py:27-47` |
| **Classification** | advisory |

**Description:** Path resolution functionality exists in two places with slightly different implementations. Both `utils.resolve_path` and `config.resolve_path` perform similar operations but are inconsistent.

**Evidence:**
- `utils.py:60-93`: `resolve_path()` function with path existence creation
- `config.py:27-47`: `resolve_path()` function without creation logic
- Both files import Path and handle relative/absolute path resolution

This duplication creates confusion about which function to use and potential inconsistencies.

**Recommendation:** Consolidate into a single utility. Keep `config.resolve_path` for config-specific resolution (no creation) and remove the duplicate from `utils.py`.

---

### QLT-005: Broad Exception catches without specific handling

| Field | Value |
|-------|-------|
| **ID** | QLT-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py:393`, `src/mko_telebot/core/task.py:70,82,98,136,154`, `src/mko_telebot/core/config.py:173`, `src/mko_telebot/core/utils.py:34` |
| **Classification** | advisory |

**Description:** Multiple `except Exception as e` clauses catch overly broad exception types without distinguishing error categories. While not a bare `except:`, catching `Exception` broadly reduces the ability to handle different error types explicitly.

**Evidence:**
```
parser.py:393: except Exception as e:
task.py:70,82,98,136,154: except Exception as e: (5 instances)
config.py:173: except Exception as e:
utils.py:34: except Exception as err:
```

These broad catches make error handling less precise and can mask programming errors.

**Recommendation:** Where possible, catch more specific exception types. For Telethon API operations, use telethon-specific exceptions. For file I/O, catch `OSError`. Keep broad catches only for top-level handlers where re-raising with context is needed.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 4 |
| LOW | 1 |

## Advisory Recommendations

- QLT-001: Add type hints to public function parameters in monitor.py and task.py
- QLT-002: Remove or document unused functions in core/utils.py
- QLT-003: Remove pydantic-settings dependency from pyproject.toml
- QLT-004: Consolidate duplicate resolve_path functions
- QLT-005: Refactor broad Exception catches to use specific types

---

## Notes

No CRITICAL or HIGH severity issues found. The codebase follows project conventions well:
- No `print()` statements in production code (only `console.print` in cli.py which is allowed)
- No bare `except:` clauses
- No hardcoded secrets in source code
- No circular imports detected
- No unused imports detected by ruff
- All tests pass (164 passed)
- Linter and type checker pass cleanly