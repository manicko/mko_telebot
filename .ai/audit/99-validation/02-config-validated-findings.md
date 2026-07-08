---
name: 02-config-validated-findings
description: Validated findings for Phase 02 — Configuration & Pydantic Models
agent: validator
status: complete
---

# Phase 02 Audit Findings — Configuration & Pydantic Models [VALIDATED]

**Executor:** validator  
**Source:** .ai/audit/02-config/findings.md  
**Validation date:** 2026-07-08  
**Status:** validated

---

## Findings

### CFG-001: Monitor accesses non-existent 'monitoring' attribute on TelepostSettings [VALIDATED]

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
- `src/mko_telebot/core/channels.py` line 82: The class is `ChannelsConfig`, containing `channels_delay`, `channels`, and `stagger_start_seconds` — confirming the correct attribute path is `settings.channels.*`.

**Recommendation:** Change `settings.monitoring` to `settings.channels` to use the correct field name. The `ChannelsConfig` model already contains all the required properties (`channels_delay`, `channels`, `stagger_start_seconds`).

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is accurate. Code at `monitor.py:306-310` references non-existent `monitoring` attribute. The field is named `channels` on `TelepostSettings`. Runtime `AttributeError` confirmed by code inspection. Recommendation is correct.

---

### CFG-002: Template config.yaml has invalid DEFAULTS key structure [VALIDATED]

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
- `src/mko_telebot/core/channels.py` lines 107-111: The `strip_defaults_from_channels` validator runs in `mode="after"`, meaning it cannot prevent validation failure on the DEFAULTS entry.
- `src/mko_telebot/core/channels.py` lines 55-79: `ChannelDefaults` model has no `stagger_start_seconds` field and no `name` field.

**Recommendation:** Restructure the template `config.yaml` to place `DEFAULTS` at the top level of `CHANNELS` (alongside `channels_delay` and `stagger_start_seconds`), or implement a `model_validator(mode="before")` to properly handle the DEFAULTS key before validation.

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is fully accurate. Two root causes confirmed: (1) `ChannelDefaults` model lacks `stagger_start_seconds` — this field is only on `ChannelsConfig`; (2) `strip_defaults_from_channels` validator is `mode="after"` so validation fails before it can strip DEFAULTS from the channels dict. The docs at `configuration.md:106-113` also show `stagger_start_seconds` inside DEFAULTS, so the template, model, and docs are all inconsistent with each other.

---

### CFG-003: Documentation references non-existent ChatsConfig model [VALIDATED]

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
- `docs/11-guides/configuration.md` line 306: "- `ChatsConfig` (from `CHANNELS` key)"
- `src/mko_telebot/core/channels.py` line 82: `class ChannelsConfig(BaseModel):`

**Recommendation:** Update documentation to reference `ChannelsConfig` instead of `ChatsConfig` to match the actual implementation.

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Three occurrences of `ChatsConfig` confirmed in documentation — the actual class is `ChannelsConfig`. Code is correct, docs are outdated. This is a genuine `DOC-UPDATE`.

---

### CFG-004: Template secrets.yaml has invalid empty credential values [VALIDATED]

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
- `src/mko_telebot/core/telethon.py` line 24: `api_id: int = Field(..., gt=0, ...)`
- `src/mko_telebot/core/telethon.py` line 25-27: `api_hash: SecretStr = Field(..., min_length=1, ...)`
- `src/mko_telebot/core/telethon.py` line 82-84: `phone_or_token: SecretStr = Field(..., min_length=5, ...)`
- Validation errors from attempting to load template:
  - `phone_or_token`: min_length=5 constraint fails on empty string
  - `api_id`: gt=0 constraint fails on 0
  - `api_hash`: min_length=1 constraint fails on empty string

**Recommendation:** Use sentinel placeholder values that pass validation but are clearly identifiable as placeholders (e.g., `api_id: 1`, `phone_or_token: "YOUR_PHONE_OR_TOKEN"`, `api_hash: "YOUR_API_HASH"`). Add model validators comment indicating users must replace these values.

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is accurate — template secrets fail basic Pydantic constraints. **However, the recommendation is partially flawed:** the custom validators in `telethon.py` reject values starting with `YOUR_` (lines 42-46, 94-100) and reject `api_id=12345` (lines 62-67), so naive sentinel values like `"YOUR_PHONE_OR_TOKEN"` and `"YOUR_API_HASH"` would themselves fail validation. Any fix must account for these existing placeholder-detection validators.

---

### CFG-005: set_offset_date method sets attribute before checking condition [VALIDATED]

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is technically correct — the early return is redundant. However, this is a trivial stylistic issue with zero functional impact. The recommendation has low operational value; fixing it would not affect correctness or maintainability in any meaningful way.

---

### CFG-006: Root TelepostSettings model missing extra="forbid" [VALIDATED]

| Field | Value |
|-------|-------|
| **ID** | CFG-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/models.py |
| **Classification** | advisory |

