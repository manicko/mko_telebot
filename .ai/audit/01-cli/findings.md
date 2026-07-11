---
name: 01-cli
description: Audit findings for CLI Entry Point & Command Layer
executor: auditor
status: complete
validated: no
template: .ai/audit/templates/audit-findings.md
---

# Phase 01 Audit Findings — CLI Entry Point & Command Layer

**Executor:** auditor  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** complete  
**Validated:** no

---

## Findings

### CLI-001: Missing type hints on public functions in monitor.py

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | mandatory |

**Description:** Multiple public functions in monitor.py lack type hints for parameters and return values. This violates the project rule requiring type hints on all public functions.

**Evidence:**
- `monitor.py:71` - `def build_message_link(msg) -> str | None:` - parameter `msg` untyped
- `monitor.py:90` - `async def build_sender_tag(msg):` - no type hints on parameter or return
- `monitor.py:120` - `async def forward_to_users(msg, msg_text, msg_media, ...)` - first 3 params untyped

**Recommendation:** Add explicit type hints using `from telethon.tl.custom.message import Message` and `from telethon import TelegramClient` for type annotations.

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
- `utils.py:60-93` - `resolve_path` function with docstring
- `config.py:27-47` - duplicate `resolve_path` function with slightly different docstring
- Both functions handle path resolution and home-directory expansion

**Recommendation:** Remove the duplicate from `utils.py` and ensure all internal references use the version from `config.py`. This reduces code duplication and maintenance burden.

---

### CLI-003: Improper exception specificity in `run` command masks root cause

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/cli.py` |
| **Classification** | advisory |

**Description:** The `run` command catches `MkoTelebotError` and `KeyboardInterrupt` together, producing generic "Failed to run monitor" output regardless of actual error. Users cannot distinguish between configuration errors, authentication failures, or interrupts.

**Evidence:**
- `cli.py:99` - `except (MkoTelebotError, KeyboardInterrupt):` both handled identically
- `cli.py:100` - `console.print("[red]Error:[/red] Failed to run monitor")` - same message for all error types

**Recommendation:** Separate exception handling to provide actionable messages: configuration/auth errors should suggest fixing config files, KeyboardInterrupt should indicate graceful shutdown (or no message at all since it's intentional).

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

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 2 |
| LOW | 1 |

---

## Mandatory Fixes

- CLI-001: Missing type hints on public functions in monitor.py

---

## Advisory Recommendations

- CLI-002: Duplicate `resolve_path` function in utils.py and config.py
- CLI-003: Improper exception specificity in `run` command masks root cause
- CLI-004: Unnecessary exception handlers for non-raising code in monitor.py

---