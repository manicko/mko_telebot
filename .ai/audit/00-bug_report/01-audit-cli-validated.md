---
name: audit-cli-validated
description: Validated findings for CLI entry point & command layer
agent: validator
alwaysApply: false
---

# Phase 01 Audit Findings - CLI Entry Point & Command Layer

**Executor:** auditor  
**Validator:** validator  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** validated  
**Validated:** yes

---

## Findings

### CLI-001: Unused settings property in TelepostConfigReader

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | src/mko_telepost/core/config_reader.py |
| **Classification** | advisory |

**Description:** The `settings` property in `TelepostConfigReader` (lines 257-270) is marked as "intended for future use" in its docstring but is never consumed by any code in the codebase. The property calls `self.load()` lazily if `_settings` is None, but all current usages explicitly call `reader.load()` instead of accessing `reader.settings`.

**Evidence:**
- `config_reader.py` lines 257-270 define the property with docstring: "Intended for future use by components that need to access settings without explicitly calling load()"
- Grep search found no usage of `reader.settings` or `config.settings` anywhere in the codebase
- All usages in the codebase call `reader.load()` explicitly to obtain settings

> **Validation Note:**
> - **Action:** validated
> - **Detail:** The property exists and is unused. The code is dead code - not referenced anywhere. Docstring correctly describes intent but implementation adds no value. Property adds complexity without utility.
> - **Recommendation:** Remove the unused property to reduce code complexity.

---

### CLI-002: Topic ID default value of 0 not validated

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telepost/core/models.py, src/mko_telepost/core/telegram_service.py, docs/SPEC.md |
| **Classification** | advisory |

**Description:** The `topic_id` field in `ChatConfig` (line 280) defaults to 0, which according to the Telegram API convention means "no topic". However, unlike `chat_id` which rejects 0 as a placeholder value (lines 301-312), there is no validation for `topic_id=0`.

**Evidence:**
- `models.py` line 280: `topic_id: int = Field(default=0, ...)` - No validator for topic_id
- `models.py` lines 301-312 validate `chat_id` to reject 0 but topic_id is unconstrained
- `telegram_service.py` lines 236-237: `reply_to=post.topic_id` - Telethon uses this directly
- `docs/SPEC.md` line 238 explicitly documents `topic_id` default as `0` with no validation constraint
- Telegram API: `reply_to=0` is valid and means "no topic reply" (not an error)

> **Rejection reason:** The behavior is correct per design. `topic_id=0` is a valid Telegram API value meaning "no topic" - this is explicitly documented in SPEC.md. Unlike `chat_id` where 0 is clearly a placeholder, `topic_id=0` represents the legitimate state of "not using a forum topic". Adding validation would be incorrect overengineering.

---

### CLI-003: README shows wrong field name for delay configuration

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | README.md, src/mko_telepost/core/models.py |
| **Classification** | advisory |

**Description:** The README documentation example (line 113) shows `delay_minutes: 10` but the actual configuration model in `ChatDefaults` and `ChatConfig` uses `min_delay_minutes`. Users following the README example would get a validation error due to `extra="forbid"` on Pydantic models.

**Evidence:**
- README.md line 113: `delay_minutes: 10` (shown in chat config example)
- `models.py` line 229: `min_delay_minutes: float = Field(..., description="Minimum delay between posts (minutes)")` in ChatDefaults
- `models.py` line 286: `min_delay_minutes: float | None = Field(..., description="Minimum delay between posts (minutes)")` in ChatConfig
- All Pydantic models enforce `extra="forbid"` - unknown fields are rejected with validation errors

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Verified the README screenshot uses the wrong field name `delay_minutes` instead of `min_delay_minutes`. The template file `app_config.yaml` correctly uses `min_delay_minutes`. This is a documentation error that will cause user configuration failures.
> - **See also:** CLI-004 shares root cause (README config example errors)

---

### CLI-004: README shows non-existent `posts:` config section

| Field | Value |
|-------|-------|
| **ID** | CLI-004 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | README.md |
| **Classification** | advisory |

**Description:** The README configuration example (lines 103-106) includes a `posts:` section with `max_photos`, `cache_dir`, and `max_retries` fields. However, this section does not exist in the actual Pydantic configuration model (`TelepostSettings`). All Pydantic models enforce `extra="forbid"`, meaning users copying the example would get validation errors.

**Evidence:**
- README.md lines 103-106: Shows `posts:` section with `max_photos`, `cache_dir`, `max_retries`
- `TelepostSettings` (models.py lines 374-393) has no `posts` field
- `max_photos` is actually under `chats.defaults` (ChatDefaults, line 241 in models.py)
- `max_retries` is under `telethon` (TelethonConfig, line 147 in models.py)
- `cache_dir` is internal to `ImageCache` class, not a config field (per SPEC.md line 399)

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed the README config example shows a `posts:` section that doesn't exist in the schema. This is a significant documentation error causing config validation failures. The fields exist but under different parent keys (`chats.defaults` and `telethon`).
> - **See also:** CLI-003 shares root cause (README config example errors)

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 1 |

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 3 | CLI-001, CLI-003, CLI-004 |
| Reclassified | 0 | — |
| Merged | 2 | CLI-003 + CLI-004 merged as related documentation errors |
| Rejected | 1 | CLI-002 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| CLI-002 | Topic ID default value of 0 not validated | The behavior is correct per design. `topic_id=0` is valid Telegram API semantics meaning "no topic". Explicitly documented in SPEC.md. Unlike `chat_id` where 0 is a placeholder, `topic_id=0` represents the legitimate state of "not using a forum topic". Adding validation would be incorrect overengineering. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| CLI-003 | CLI-004 | Both findings stem from the same root cause: incorrect configuration example in README.md. CLI-003 (wrong field name) and CLI-004 (non-existent section) should both be fixed in the same README update. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | No reclassifications required |

---