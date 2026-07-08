---
name: 06-data-flow-validated-findings
description: End-to-end data flow audit findings — validated
agent: validator
status: complete
source: .ai/audit/06-data-flow/findings.md
---

# Phase 06 Audit Findings — End-to-End Data Flow [VALIDATED]

**Executor:** validator  
**Source:** `.ai/audit/06-data-flow/findings.md`  
**Status:** complete  
**Validated:** yes

---

## Runtime Verification Results

The runtime verification is informational and not subject to validation changes. Results confirmed: all modules importable, ruff passes, mypy passes (10 source files), 103 tests pass in 2.28s.

---

## Findings

### DF-001: `settings.monitoring` referenced but `TelepostSettings` has no `monitoring` attribute

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | CRITICAL |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Evidence confirmed. `monitor.py` lines 306-310 access `settings.monitoring.channels_delay`, `settings.monitoring.channels`, and `settings.monitoring.stagger_start_seconds`. `TelepostSettings` (models.py) defines `channels: ChannelsConfig` — there is no `monitoring` attribute. This will raise `AttributeError` at runtime. The correct access is `settings.channels.*`. DF-002 is merged into this finding (same root cause).
> - **See also:** DF-002 (merged)

**Description:** The `main_loop` function in `monitor.py` (lines 306-310) accesses `settings.monitoring.channels_delay`, `settings.monitoring.channels`, and `settings.monitoring.stagger_start_seconds`. However, `TelepostSettings` (defined in `core/models.py`) only has `telethon` and `channels` fields — there is no `monitoring` attribute. This causes an `AttributeError` at runtime when the monitor is run, breaking the entire data flow pipeline.

**Evidence:**
- `src/mko_telebot/monitor.py` lines 306-310:
  ```python
  channels_delay = settings.monitoring.channels_delay
  channels = settings.monitoring.channels
  stagger_start_seconds = settings.monitoring.stagger_start_seconds
  ```
- `src/mko_telebot/core/models.py` lines 24-33: `TelepostSettings` has only `telethon` and `channels` fields
- `src/mko_telebot/core/channels.py` lines 82-105: The `channels` field is of type `ChannelsConfig` which contains `channels_delay` and `stagger_start_seconds`

The correct access pattern should be `settings.channels.channels_delay`, `settings.channels.channels`, and `settings.channels.stagger_start_seconds`.

**Recommendation:** Change `settings.monitoring` to `settings.channels` in `monitor.py` lines 306-310. The `ChannelsConfig` model already contains all the required properties (`channels_delay`, `channels`, `stagger_start_seconds`). Effort: trivial - single line change.

---

### DF-002: Config propagation trace reveals structural mismatch between `ChannelsConfig` and expected `monitoring` attribute [MERGED INTO DF-001]

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/models.py, src/mko_telebot/monitor.py |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** merged into DF-001
> - **Detail:** DF-002 shares the exact same root cause as DF-001: `monitor.py` accesses `settings.monitoring` but the model exposes `settings.channels`. The secondary observation about audit spec references to `posts.*` and `chats.*` is a separate doc issue (see DF-003). No new actionable information beyond what DF-001 captures.

**Description:** The audit phase specification requires tracing `telethon.*`, `posts.*`, and `chats.*` config sections to their consumers. However, the codebase structure does not match the spec: there is no `posts.*` or `chats.*` config section, and the `telethon.*` config correctly flows through the client but the `monitoring.*` section is misnamed as `channels.*`. The data flow breaks at the model boundary because `monitor.py` expects `settings.monitoring.channels` but the Pydantic model provides `settings.channels.channels`.

**Evidence:**
- `src/mko_telebot/core/models.py`: `TelepostSettings` has `telethon: TelethonConfig` and `channels: ChannelsConfig`
- `src/mko_telebot/core/channels.py`: `ChannelsConfig` contains `channels_delay`, `stagger_start_seconds`, and `channels` dict
- `src/mko_telebot/monitor.py` line 306-310: Incorrectly accesses `settings.monitoring.channels_delay` instead of `settings.channels.channels_delay`
- The audit spec lines 67-73 reference `google_sheets.*`, `telethon.*`, `posts.*`, `chats.*` config sections — but only `telethon.*` and `channels.*` actually exist

**Recommendation:** Either rename `channels` to `monitoring` in `TelepostSettings` and `ChannelsConfig`, or update `monitor.py` to use the correct attribute names. The current mismatch causes runtime crashes. Effort: trivial - rename either the model field or the access pattern.

---

