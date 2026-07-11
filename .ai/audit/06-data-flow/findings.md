---
name: 06-data-flow-findings
description: End-to-End Data Flow audit findings
agent: auditor
alwaysApply: false
---

# Phase 06 Audit Findings — End-to-End Data Flow

**Executor:** auditor  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** complete  
**Validated:** no

---

## Findings

### DF-001: ChannelDefaults configuration never applied to individual channels

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/channels.py, src/mko_telebot/core/task.py |
| **Classification** | mandatory |

**Description:** The `ChannelDefaults` class in the configuration model defines default values for `forward_to`, `keywords`, `scan_interval`, `history_limit`, and `history_days`. However, these defaults are never merged into individual `ChannelConfig` instances. When channels are created from YAML config with the `defaults` section populated, each channel receives empty lists for `forward_to` and `keywords` instead of inheriting from defaults. This causes data loss - users configuring defaults expect them to propagate to all channels but they do not.

**Evidence:**
- `core/channels.py:65-90` - `ChannelDefaults` defines `forward_to` and `keywords` fields with defaults
- `core/channels.py:117-121` - The `strip_defaults_from_channels` validator only REMOVES a 'DEFAULTS' key and does NOT merge defaults into channels
- `core/task.py:44-59` - `Task.__init__` copies `config.forward_to` and `config.keywords` directly without any fallback to defaults
- Test verification: Channels configured without explicit `forward_to` receive `[]` even when defaults specify `['@some_target']`

**Recommendation:** Implement a model validator or factory method to merge defaults into channel configs. Either modify `ChannelsConfig` to apply defaults during validation, or create a `Task.from_channel_config_with_defaults()` method that merges defaults at Task creation time. Without this, configuration is incomplete and messages may not be forwarded to expected targets. Effort: medium.

---

### DF-002: SecretStr api_hash passed directly to TelegramClient without proper serialization

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py:35-46 |
| **Classification** | mandatory |

**Description:** The `create_client()` function calls `settings.telethon.client.model_dump()` to extract configuration for the Telethon client, but `model_dump()` returns `SecretStr` objects as-is (masked) instead of their string values. The Telethon `TelegramClient` constructor expects `api_hash` as a plain `str`. This causes a type mismatch that would fail at Telethon API initialization time. While the test suite mocks this correctly (using plain string values), the actual runtime code would pass a `SecretStr` object to the Telegram API.

**Evidence:**
- `core/telethon.py:25-27` - `api_hash` defined as `SecretStr` type
- `monitor.py:35` - `client_config = settings.telethon.client.model_dump()` returns `api_hash: SecretStr('**********')`
- `monitor.py:46` - `return TelegramClient(**client_config)` passes the SecretStr object directly
- `monitor.py:37-44` - Session string is manually extracted and converted, but `api_hash` is not
- Test `test_monitor.py:159` mocks `model_dump.return_value` with plain string `"test_hash_value"` instead of SecretStr

**Recommendation:** Convert SecretStr to its string value in `create_client()`. Either call `get_secret_value()` on the api_hash field after model_dump, or use `model_dump(mode='json')` which serializes SecretStr values. Effort: small.

---

### DF-003: No cleanup of Telegram client connection on exit paths

| Field | Value |
|-------|-------|
| **ID** | DF-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/cli.py:96-101, src/mko_telebot/monitor.py:346-356 |
| **Classification** | advisory |

**Description:** The `run()` CLI command and `run_monitor()` function lack proper cleanup on exit. When `run_monitor()` exits due to `KeyboardInterrupt` or error, the Telethon client connection is never explicitly disconnected. The audit checklist requires try/finally or context manager cleanup for all exit paths.

**Evidence:**
- `monitor.py:353-356` - `run_monitor()` calls `start_client()` but never calls `await client.disconnect()`
- `cli.py:96-101` - The outer try/except catches `KeyboardInterrupt` but has no cleanup hook for client disconnection
- The Telethon client remains connected after `main_loop()` exits, leaving orphaned sessions

**Recommendation:** Wrap client lifecycle in try/finally block and call `await client.disconnect()` on exit. Effort: small.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- DF-001: ChannelDefaults configuration never applied to individual channels
- DF-002: SecretStr api_hash passed directly to TelegramClient without proper serialization

## Advisory Recommendations

- DF-003: No cleanup of Telegram client connection on exit paths

---

## Notes

This phase audit focused on the actual project architecture (Telegram channel monitoring) rather than the Google Sheets/PostProcessor/ImageCache references in the phase specification, which were identified as misaligned with this project in Phase 03 and Phase 05 validation. The findings reflect real data flow issues in the Telegram monitoring pipeline.