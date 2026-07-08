---
name: 04-security-findings
description: Security & Secret Management Audit Findings
agent: auditor
status: complete
validated: no
---

# Phase 04 Audit Findings — Security & Secret Management

**Executor:** auditor
**Template:** `.ai/audit/templates/audit-findings.md`
**Status:** complete
**Validated:** no

---

## Findings

### SEC-001: Template secrets.yaml allows empty credential values that bypass placeholder validation

| Field | Value |
|-------|-------|
| **ID** | SEC-001 |
| **Severity** | CRITICAL |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/settings/secrets.yaml, src/mko_telebot/core/telethon.py |
| **Classification** | mandatory |

**Description:** The template `secrets.yaml` in the package source directory contains empty string values (`phone_or_token: ""`, `api_hash: ""`, `session: ""`) for sensitive credentials. While validators exist to reject `YOUR_` prefix placeholder values and the sentinel value 12345 for api_id, they do NOT reject empty strings. Pydantic's `min_length=1` on `api_hash` would reject empty strings, but the template would still fail with confusing error messages. More importantly, `api_id: 0` bypasses the placeholder check (only checks for 12345) and would pass validation despite being invalid. Additionally, `api_id: 0` with `gt=0` constraint would fail validation, but the error would be cryptic ("Input should be greater than 0").

**Evidence:**
- `src/mko_telebot/settings/secrets.yaml` lines 4-8: Empty strings for `phone_or_token`, `api_hash`, `session`, and `0` for `api_id`
- `src/mko_telebot/core/telethon.py` line 24: `api_id: int = Field(..., gt=0)` - rejects 0 but with unclear error
- `src/mko_telebot/core/telethon.py` lines 42-46, 52-56, 95-100: Placeholder validators check for `YOUR_` prefix but not empty strings

**Recommendation:** Template values should use clearly marked placeholders with the `YOUR_` prefix pattern to ensure validation provides clear guidance. Update `secrets.yaml` template to use `YOUR_bot_token`, `YOUR_api_hash` (32 chars), `YOUR_phone_number`, and add validation to reject empty strings and obviously invalid values like `api_id: 0`. Effort: small.

---

### SEC-002: Channel name used in state file path without sanitization enables path traversal

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | mandatory |

**Description:** The `channel_name` value from configuration is used directly in constructing state file paths without sanitization. A malicious or malformed `channel_name` containing path traversal sequences (e.g., `../`, `/`, `\`) could potentially write or read files outside the intended state directory.

**Evidence:**
- `src/mko_telebot/core/task.py` line 92: `self.state_file = state_dir / f"{self.channel_name}.json"`
- `src/mko_telebot/core/channels.py` line 34: `name: str = Field(..., description="Channel identifier")` - no validation
- The `channel_name` flows from config YAML → `ChannelConfig` → `Task` → `state_file` without sanitization

**Recommendation:** Add a `field_validator` on `ChannelConfig.name` to strip path separators and reject names containing `/`, `\`, or `..` patterns. Alternatively, sanitize the value in `resolve_state_file()` before path construction. Effort: small.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 1 |
| MEDIUM | 0 |
| LOW | 0 |

## Mandatory Fixes

- SEC-001: Template secrets.yaml allows empty credential values that bypass placeholder validation
- SEC-002: Channel name used in state file path without sanitization enables path traversal

---