### DF-003: Audit spec references Google Sheets integration and PostProcessor/ImageCache that do not exist [RECLASSIFIED]

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | HIGH |
| **Type** | ~~SPEC-DEVIATION~~ → **DOC-UPDATE** |
| **Affected Modules** | Audit phase specification |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** The codebase is correct — no Google Sheets integration exists because the project is a Telegram-to-Telegram channel monitor, not a Google Sheets publisher. The audit phase spec (`.kilo/commands/audit/phases/06-audit-data-flow.md`) was apparently templated from a different project. The finding is about the audit spec being out of date, not about a code defect. Cross-phase duplicate with INT-001 (Phase 05).
> - **See also:** INT-001 (Phase 05 — same root cause, audit template needs updating)

**Description:** The audit phase specification (lines 26, 69, 82-87, 110-112) explicitly audits a Google Sheets → Telegram publishing pipeline with `GSheetsReader`, `PostProcessor`, `ImageCache`, and `TelegramPoster` classes. However, the actual codebase is a Telegram channel monitor that forwards messages from Telegram channels to Telegram targets. There is no Google Sheets integration, no image caching, and no `GSheetsReader` class.

**Evidence:**
- `src/mko_telebot/monitor.py`: Contains `process_messages`, `forward_to_users`, `process_task` functions — no Google Sheets code
- No `gspread`, `google`, or `sheet` imports anywhere in `src/`
- No `ImageCache`, `PostProcessor`, or `TelegramPoster` classes exist
- `search_match` function in `parser.py` is used for keyword matching on Telegram message text, not post extraction from sheets

**Recommendation:** Update the audit phase specification to reflect the actual architecture: this is a Telegram-to-Telegram forwarder, not a Google Sheets publisher. Effort: trivial - documentation update.

---

### DF-004: `telethon.*` config correctly propagates but `max_retries` is unused in message sending

| Field | Value |
|-------|-------|
| **ID** | DF-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/telethon.py, src/mko_telebot/monitor.py |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Evidence confirmed. `TelethonConfig.max_retries` (telethon.py line 85-87) defined but never read in `forward_to_users` (monitor.py lines 121-173). Cross-phase duplicate with INT-004 (Phase 05). The BEST-PRACTICE classification is appropriate — this is a real inconsistency, but the fix (either implement retry or remove the field) is advisory at this project scale given existing FloodWaitError handling.
> - **See also:** INT-004 (Phase 05 — same issue)

**Description:** The `TelethonConfig.max_retries` field (line 85-87 in `telethon.py`) defines retry attempts for message sending but is never used in `monitor.py`. The `forward_to_users` function has no retry logic for Telegram API calls — failures are logged but not retried.

**Evidence:**
- `src/mko_telebot/core/telethon.py` line 85-87: `max_retries: int = Field(default=5, ge=1, le=20, description="Max retry attempts for sending messages")`
- `src/mko_telebot/monitor.py` lines 121-173: `forward_to_users` has no retry loop; messages are sent once with only `FloodWaitError` handled specially
- `src/mko_telebot/monitor.py` line 169-172: Only `TelegramServiceError` is logged, no retries occur

**Recommendation:** Either implement retry logic using `max_retries` in `forward_to_users`, or remove the unused field from `TelethonConfig` to avoid confusion. Effort: medium - requires adding retry loop around send operations.

---

### DF-005: Template config.yaml has incorrect DEFAULTS structure preventing valid config load

| Field | Value |
|-------|-------|
| **ID** | DF-005 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/settings/config.yaml |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Evidence confirmed. The template `config.yaml` places `DEFAULTS` inside the `channels` dict. `ChannelConfig` requires a `name` field (no default), so `DEFAULTS` fails validation before the `strip_defaults_from_channels` validator can remove it. Also, `stagger_start_seconds` is a field of `ChannelsConfig` (channels.py line 103), not `ChannelDefaults`, so it's structurally misplaced even when parsed.

**Description:** The template `config.yaml` places `DEFAULTS` inside the `channels` dictionary with invalid field combinations. When users run `init` and then `validate` or `run`, the configuration fails validation because: (1) `name` field is required in `ChannelConfig` but missing in `DEFAULTS`, (2) `stagger_start_seconds` is a `ChannelsConfig` field but placed under `channels.DEFAULTS`.

**Evidence:**
- `src/mko_telebot/settings/config.yaml` lines 5-14: `DEFAULTS` is nested under `channels` with `stagger_start_seconds`
- `src/mko_telebot/core/channels.py` line 103-104: `stagger_start_seconds` is a field of `ChannelsConfig`, not `ChannelDefaults`
- The `strip_defaults_from_channels` validator in `ChannelsConfig` removes the `DEFAULTS` key but the structure is still wrong

**Recommendation:** Move `DEFAULTS` to the top level of `CHANNELS` alongside `channels_delay` and `stagger_start_seconds` to match the `ChannelsConfig` model. Effort: trivial - restructure the YAML.

---

### DF-006: No centralized state cleanup on failure paths

