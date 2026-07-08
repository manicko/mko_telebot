---
name: 08-quality-findings
description: Code Quality, Security & Maintainability Audit Findings
agent: auditor
status: complete
validated: no
---

# Phase 08 Audit Findings — Code Quality, Security & Maintainability

**Executor:** auditor
**Template:** `.ai/audit/templates/audit-findings.md`
**Status:** complete
**Validated:** no

---

## Findings

### QLT-001: Type error - TelepostSettings has no attribute 'monitoring'

| Field | Value |
|-------|-------|
| **ID** | QLT-001 |
| **Severity** | CRITICAL |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | src/mko_telebot/monitor.py, src/mko_telebot/core/models.py |
| **Classification** | mandatory |

**Description:** The `main_loop()` function in monitor.py accesses `settings.monitoring` on lines 306, 307, and 310, but the `TelepostSettings` model does not have a `monitoring` attribute. The model has `channels` and `telethon` attributes. This is a type-safety violation that would cause an AttributeError at runtime when the monitoring feature is used, preventing the application from starting correctly.

**Evidence:**
- `uv run mypy src\mko_telebot` output:
  ```
  src\mko_telebot\monitor.py:306: error: "TelepostSettings" has no attribute "monitoring"
  src\mko_telebot\monitor.py:307: error: "TelepostSettings" has no attribute "monitoring"
  src\mko_telebot\monitor.py:310: error: "TelepostSettings" has no attribute "monitoring"
  ```
- `src/mko_telebot/core/models.py` lines 11-33: `TelepostSettings` class defines only `telethon: TelethonConfig` and `channels: ChannelsConfig` attributes
- `src/mko_telebot/monitor.py` lines 306-310 show usage of `settings.monitoring.channels_delay`, `settings.monitoring.channels`, and `settings.monitoring.stagger_start_seconds`

**Recommendation:** Change `settings.monitoring` to `settings.channels` in monitor.py lines 306-310. The `ChannelsConfig` already contains `channels_delay`, `channels` (dict), and `stagger_start_seconds` properties. Effort: trivial.

---

### QLT-002: Missing type hints on public methods in Task class

| Field | Value |
|-------|-------|
| **ID** | QLT-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** Several public methods in the `Task` class are missing return type hints. According to project rules, all public functions must have type hints. Missing return type hints reduce code clarity and prevent static type checking from catching potential errors.

**Evidence:**
- `src/mko_telebot/core/task.py` line 61: `async def resolve_targets_entities(self, client):` - missing return type `-> None`
- `src/mko_telebot/core/task.py` line 78: `async def resolve_channel_entity(self, client):` - missing return type `-> None`
- `src/mko_telebot/core/task.py` line 90: `def resolve_state_file(self):` - missing return type `-> None`
- `src/mko_telebot/core/task.py` line 125: `async def load_state(self):` - missing return type `-> None`
- `src/mko_telebot/core/task.py` line 146: `async def save_state(self):` - missing return type `-> None`

**Recommendation:** Add `-> None` return type hints to all five methods. Effort: trivial.

---

### QLT-003: Missing type hints on private methods in PatternParser class

| Field | Value |
|-------|-------|
| **ID** | QLT-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `_peek()` and `_consume()` methods in `PatternParser` are missing return type hints. While these are private methods, adding type hints improves code maintainability and enables better IDE support.

**Evidence:**
- `src/mko_telebot/core/parser.py` line 145: `def _peek(self):` - missing return type `-> tuple[str, str] | None`
- `src/mko_telebot/core/parser.py` line 151: `def _consume(self, expected_type=None):` - missing return type and parameter type hint `expected_type: str | None`

**Recommendation:** Add type hints: `_peek(self) -> tuple[str, str] | None` and `_consume(self, expected_type: str | None = None) -> tuple[str, str] | None`. Effort: trivial.

---

### QLT-004: Unused logger variable in paths.py

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/paths.py |
| **Classification** | advisory |

**Description:** The `logger` variable is defined at line 18 but never used anywhere in the module. This is dead code that increases cognitive load and suggests incomplete implementation or leftover code from refactoring.

**Evidence:**
- `src/mko_telebot/core/paths.py` line 18: `logger = logging.getLogger(__name__)`
- No calls to `logger.` anywhere in the file

**Recommendation:** Remove the unused logger import and variable. Effort: trivial.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 2 |

## Mandatory Fixes

- QLT-001: Type error - TelepostSettings has no attribute 'monitoring'

## Advisory Recommendations

- QLT-002: Missing type hints on public methods in Task class
- QLT-003: Missing type hints on private methods in PatternParser class
- QLT-004: Unused logger variable in paths.py

---