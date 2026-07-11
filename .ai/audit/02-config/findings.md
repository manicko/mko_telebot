---
name: 02-config-findings
description: Configuration & Pydantic Models audit findings
agent: auditor
alwaysApply: false
---

# Phase 02 Audit Findings — Configuration & Pydantic Models

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### CFG-001: Unused `LogLevel` StrEnum defined in channels.py but never consumed

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/channels.py |
| **Classification** | advisory |

**Description:** The `LogLevel` StrEnum class is defined in `channels.py` and exported via `__all__`, but it is never used in any configuration model or consumed by services. The documentation does not mention a log level configuration field, and the logging configuration (`log_config.yaml`) uses Python's standard string level names directly.

**Evidence:** 
- `src/mko_telebot/core/channels.py:10-17` defines `LogLevel(StrEnum)` with values DEBUG, INFO, WARNING, ERROR, CRITICAL
- `src/mko_telebot/core/channels.py:124` exports `LogLevel` in `__all__`
- No field in `ChannelsConfig`, `TelethonConfig`, or `TelepostSettings` uses `LogLevel` as a type
- `src/mko_telebot/logging.py` loads log config from YAML without consuming any `LogLevel` enum

**Recommendation:** Remove `LogLevel` StrEnum from `channels.py` as dead code. Effort: trivial.

---

### CFG-002: `defaults` in ChannelsConfig not applied to individual channels

| Field | Value |
|-------|-------|
| **ID** | CFG-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/channels.py, src/mko_telebot/core/task.py |
| **Classification** | mandatory |

**Description:** The `defaults` field in `ChannelsConfig` is documented as providing "fallback values for all channels" (see configuration.md), but these defaults are never applied to individual channel configurations. When a channel is created with `ChannelConfig(name="@test")`, it uses `ChannelConfig` model defaults (scan_interval=420, etc.), not the values from `settings.channels.defaults`. This is a fundamental mismatch between documented behavior and actual behavior.

**Evidence:**
- `src/mko_telebot/core/channels.py:65-90` defines `ChannelDefaults` with defaults of scan_interval=420, history_limit=50, etc.
- `src/mko_telebot/core/task.py:44-59` creates `Task` from `ChannelConfig`, accessing fields directly without merging `ChannelsConfig.defaults`
- `src/mko_telebot/monitor.py:323-336` iterates over `settings.channels.channels` and creates `Task(config=channel_settings)` - the `channel_settings` comes directly from the parsed `ChannelConfig`, not merged with defaults
- Running test: `channel = settings.channels.channels['test_channel']` produces `scan_interval: 420` even when `settings.channels.defaults.scan_interval` is set to `600`

**Recommendation:** Implement a model validator or factory method in `ChannelsConfig` that applies `defaults` values to each channel entry during validation, or explicitly merge defaults in `Task.__init__()`. Effort: small. Priority: mandatory (correctness issue).

---

### CFG-003: `keyw_config_example_keep.yaml` is a malformed example config

| Field | Value |
|-------|-------|
| **ID** | CFG-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/settings/keyw_config_example_keep.yaml |
| **Classification** | advisory |

**Description:** The `keyw_config_example_keep.yaml` file contains configuration examples that would fail Pydantic validation:
1. `DEFAULTS` key inside `channels` dict is validated as a `ChannelConfig`, but lacks required `name` field
2. Channel entries (`channel_1`, `channel_2`, `channel_3`) are empty dictionaries missing the required `name` field
3. The `DEFAULTS` dict contains `stagger_start_seconds` which is not a valid field for `ChannelConfig` (it belongs to `ChannelsConfig`)

**Evidence:**
- `src/mko_telebot/settings/keyw_config_example_keep.yaml:7-26` contains malformed structure
- Validation error when loading: `CHANNELS.channels.DEFAULTS.name - Field required`
- Validation error: `CHANNELS.channels.DEFAULTS.stagger_start_seconds - Extra inputs are not permitted`
- Validation error: `CHANNELS.channels.channel_1.name - Field required`

**Recommendation:** Either remove this file (it's not referenced in documentation) or fix it to match the documented schema in configuration.md. Effort: trivial. The file appears to be a legacy/work-in-progress example that should be cleaned up.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 2 |
| LOW | 0 |

## Mandatory Fixes

- CFG-002: `defaults` in ChannelsConfig not applied to individual channels

## Advisory Recommendations

- CFG-001: Unused `LogLevel` StrEnum defined in channels.py but never consumed
- CFG-003: `keyw_config_example_keep.yaml` is a malformed example config

---