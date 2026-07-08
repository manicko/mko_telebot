---
name: 06-data-flow-findings
description: End-to-end data flow audit findings
agent: auditor
status: complete
validated: no
---

# Phase 06 Audit Findings — End-to-End Data Flow

**Executor:** auditor  
**Template:** `.ai/audit/templates/audit-findings.md`  
**Status:** complete  
**Validated:** no

---

## Runtime Verification Results

| Check | Result |
|-------|--------|
| R1 - Import Full Pipeline | All modules importable (package installed in editable mode) |
| R2 - Linter (ruff) | All checks passed |
| R2 - Type Checker (mypy) | Success - no issues found in 10 source files |
| R3 - Test Suite | 103 passed in 2.28s |

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

### DF-002: Config propagation trace reveals structural mismatch between `ChannelsConfig` and expected `monitoring` attribute

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/models.py, src/mko_telebot/monitor.py |
| **Classification** | mandatory |

**Description:** The audit phase specification requires tracing `telethon.*`, `posts.*`, and `chats.*` config sections to their consumers. However, the codebase structure does not match the spec: there is no `posts.*` or `chats.*` config section, and the `telethon.*` config correctly flows through the client but the `monitoring.*` section is misnamed as `channels.*`. The data flow breaks at the model boundary because `monitor.py` expects `settings.monitoring.channels` but the Pydantic model provides `settings.channels.channels`.

**Evidence:**
- `src/mko_telebot/core/models.py`: `TelepostSettings` has `telethon: TelethonConfig` and `channels: ChannelsConfig`
- `src/mko_telebot/core/channels.py`: `ChannelsConfig` contains `channels_delay`, `stagger_start_seconds`, and `channels` dict
- `src/mko_telebot/monitor.py` line 306-310: Incorrectly accesses `settings.monitoring.channels_delay` instead of `settings.channels.channels_delay`
- The audit spec lines 67-73 reference `google_sheets.*`, `telethon.*`, `posts.*`, `chats.*` config sections — but only `telethon.*` and `channels.*` actually exist

**Recommendation:** Either rename `channels` to `monitoring` in `TelepostSettings` and `ChannelsConfig`, or update `monitor.py` to use the correct attribute names. The current mismatch causes runtime crashes. Effort: trivial - rename either the model field or the access pattern.

---

### DF-003: Audit spec references Google Sheets integration and PostProcessor/ImageCache that do not exist

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | Audit phase specification |
| **Classification** | advisory |

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

**Description:** The audit spec requires that cleanup runs on both success and failure paths (lines 111-112). However, while the codebase has state persistence via `Task.save_state()`, there is no image cache cleanup (since `ImageCache` doesn't exist) and no guaranteed state consistency cleanup on failures. The `main_loop` has no cleanup mechanism.

**Evidence:**
- `src/mko_telebot/monitor.py` lines 330-341: `run_monitor` runs the loop but has no cleanup wrapper
- `src/mko_telebot/monitor.py` line 249: `task.last_msg_id` is only updated after successful processing
- No `try/finally` blocks around the main monitoring loop to ensure state is saved/committed on interrupt

**Recommendation:** Add `try/finally` around the main monitoring loop to ensure state is properly committed on graceful shutdown. Effort: small - wrap loop in error handling.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 2 |
| MEDIUM | 2 |
| LOW | 0 |

## Mandatory Fixes

- DF-001: `settings.monitoring` referenced but `TelepostSettings` has no `monitoring` attribute
- DF-002: Config propagation trace reveals structural mismatch between `ChannelsConfig` and expected `monitoring` attribute
- DF-005: Template config.yaml has incorrect DEFAULTS structure preventing valid config load

## Advisory Recommendations

- DF-003: Audit spec references Google Sheets integration that does not exist
- DF-004: `telethon.*` config correctly propagates but `max_retries` is unused in message sending
- DF-006: No centralized state cleanup on failure paths

---