**Description:** The `TelepostSettings` root model does not have `extra="forbid"` in its `model_config`, unlike all sub-models (`TelethonConfig`, `ChannelsConfig`, `ClientConfig`, `ChannelConfig`, `ChannelDefaults`) which all have it. This means typos in the top-level config YAML keys will be silently ignored instead of raising validation errors.

**Evidence:**
- `src/mko_telebot/core/models.py` line 22: `model_config = ConfigDict(populate_by_name=True)` — no `extra="forbid"`
- `src/mko_telebot/core/telethon.py` line 23: `model_config = ConfigDict(extra="forbid")` on `ClientConfig`
- `src/mko_telebot/core/telethon.py` line 80: `model_config = ConfigDict(extra="forbid")` on `TelethonConfig`
- `src/mko_telebot/core/channels.py` line 33: `model_config = ConfigDict(extra="forbid")` on `ChannelConfig`
- `src/mko_telebot/core/channels.py` line 61: `model_config = ConfigDict(extra="forbid")` on `ChannelDefaults`
- `src/mko_telebot/core/channels.py` line 92: `model_config = ConfigDict(extra="forbid")` on `ChannelsConfig`

**Recommendation:** Add `extra="forbid"` to the `model_config` of `TelepostSettings` to catch typos in config file keys at the top level. This is compatible with `populate_by_name=True` — both can coexist in a single `ConfigDict`.

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Finding is accurate and well-supported by evidence. All 5 sub-models consistently use `extra="forbid"`; the root model is the only outlier. Fix cost is ~1 line and follows the established pattern.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 6 | CFG-001, CFG-002, CFG-003, CFG-004, CFG-005, CFG-006 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

All 6 findings are validated as-is. No findings were reclassified, merged, or rejected.

### Rollout Analysis

| Finding | Dependency | Risk Level | Notes |
|---------|-----------|------------|-------|
| CFG-001 | None | **HIGH** | Runtime crash on `main_loop()` entry — release blocker |
| CFG-002 | CFG-004 | **HIGH** | Template `config.yaml` fails validation due to combined config+secrets load. Fix sequencing: fix CFG-004 sentinels first, then CFG-002 template structure. |
| CFG-003 | None | LOW | Independent doc fix, no code changes needed |
| CFG-004 | CFG-001 | **HIGH** | Template `secrets.yaml` fails validation — init flow unusable. Must ensure sentinel values pass both basic constraints AND custom validators. |
| CFG-005 | None | LOW | Zero functional impact, fully independent |
| CFG-006 | None | LOW | Simple one-line config addition, low risk of regression |

**Dependency chain identified:** CFG-004 → CFG-002 (fix sentinels first to isolate DEFAULTS validation errors from credential validation errors).

### Warnings

1. **CFG-004 recommendation is partially flawed** — The suggested sentinel values `"YOUR_PHONE_OR_TOKEN"` and `"YOUR_API_HASH"` would themselves be rejected by the custom validators in `telethon.py` (lines 42-46, 94-100) which reject any value starting with `YOUR_`. The fix must either disable placeholder detection for template-init flows or use different sentinel values (e.g., `"PLACEHOLDER_REPLACE_ME_PHONE"`).

2. **No SPEC.md exists** — The project has no `docs/SPEC.md` file referenced in the guidelines. This means the "dead code" spec cross-reference procedure cannot be applied for this project. All CFG findings were validated against code and models directly.

3. **`stagger_start_seconds` inconsistency** — The docs (`configuration.md:136`) list `stagger_start_seconds` as a `ChannelDefaults` field, but the `ChannelDefaults` model in `channels.py:55-79` does not have this field — it's a top-level `ChannelsConfig` field (`channels.py:103-104`). This is a secondary docs-vs-model mismatch (related to but not explicitly covered by CFG-002 or CFG-003).

### Required Fixes

| ID | Severity | Classification | Action |
|----|----------|---------------|--------|
| CFG-001 | CRITICAL | SPEC-DEVIATION | Replace `settings.monitoring.*` with `settings.channels.*` in `monitor.py:306-310` |
| CFG-002 | CRITICAL | SPEC-DEVIATION | Restructure template `config.yaml` OR change `strip_defaults_from_channels` to `mode="before"` and align `ChannelDefaults` model |
| CFG-004 | HIGH | SPEC-DEVIATION | Replace empty/invalid placeholder values in `secrets.yaml` with valid sentinels that pass both basic constraints and custom validators |

### Advisory Recommendations

| ID | Severity | Type | Action |
|----|----------|------|--------|
| CFG-003 | MEDIUM | DOC-UPDATE | Rename `ChatsConfig` → `ChannelsConfig` in `configuration.md` (3 occurrences) |
| CFG-006 | MEDIUM | BEST-PRACTICE | Add `extra="forbid"` to `TelepostSettings.model_config` |
| CFG-005 | LOW | BEST-PRACTICE | Minor code clarity improvement in `set_offset_date()` — optional, low value |
| — | LOW | DOC-UPDATE | Fix `stagger_start_seconds` documentation: it appears as a `ChannelDefaults` field in docs but is actually on `ChannelsConfig` |