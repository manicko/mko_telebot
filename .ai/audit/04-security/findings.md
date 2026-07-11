---
name: 04-security
description: Security audit findings for secret management, credential handling, logging security, and input validation
executor: auditor
status: complete
validated: no
template: .ai/audit/templates/audit-findings.md
---

# Phase 04 Audit Findings — Security & Secret Management

**Executor:** auditor  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** complete  
**Validated:** no

---

## Findings

### SEC-001: Session path lacks validation for path traversal characters

| Field | Value |
|-------|-------|
| **ID** | SEC-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/telethon.py`, `src/mko_telebot/monitor.py` |
| **Classification** | mandatory |

**Description:** The `session` field in `ClientConfig` (telethon.py:28) lacks validation for path traversal characters (`..`, `/`, `\`). While `create_client()` in monitor.py uses `session_path.name` to extract only the filename (line 42), the `Path(session)` call on line 38 could still process malicious paths before the name extraction. An attacker who can modify the config could potentially cause unexpected behavior.

**Evidence:**
- `telethon.py:28` - `session: str = Field(default="first_session", ...)` - no path traversal validation
- `telethon.py:48-56` - `validate_not_placeholder` validator only checks for `YOUR_` prefix, not path characters
- `monitor.py:38` - `session_path = Path(session)` - processes session string without sanitization

**Recommendation:** Add path traversal validation to the `session` field validator, rejecting any session value containing `..`, `/`, or `\` characters. This provides defense-in-depth even though the current code extracts `.name` for the final path.

---

### SEC-002: Template api_id value 1 bypasses placeholder validation

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/settings/secrets.yaml`, `src/mko_telebot/core/telethon.py` |
| **Classification** | advisory |

**Description:** The template `secrets.yaml` contains `api_id: 1` (line 6), which is not a valid Telegram API ID but passes the Pydantic validation in `telethon.py:60-67`. The validator only rejects `api_id == 12345`, but `api_id: 1` is semantically invalid (Telegram API IDs are large integers) and could lead to confusing error messages or failed API authentication.

**Evidence:**
- `secrets.yaml:6` - `"api_id": 1,` - clearly invalid api_id value
- `telethon.py:24` - `api_id: int = Field(..., gt=0, ...)` - only requires positive integer, no minimum value check

**Recommendation:** Add a minimum value constraint to `api_id` (e.g., `gt=10000`) to reject placeholder values, or update the template to use `0` or remove the api_id field entirely so Pydantic's required field validation catches it.

---

### SEC-003: State file path derived from user-supplied channel name without explicit sanitization

| Field | Value |
|-------|-------|
| **ID** | SEC-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/task.py` |
| **Classification** | advisory |

**Description:** The `resolve_state_file()` function (task.py:90-104) constructs a state file path using `channel_name` directly: `self.state_file = state_dir / f"{self.channel_name}.json"`. While the channel name validator in `channels.py:54-62` rejects path traversal characters (`/` and `\` and `..`), the validation happens in a separate module. If the channel name is set programmatically without validation, the state file path could be manipulated.

**Evidence:**
- `task.py:92` - `self.state_file = state_dir / f"{self.channel_name}.json"` - direct string interpolation
- `channels.py:54-62` - validator rejects `/`, `\`, and `..` but this is not enforced at the usage site

**Recommendation:** Add explicit path sanitization in `resolve_state_file()` to strip or reject dangerous characters, providing defense-in-depth against future changes to the validation chain.

---

### SEC-004: Secrets template exposes internal configuration structure

| Field | Value |
|-------|-------|
| **ID** | SEC-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/settings/secrets.yaml` |
| **Classification** | advisory |

**Description:** The template `secrets.yaml` includes non-essential fields (`system_lang_code: "en-US"`, `lang_code: "ru"` on lines 8-9) that document internal configuration options. While not a direct security vulnerability, exposing these in the template could lead users to include unnecessary data in their secrets file, increasing the risk of accidental exposure of intent through version control if the file is mistakenly committed.

**Evidence:**
- `secrets.yaml:8-9` - `"system_lang_code": "en-US"` and `"lang_code": "ru"` are included in the template but are optional

**Recommendation:** Move optional fields to the main `config.yaml` or remove them from the template to keep `secrets.yaml` focused only on required credentials (api_id, api_hash, phone_or_token).

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 2 |
| LOW | 1 |

---

## Mandatory Fixes

- SEC-001: Session path lacks validation for path traversal characters

---

## Advisory Recommendations

- SEC-002: Template api_id value 1 bypasses placeholder validation
- SEC-003: State file path derived from user-supplied channel name without explicit sanitization
- SEC-004: Secrets template exposes internal configuration structure

---