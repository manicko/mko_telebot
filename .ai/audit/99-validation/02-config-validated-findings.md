---
name: 02-config-validated
description: Validated audit findings for Configuration & Pydantic Models
agent: validator
status: validated
validated: yes
---

# Phase 02 Audit Findings — Configuration & Pydantic Models (Validated)

**Executor:** auditor
**Validator:** validator
**Status:** validated
**Validated:** yes

---

## Findings

### CFG-001: ~~Unused `LogLevel` StrEnum defined in channels.py but never consumed~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/channels.py |
| **Classification** | advisory |

> **Rejection reason:** Low ROI for removal at this project scale. `LogLevel` is a StrEnum following project patterns for constants, is documented in `__all__`, and no specification requires its removal. It is not causing functional issues and may be intended for future use. The principle of avoiding unnecessary changes applies here.

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

**Recommendation:** Add a model validator in `ChannelsConfig` (after line 121) that merges defaults into each channel during validation:

```python
from pydantic import model_validator

@model_validator(mode="after")
def apply_defaults_to_channels(self) -> ChannelsConfig:
    """Merge defaults into each channel config."""
    for channel_name, channel in self.channels.items():
        for field_name, default_value in self.defaults.model_dump().items():
            if getattr(channel, field_name, None) is None and default_value is not None:
                setattr(channel, field_name, default_value)
            elif getattr(channel, field_name, None) == channel.model_fields[field_name].default:
                setattr(channel, field_name, default_value)
    return self
```

Alternatively, in `Task.__init__` (task.py line 51-59), merge defaults after extracting config:
- Add `defaults = settings.channels.defaults` and apply field-by-field merge for any `None` or default values in the channel config.

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed that `defaults` is documented behavior in `configuration.md` (line 122: "Each channel inherits these values unless it explicitly overrides a field") but the implementation does not apply defaults. `Task.__init__` reads values directly from `ChannelConfig` without reference to `ChannelsConfig.defaults`. This is a genuine SPEC-DEVIATION between documentation and implementation.
> - **See also:** —

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

**Recommendation:** Replace `keyw_config_example_keep.yaml` contents with valid schema matching `channels` structure:

```yaml
# Delete the malformed file or replace with:
channels:
  # Each channel requires a name field
  channel_1:
    name: "@your_channel"
    keywords: ["keyword1", "keyword2"]
    forward_to: ["@target_channel"]
  # Or remove the file entirely if unused
```

The file is copied to user config via `cli.py:init()` but causes validation errors. Either remove from template or fix to be a valid example per the documented schema in configuration.md.

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed the file is copied to user config directory via `cli.py:init()` (line 56-64 copies all files from `app_settings_dir`). The file structure is invalid: `DEFAULTS` inside `channels` is validated as `ChannelConfig` (missing `name`), and `channel_1/2/3` entries are empty dicts missing required `name`. This is accessible to users via `mko-telebot init` and would cause validation errors.
> - **See also:** —

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- CFG-002: `defaults` in ChannelsConfig not applied to individual channels

## Advisory Recommendations

- CFG-003: `keyw_config_example_keep.yaml` is a malformed example config

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | CFG-002, CFG-003 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 1 | CFG-001 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| CFG-001 | Unused `LogLevel` StrEnum defined in channels.py but never consumed | Low ROI for removal; StrEnum exists as documented constants, no spec reference requires removal, not causing functional issues |

### Reclassified Findings

No findings reclassified.

### Architectural Observations

1. **Documentation/Implementation mismatch**: The `defaults` feature in `ChannelsConfig` is documented as providing fallback values (configuration.md line 122), but `Task` never references `settings.channels.defaults`. This is a functional bug affecting configuration usability.

2. **Invalid example file distributed**: The `keyw_config_example_keep.yaml` file is copied to user config directories but contains invalid configuration that would fail Pydantic validation. Users editing this file without understanding the schema would encounter confusing errors.

3. **No circular dependencies detected**: All three findings are independent with no cross-dependencies preventing implementation.