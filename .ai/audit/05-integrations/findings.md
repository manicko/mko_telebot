---
name: 05-integrations-findings
description: External Integrations audit findings
agent: auditor
alwaysApply: false
---

# Phase 05 Audit Findings — External Integrations

**Executor:** auditor  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** complete  
**Validated:** no

---

## Findings

### INT-001: GSheetsReader Google Sheets integration class does not exist

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/ (missing), .kilo/commands/audit/phases/05-audit-integrations.md |
| **Classification** | mandatory |

**Description:** The audit specification explicitly references a `GSheetsReader` class for Google Sheets OAuth2 integration (lines 26, 63, 67-74). This class is documented to handle token loading, refresh, and re-authentication flows. However, no such class exists in the codebase. Google Sheets integration is completely absent - no OAuth2 flow, no spreadsheets module, no related imports.

**Evidence:**
- `.kilo/commands/audit/phases/05-audit-integrations.md:26` - Mentions "Google Sheets Integration Discovery — Locate the GSheetsReader class"
- `.kilo/commands/audit/phases/05-audit-integrations.md:67-74` - Checklist requires OAuth2 flow completeness for GSheetsReader
- `grep` search for `class GSheetsReader`, `gsheets_reader.py`, `google`, `sheets` in `src/` returns no matches
- `src/mko_telebot/core/` directory contains only: channels.py, config.py, errors.py, models.py, parser.py, paths.py, task.py, telethon.py, utils.py - no Google Sheets reader

**Recommendation:** Either implement the Google Sheets integration (GSheetsReader with OAuth2 flow) or update all phase 05 audit documentation to remove references to non-existent functionality. Effort: large (implementation) or medium (documentation).

---

### INT-002: SecretStr api_hash not converted to string for Telethon API

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor.py:35-46 |
| **Classification** | mandatory |

**Description:** The `api_hash` field in `ClientConfig` is defined as `SecretStr` - a Pydantic type for secure secrets. However, when `create_client()` calls `settings.telethon.client.model_dump()`, it returns the `SecretStr` object itself (masked as `********`), not the actual string value. The Telethon API expects `api_hash` as `str` type (per TelegramClient.__init__ signature), and while tests mock this correctly, real runtime would pass the masked SecretStr object.

**Evidence:**
- `src/mko_telebot/core/telethon.py:25-27` - `api_hash` defined as `SecretStr`
- `src/mko_telebot/monitor.py:35` - `client_config = settings.telethon.client.model_dump()` returns `SecretStr` object
- `src/mko_telebot/monitor.py:46` - `return TelegramClient(**client_config)` passes SecretStr to Telethon
- Test `test_passes_config_through` mocks `model_dump.return_value` with plain string `"test_hash_value"` (line 159) instead of SecretStr
- Runtime test: `model_dump()` returns `{'api_id': 123456, 'api_hash': SecretStr('**********'), ...}` with type `<class 'pydantic.types.SecretStr'>`

**Recommendation:** Convert SecretStr to string when passing to TelegramClient using `.get_secret_value()`. Either add explicit handling in `create_client()` or use `model_dump(mode='json')` which serializes SecretStr to its value. Effort: small.

---

### INT-003: Telegram client lifecycle not properly managed - no disconnect on exit

| Field | Value |
|-------|-------|
| **ID** | INT-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py:346-356, src/mko_telebot/cli.py:86-102 |
| **Classification** | advisory |

**Description:** The `run_monitor()` function starts the Telethon client via `start_client()` but never disconnects it. When the monitoring loop exits (via KeyboardInterrupt or error), the client connection remains open. While Telethon may handle cleanup on process exit, this violates the audit checklist requirement for proper client lifecycle management using `async with client.start()`.

**Evidence:**
- `src/mko_telebot/monitor.py:353-356` - `run_monitor` calls `start_client(client, settings)` but never calls `await client.disconnect()` or uses context manager
- `src/mko_telebot/cli.py:88-101` - `run()` command calls `run_monitor()` within try/except but no cleanup hook
- Audit spec line 86 requires "The Telegram client is properly started and stopped (`async with client.start()`)"

**Recommendation:** Wrap client usage in try/finally block and call `await client.disconnect()` on exit, or use async context manager pattern. Effort: small.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- INT-001: GSheetsReader Google Sheets integration class does not exist
- INT-002: SecretStr api_hash not converted to string for Telethon API

## Advisory Recommendations

- INT-003: Telegram client lifecycle not properly managed - no disconnect on exit

---