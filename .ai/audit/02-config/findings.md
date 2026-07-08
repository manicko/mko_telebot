---
name: 02-config-audit
description: Configuration and Pydantic models audit findings
agent: auditor
status: complete
validated: no
---

# Phase 02 Audit Findings — Configuration & Pydantic Models

**Executor:** auditor  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** complete  
**Validated:** no

---

## Findings

### CFG-001: Monitor accesses non-existent 'monitoring' attribute on TelepostSettings

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | CRITICAL |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | mandatory |

**Description:** The `main_loop` function in monitor.py accesses `settings.monitoring.channels_delay`, `settings.monitoring.channels`, and `settings.monitoring.stagger_start_seconds` on lines 306, 307, and 310. However, the `TelepostSettings` model (defined in models.py) only has `telethon` and `channels` fields — there is no `monitoring` attribute. This will cause an `AttributeError` at runtime when `run_monitor` is called.

**Evidence:**
- `src/mko_telebot/monitor.py` lines 306-310:
  ```python
  channels_delay = settings.monitoring.channels_delay
  channels = settings.monitoring.channels
  stagger_start_seconds = settings.monitoring.stagger_start_seconds
  ```
- `src/mko_telebot/core/models.py` lines 24-33: TelepostSettings has only `telethon` and `channels` fields.
- Test shows: `AttributeError: 'TelepostSettings' object has no attribute 'monitoring'`

**Recommendation:** Change `settings.monitoring` to `settings.channels` to use the correct field name. The `ChannelsConfig` model already contains all the required properties (`channels_delay`, `channels`, `stagger_start_seconds`).

---

### CFG-002: Template config.yaml has invalid DEFAULTS key structure

| Field | Value |
|-------|-------|
| **ID** | CFG-002 |
| **Severity** | CRITICAL |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/settings/config.yaml, src/mko_telebot/core/channels.py |
| **Classification** | mandatory |

**Description:** The template `config.yaml` includes a `DEFAULTS` key inside the `channels` dict with fields that don't match `ChannelConfig` model. The `ChannelConfig` model requires a `name` field and does not accept `stagger_start_seconds`. Additionally, `stagger_start_seconds` is defined in `ChannelsConfig` (top-level), not in `ChannelDefaults`. When users run `init` and load the template config, validation fails with multiple errors.

**Evidence:**
- Validation error output when loading template config:
  ```
  TELETHON_API.phone_or_token: Value should have at least 5 items after validation, not 0
  TELETHON_API.client.api_id: Input should be greater than 0, not 0
  TELETHON_API.client.api_hash: Value should have at least 1 item after validation, not 0
  CHANNELS.channels.DEFAULTS.name: Field required [type=missing]
  CHANNELS.channels.DEFAULTS.stagger_start_seconds: Extra inputs are not permitted [type=extra_forbidden]
  ```
- `src/mko_telebot/settings/config.yaml` lines 5-14: DEFAULTS is nested under `channels` with `stagger_start_seconds`
- `src/mko_telebot/core/channels.py` line 103-104: `stagger_start_seconds` is a field of `ChannelsConfig`, not `ChannelDefaults`

**Recommendation:** Restructure the template `config.yaml` to place `DEFAULTS` at the top level of `CHANNELS` (alongside `channels_delay` and `stagger_start_seconds`), or implement a `model_validator(mode="before")` to properly handle the DEFAULTS key before validation.

---

### CFG-003: Documentation references non-existent ChatsConfig model

| Field | Value |
|-------|-------|
| **ID** | CFG-003 |
| **Severity** | MEDIUM |
| **Type** | DOC-UPDATE |
| **Affected Modules** | docs/11-guides/configuration.md |
| **Classification** | advisory |

**Description:** The documentation in `configuration.md` references a `ChatsConfig` model that does not exist in the codebase. The actual model is named `ChannelsConfig` (defined in `core/channels.py`).

**Evidence:**
- `docs/11-guides/configuration.md` line 117: "The root key `CHANNELS` maps to `ChatsConfig` in the Pydantic model"
- `docs/11-guides/configuration.md` line 121: "#### `ChatsConfig` (top-level monitoring)"
- `src/mko_telebot/core/channels.py` line 82: `class ChannelsConfig(BaseModel):`

