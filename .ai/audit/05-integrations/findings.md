---
name: 05-integrations-audit-findings
description: Audit findings for external integrations phase
agent: auditor
status: complete
validated: no
---

# Phase 05 Audit Findings — External Integrations

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### INT-001: Google Sheets Integration Not Implemented Despite Spec Requirements

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | .kilo/commands/audit/phases/05-audit-integrations.md |
| **Classification** | mandatory |

**Description:** The audit spec (line 57) specifies "Google Sheets API integration (GSheetsReader)" and requires auditing OAuth2 flow, credentials handling, and API error catching. However, GSheetsReader, GoogleSheetsConfig, and all related Google Sheets integration code are completely absent from the codebase. The spec also references `GoogleSheetsConfig` model fields (spreadsheet_id, credentials_file, token_file, scopes) that should be passed to GSheetsReader, but this model does not exist. This represents a fundamental spec/code mismatch where the spec describes features that were never implemented.

**Evidence:**
- Audit spec line 57: Lists "Google Sheets API integration (GSheetsReader)" in scope
- Audit spec line 67-74: Requires checking OAuth2 flow, credential paths, and error handling for GSheetsReader
- Audit spec line 104: References `GoogleSheetsConfig` model fields that should reach GSheetsReader
- Codebase grep returns no matches for `GSheetsReader`, `GoogleSheetsConfig`, `google_sheets`, or `spreadsheet_id`
- No Google-related dependencies in pyproject.toml (no google-api-python-client, google-auth, etc.)

**Recommendation:** Either implement the Google Sheets integration as documented in the spec, or update the audit spec to reflect the actual architecture which only includes Telegram integration. The codebase overview (docs/00-overview/overview.md) does not mention any Google Sheets features, confirming this was never an implemented feature.

**Effort:** large (would require full implementation) or small (spec update)
**Priority:** mandatory

---

### INT-002: Missing OSError and WorkerBusyTooLongRetryError Handling in Telegram Integration

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/monitor_forward.py |
| **Classification** | advisory |

**Description:** The audit spec requires that OSError and WorkerBusyTooLongRetryError trigger retries with exponential backoff (line 84). The current implementation in `monitor_forward.py` only handles FloodWaitError and RPCError. OSError is caught in `core/config.py` and `core/utils.py` but not in the Telegram message sending/receiving logic where network-level errors would most likely occur.

**Evidence:**
- Audit spec line 84: "OSError triggers retries with exponential backoff"
- `monitor_forward.py` lines 84-102: Only FloodWaitError and RPCError are caught in `forward_to_users()`
- `monitor_forward.py` lines 195-203: Only FloodWaitError and TelegramServiceError in `process_task()`
- No import or handling of `WorkerBusyTooLongRetryError` anywhere in codebase
- No catch for `OSError` in the message sending or fetching functions

**Recommendation:** Add exception handling for OSError and WorkerBusyTooLongRetryError in `monitor_forward.py`'s `forward_to_users()` and `process_task()` functions, following the existing retry pattern with exponential backoff and jitter.

**Effort:** small
**Priority:** recommended

---

### INT-003: Proxy Credentials Exposed Without SecretStr Protection

| Field | Value |
|-------|-------|
| **ID** | INT-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/telethon.py, src/mko_telebot/monitor_client.py |
| **Classification** | advisory |

**Description:** The proxy configuration in `ClientConfig` accepts username and password as plain strings within a `dict[str, object]`, unlike `api_hash` and `phone_or_token` which use `SecretStr`. Per the spec's credential handling requirements (lines 94-96), sensitive values should be protected. When `model_dump(mode='json')` is called, these credentials are exposed as plain text in the returned dictionary, creating potential for credential leakage if the config is ever logged.

**Evidence:**
- `src/mko_telebot/core/telethon.py` lines 37-42: proxy field defined as `dict[str, object] | None` with no SecretStr
- `src/mko_telebot/monitor_client.py` line 32: `client_config = settings.telethon.client.model_dump(mode='json')` passes proxy credentials unprotected
- `src/mko_telebot/core/telethon.py` lines 40-41: Documentation shows `username` and `password` as optional plain strings
- Audit spec line 94: "No hardcoded credentials — API IDs, hashes, tokens, and spreadsheet IDs come from config, not hardcoded values" (implies protection needed)

**Recommendation:** Create a dedicated Pydantic model `ProxyConfig` with `SecretStr` fields for username and password, and add validation to at least reject placeholder values for these sensitive fields.

**Effort:** small
**Priority:** recommended

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 2 |
| LOW | 0 |

## Mandatory Fixes

- INT-001: Google Sheets Integration Not Implemented Despite Spec Requirements — The spec requires GSheetsReader integration that does not exist in the codebase.

## Advisory Recommendations

- INT-002: Missing OSError and WorkerBusyTooLongRetryError Handling in Telegram Integration
- INT-003: Proxy Credentials Exposed Without SecretStr Protection

## Doc Updates Needed

None

---