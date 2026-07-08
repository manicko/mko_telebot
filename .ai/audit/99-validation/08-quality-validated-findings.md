---
name: 08-quality-validated-findings
description: Validated Code Quality, Security & Maintainability Audit Findings
agent: validator
status: complete
validated: yes
---

# Phase 08 Audit Findings — Code Quality, Security & Maintainability (Validated)

**Executor:** validator
**Source:** `.ai/audit/08-quality/findings.md`
**Status:** complete
**Validated:** yes

---

## Findings

### QLT-001: Type error - TelepostSettings has no attribute 'monitoring'

| Field | Value |
|-------|-------|
| **ID** | QLT-001 |
| **Severity** | CRITICAL |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py, src/mko_telebot/core/models.py |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** Original type was `RUNTIME-ERROR`. Reclassified to `SPEC-DEVIATION` — the implementation in `monitor.py` accesses `settings.monitoring` which does not exist on `TelepostSettings`. The `ChannelsConfig` model at `src/mko_telebot/core/channels.py` already contains all referenced fields (`channels_delay`, `channels`, `stagger_start_seconds`), so the correct mapping is `settings.channels`.
> - **Evidence verified:** mypy confirms 3 errors on lines 306, 307, 310. `TelepostSettings` (models.py:11-33) has only `telethon` and `channels` fields. `ChannelsConfig` (channels.py:82-111) has `channels_delay`, `channels`, `stagger_start_seconds`.

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
- `src/mko_telebot/core/channels.py` lines 82-111: `ChannelsConfig` has all three referenced fields

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** All five methods confirmed lacking `-> None` return type hints by code inspection. Project rule requires type hints on all public functions. Fix is trivial and aligns with project standards.

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Code inspection confirms `_peek()` and `_consume()` lack type hints. While project rules only mandate public function type hints, adding them improves maintainability and IDE support. Recommendation is correct. Not rejected — the finding has practical value with trivial effort.

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Code inspection confirms `logger = logging.getLogger(__name__)` on line 18 is never referenced anywhere in the file (zero calls to `logger.`). The `import logging` on line 16 is also only used to create this unused logger — no other code reference to the `logging` module exists in the file (the word appears only in a docstring on line 132 describing the log config file path, not as a code reference). Spec cross-reference: no `docs/SPEC.md` exists; no models or config templates reference this logger. Dead code is confirmed.

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

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 3 | QLT-002, QLT-003, QLT-004 |
| Reclassified | 1 | QLT-001 (RUNTIME-ERROR → SPEC-DEVIATION) |
| Merged | 0 | — |
| Rejected | 0 | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| QLT-001 | RUNTIME-ERROR | SPEC-DEVIATION | Implementation references `settings.monitoring` which does not exist on `TelepostSettings`. The `ChannelsConfig` model already contains the referenced fields. This is a code implementation deviation from the model definition. |

### Cross-Phase Analysis

No cross-phase conflicts detected. Findings in this phase are independent of findings in phases 07 (tests) and 09 (structural quality). No dependency chains exist between QLT findings.

### Rollout Analysis

| Concern | Status | Details |
|---------|--------|---------|
| Circular dependencies | None | All findings are isolated to individual modules |
| Hidden dependency chains | None | No fix depends on another fix |
| Rollback feasibility | Safe | All recommendations are reversible and local |
| Fragile insertion points | None | All changes are simple replacements or additions |

### Warnings

None detected.

### Advisory Recommendations

- QLT-002, QLT-003, QLT-004 are low-risk, high-ROI improvements suitable for batch implementation.
- QLT-001 is a blocking bug — should be fixed before any deployment.