**Recommendation:** Update documentation to reference `ChannelsConfig` instead of `ChatsConfig` to match the actual implementation.

---

### CFG-004: Template secrets.yaml has invalid empty credential values

| Field | Value |
|-------|-------|
| **ID** | CFG-004 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/settings/secrets.yaml |
| **Classification** | mandatory |

**Description:** The template `secrets.yaml` contains empty strings for required credential fields (`phone_or_token`, `api_hash`, `api_id=0`). While these are placeholder values for users to replace, the Pydantic validators reject empty values and `api_id=0` because they fail the minimum length and greater-than-0 constraints. The template cannot be loaded as-is even for testing user configurations.

**Evidence:**
- `src/mko_telebot/settings/secrets.yaml` shows `api_id: 0` and empty strings for required fields
- Validation errors from attempting to load template:
  - `phone_or_token`: min_length=5 constraint fails on empty string
  - `api_id`: gt=0 constraint fails on 0
  - `api_hash`: min_length=1 constraint fails on empty string

**Recommendation:** Use sentinel placeholder values that pass validation but are clearly identifiable as placeholders (e.g., `api_id: 1`, `phone_or_token: "YOUR_PHONE_OR_TOKEN"`, `api_hash: "YOUR_API_HASH"`). Add model validators comment indicating users must replace these values.

---

### CFG-005: set_offset_date method sets attribute before checking condition

| Field | Value |
|-------|-------|
| **ID** | CFG-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory |

**Description:** The `set_offset_date` method in `Task` class sets `self.offset_date = None` at the start (line 108), then checks `if not self.history_days` and returns early (lines 109-110). However, the attribute was already set to `None` on line 108, making the early return redundant.

**Evidence:**
- `src/mko_telebot/core/task.py` lines 106-110:
  ```python
  def set_offset_date(self) -> datetime | None:
      """Compute and store offset_date as (now - history_days) in UTC."""
      self.offset_date = None
      if not self.history_days:
          return None
  ```
- The early return is unnecessary since `self.offset_date` was already set to `None` on line 108.

**Recommendation:** Restructure to check `if self.history_days` before setting `self.offset_date = None`, or remove the redundant early return and let it fall through to compute the actual value.

---

### CFG-006: Root TelepostSettings model missing extra="forbid"

| Field | Value |
|-------|-------|
| **ID** | CFG-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/models.py |
| **Classification** | advisory |

**Description:** The `TelepostSettings` root model does not have `extra="forbid"` in its `model_config`, unlike the sub-models (`TelethonConfig`, `ChannelsConfig`, `ClientConfig`) which all have it. This means typos in the top-level config YAML keys will be silently ignored instead of raising validation errors.

**Evidence:**
- `src/mko_telebot/core/models.py` line 22: `model_config = ConfigDict(populate_by_name=True)` — no `extra="forbid"`
- `src/mko_telebot/core/telethon.py` line 23: `model_config = ConfigDict(extra="forbid")` on `ClientConfig`
- `src/mko_telebot/core/telethon.py` line 80: `model_config = ConfigDict(extra="forbid")` on `TelethonConfig`
- `src/mko_telebot/core/channels.py` line 33, 61, 92: all have `model_config = ConfigDict(extra="forbid")`

**Recommendation:** Add `extra="forbid"` to the `model_config` of `TelepostSettings` to catch typos in config file keys at the top level.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 2 |
| HIGH | 1 |
| MEDIUM | 2 |
| LOW | 1 |

## Mandatory Fixes

- CFG-001: Monitor accesses non-existent 'monitoring' attribute on TelepostSettings
- CFG-002: Template config.yaml has invalid DEFAULTS key structure
- CFG-004: Template secrets.yaml has invalid empty credential values

## Advisory Recommendations

- CFG-003: Documentation references non-existent ChatsConfig model
- CFG-005: set_offset_date method sets attribute before checking condition
- CFG-006: Root TelepostSettings model missing extra="forbid"

## Doc Updates Needed

- CFG-003: Documentation references non-existent ChatsConfig model