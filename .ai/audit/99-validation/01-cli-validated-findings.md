---
name: 01-cli
description: Validated audit findings for CLI Entry Point & Command Layer
agent: validator
status: validated
validated: yes
---

# Phase 01 Audit Findings — CLI Entry Point & Command Layer (Validated)

**Executor:** auditor  
**Validator:** validator  
**Status:** validated  
**Validated:** yes

---

## Findings

### CLI-001: Missing type hints on public functions in monitor.py

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | mandatory |

**Description:** Multiple public functions in monitor.py lack type hints for parameters and return values. This violates the project rule requiring type hints on all public functions.

**Evidence:**
- `monitor.py:71` - `def build_message_link(msg) -> str | None:` - parameter `msg` untyped
- `monitor.py:90` - `async def build_sender_tag(msg):` - no type hints on parameter or return
- `monitor.py:120` - `async def forward_to_users(msg, msg_text, msg_media, ...)` - first 3 params untyped

**Recommendation:** Add explicit type hints using `from telethon.tl.custom.message import Message` for type annotations.

> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** Changed from BEST-PRACTICE to SPEC-DEVIATION. The project rules explicitly require "Type hints on all public functions". This is a specification deviation, not an optional improvement.
> - **See also:** CLI-004 (related to same module)

---

### CLI-002: Duplicate `resolve_path` function in utils.py and config.py

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/utils.py`, `src/mko_telebot/core/config.py` |
| **Classification** | advisory |

**Description:** `resolve_path` function exists in both `utils.py` (lines 60-93) and `config.py` (lines 27-47) with nearly identical implementations. The one in `config.py` is exported via `core/__init__.py`, but `utils.py` version exists and may cause confusion.

**Evidence:**
- `utils.py:60-93` - `resolve_path` function with full implementation including `ensure_path_exists`
- `config.py:27-47` - simpler `resolve_path` without path creation
- Both functions handle path resolution and home-directory expansion
- `__init__.py` imports `resolve_path` from `config` only, not `utils`

**Recommendation:** Remove the duplicate from `utils.py` and ensure all internal references use the version from `config.py`. This reduces code duplication and maintenance burden.

> **Validation Note:**
> - **Action:** validated
> - **Detail:** The `resolve_path` in `utils.py` is unused (not exported from `__init__.py`, no imports found). The `config.py` version is used and exported. This is genuine duplication that introduces maintenance risk.
> - **See also:** —

---

### CLI-003: Improper exception specificity in `run` command masks root cause

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/cli.py` |
| **Classification** | advisory |

**Description:** The `run` command catches `MkoTelebotError` and `KeyboardInterrupt` together, producing generic "Failed to run monitor" output regardless of actual error. Users cannot distinguish between configuration errors, authentication failures, or interrupts.

**Evidence:**
- `cli.py:99` - `except (MkoTelebotError, KeyboardInterrupt):` both handled identically
- `cli.py:100` - `console.print("[red]Error:[/red] Failed to run monitor")` - same message for all error types

**Recommendation:** Separate exception handling to provide actionable messages: configuration/auth errors should suggest fixing config files, KeyboardInterrupt should indicate graceful shutdown (or no message at all since it's intentional).

> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** Changed from BEST-PRACTICE to SPEC-DEVIATION. The project rules require "Use custom exceptions from core/errors.py. Never silently swallow errors." The `KeyboardInterrupt` handling is particularly problematic as it masks user-initiated shutdown and reports it as an error.
> - **See also:** —

---

### CLI-004: Unnecessary exception handlers for non-raising code in monitor.py

| Field | Value |
|-------|-------|
| **ID** | CLI-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | advisory |

**Description:** The `build_message_link` function catches `TelegramServiceError` (lines 85-87), but the code inside the try block (lines 80-84) does not raise this exception - it only uses `getattr` and string formatting. Same issue in `process_messages` where `TelegramServiceError` is caught around non-raising code.

**Evidence:**
- `monitor.py:80-84` - Only uses `getattr` and f-string, no Telegram API calls
- `monitor.py:85-87` - Catches `TelegramServiceError` but this exception cannot be raised by the preceding code
- `monitor.py:216-220` - Same issue in `process_messages` where `TelegramServiceError` is caught around non-raising code

**Recommendation:** Remove the unnecessary exception handlers in `build_message_link` (lines 85-87) and `process_messages` (lines 216-220).

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed that `TelegramServiceError` is only raised in `task.py` (lines 74, 86) during entity resolution. The `build_message_link` function contains no code path that could raise this exception. The `process_messages` try block (lines 202-214) uses only `getattr`, list operations, and string formatting - no exception-raising operations.
> - **See also:** —

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 1 |

---

## Mandatory Fixes

- CLI-001: Missing type hints on public functions in monitor.py
- CLI-003: Improper exception specificity in `run` command masks root cause

---

## Advisory Recommendations

- CLI-002: Duplicate `resolve_path` function in utils.py and config.py
- CLI-004: Unnecessary exception handlers for non-raising code in monitor.py

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | CLI-002, CLI-004 |
| Reclassified | 2 | CLI-001, CLI-003 |
| Merged | 0 | — |
| Rejected | 0 | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| CLI-001 | BEST-PRACTICE | SPEC-DEVIATION | Project rules explicitly require type hints on all public functions |
| CLI-003 | BEST-PRACTICE | SPEC-DEVIATION | Project rules require proper error handling; KeyboardInterrupt masking user shutdown violates this |

### Rejected Findings

No findings rejected.

### Architectural Observations

1. **Exception handling inconsistency**: `TelegramServiceError` is caught in `build_message_link` and `build_sender_tag` but never raised there. These catch blocks are defensive dead code that could obscure actual bugs.

2. **Code duplication risk**: The duplicate `resolve_path` in `utils.py` is not currently causing issues because it's not exported, but represents a maintenance liability if future code accidentally imports from the wrong module.

3. **CLI error messaging**: The generic error message in `run` command provides no diagnostic value. Users cannot determine if the failure was due to configuration, authentication, network, or intentional interruption.