| Field | Value |
|-------|-------|
| **ID** | DF-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Evidence confirmed. `run_monitor` (lines 330-341) and `main_loop` (lines 292-328) have no `try/finally` cleanup. The only interrupt handling is in `launcher` (line 351). `asyncio.run()` handles some cleanup, but state persistence is not guaranteed on interrupt. The finding is a valid BEST-PRACTICE observation at low effort.

**Description:** The audit spec requires that cleanup runs on both success and failure paths (lines 111-112). However, while the codebase has state persistence via `Task.save_state()`, there is no image cache cleanup (since `ImageCache` doesn't exist) and no guaranteed state consistency cleanup on failures. The `main_loop` has no cleanup mechanism.

**Evidence:**
- `src/mko_telebot/monitor.py` lines 330-341: `run_monitor` runs the loop but has no cleanup wrapper
- `src/mko_telebot/monitor.py` line 249: `task.last_msg_id` is only updated after successful processing
- No `try/finally` blocks around the main monitoring loop to ensure state is saved/committed on interrupt

**Recommendation:** Add `try/finally` around the main monitoring loop to ensure state is properly committed on graceful shutdown. Effort: small - wrap loop in error handling.

---

## Cross-Phase Conflict Analysis

### DF-003 ↔ INT-001 (Phase 05)

Both findings identify the same root cause: the audit phase templates (phases 05 and 06) reference non-existent Google Sheets integration (`GSheetsReader`, `GoogleSheetsConfig`). These are cross-phase duplicates. The templates were apparently copied from a different project and need to be adapted.

### DF-004 ↔ INT-004 (Phase 05)

Both findings identify that `TelethonConfig.max_retries` is defined but never used in `forward_to_users`. INT-004 classifies this as `SPEC-DEVIATION` while DF-004 classifies it as `BEST-PRACTICE`. The DF-004 classification is more appropriate — the field's presence doesn't violate any spec (the model just declares intent), but it's a code quality inconsistency.

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 4 | DF-001, DF-004, DF-005, DF-006 |
| Reclassified | 1 | DF-003 (SPEC-DEVIATION → DOC-UPDATE) |
| Merged | 1 | DF-002 → DF-001 |
| Rejected | 0 | — |

### Cross-Phase Duplicates
| Finding | Cross-Phase Duplicate | Phase |
|---------|----------------------|-------|
| DF-003 | INT-001 | Phase 05 |
| DF-004 | INT-004 | Phase 05 |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| DF-003 | SPEC-DEVIATION | DOC-UPDATE | The codebase is correct — no Google Sheets integration exists because the project architecture doesn't include it. The audit phase template is what's outdated. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| DF-002 | DF-001 | Same root cause: accessing `settings.monitoring` instead of `settings.channels`. DF-001 provides a more precise fix recommendation. |

### Rollout Analysis

| Finding | Risk | Dependency | Rollout Concern |
|---------|------|------------|-----------------|
| DF-001 (fix in monitor.py) | LOW | None | Isolated to 3 lines in `monitor.py`. Single-attribute rename. Safe. |
| DF-005 (fix in config.yaml) | LOW | None | Template only. No runtime impact until user runs `init`. Safe. |
| DF-003 (fix audit spec) | NONE | Requires fixing audit phase 05 template too | Documentation only. No rollout risk. |
| DF-004 (fix or remove) | LOW | None | Advisory. Removing the field would affect the model only. |
| DF-006 (add cleanup) | LOW | None | Adding `try/finally` around the main loop has no side effects. |

### Required Fixes

1. **DF-001** (CRITICAL): Change `settings.monitoring` → `settings.channels` in `monitor.py` lines 306-310. This is a runtime crash bug.
2. **DF-005** (HIGH): Restructure `config.yaml` so `DEFAULTS` is at the top level of `CHANNELS` (as `defaults`), and move `stagger_start_seconds` to the `CHANNELS` level (not inside `DEFAULTS`).

### Advisory Recommendations

1. **DF-003** (DOC-UPDATE): Update audit phase 06 spec to remove Google Sheets references. Also update phase 05 spec (see INT-001).
2. **DF-004** (BEST-PRACTICE): Either implement retry using `max_retries` in `forward_to_users`, or remove the unused field from `TelethonConfig`.
3. **DF-006** (BEST-PRACTICE): Add `try/finally` around the main monitoring loop in `run_monitor` or `main_loop` to ensure state cleanup on shutdown.

### Warnings

- **Cross-phase duplicate:** DF-003 and INT-001 (Phase 05) both identify the same audit template problem. Fix both specs together to avoid inconsistency.
- **Cross-phase duplicate:** DF-004 and INT-004 (Phase 05) both identify the unused `max_retries` field. Coordinate fix to avoid re-opening.
- **Architectural risk:** The audit phase templates (phases 05 and 06) reference a Google Sheets pipeline that does not exist. This suggests the templates were copied from a legacy project. All audit phases using these templates should be reviewed for the same issue.

---