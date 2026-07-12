# Phase 04 Audit Findings — Security & Secret Management

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Findings

### SEC-001: Session Name Lacks Path Traversal Validation

| Field | Value |
|-------|-------|
| **ID** | SEC-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/telethon.py, src/mko_telebot/monitor_client.py |
| **Classification** | advisory |

**Description:** The `session` field in `ClientConfig` is validated only for placeholder values (`YOUR_`, `PLACEHOLDER_`), but not for path traversal characters. An attacker could provide a session value like `../../../malicious` which would, while mitigated by `.name` extraction in `monitor_client.py`, represent a security gap where input validation is delegated to path handling rather than being explicit.

**Evidence:**
- `src/mko_telebot/core/telethon.py:29` - session field with placeholder-only validation
- `src/mko_telebot/core/telethon.py:55-63` - `validate_not_placeholder` only checks for `YOUR_` and `PLACEHOLDER_` prefixes
- `src/mko_telebot/monitor_client.py:36-41` - session path is handled by extracting `.name`, but no explicit validation exists

**Recommendation:** Add explicit path traversal validation for the session field in `ClientConfig.validate_not_placeholder()` or add a dedicated validator to reject `/`, `\`, and `..` characters in session names.

---

### SEC-002: Incomplete .gitignore Coverage for User Config Templates

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | .gitignore |
| **Classification** | advisory |

**Description:** The `.gitignore` uses `**user*.yamls` (line 187) which is an unusual pattern. Standard glob patterns use `**/*.ext` for recursive matching. This pattern would only match files ending in `yamls` (not `.yaml`) at the root or with `user` prefix, missing the standard user config file `telethon_config.yaml`. However, since `telethon_config.yaml` is stored in the user's config directory via `platformdirs`, it's inherently outside the project, making this a minor concern.

**Evidence:**
- `.gitignore:187` - `**user*.yamls` pattern (non-standard glob)
- `.gitignore:190` - `*token.json` covers token files
- `.gitignore:191` - `*.session*` covers session files

---

### SEC-003: Proxy Credentials Stored as Plain Strings Without Protection

| Field | Value |
|-------|-------|
| **ID** | SEC-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/telethon.py |
| **Classification** | advisory |

**Description:** The proxy configuration in `ClientConfig` stores `username` and `password` as plain strings within a `dict[str, object]` rather than using `SecretStr` like `api_hash` and `phone_or_token`. When `model_dump(mode='json')` is called in `monitor_client.py:32`, these credentials are exposed as plain text in the returned dictionary. If the config dict is ever logged (e.g., during debugging), these credentials would be leaked.

**Evidence:**
- `src/mko_telebot/core/telethon.py:37-42` - proxy field uses `dict[str, object]` without SecretStr for credentials
- `src/mko_telebot/core/telethon.py:41` - username/password documented as plain strings
- `src/mko_telebot/monitor_client.py:32` - `model_dump(mode='json')` exposes proxy credentials as plain text

**Recommendation:** Consider using a separate Pydantic model for proxy configuration with `SecretStr` fields for `username` and `password`, or add validation to reject placeholder values and document that proxy credentials should be avoided in favor of IP-based auth.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 2 |

## Mandatory Fixes

None - no security vulnerabilities classified as mandatory were identified.

## Advisory Recommendations

- **SEC-001**: Add explicit path traversal validation for the session field in `ClientConfig`.
- **SEC-002**: Update `.gitignore` pattern `**user*.yamls` to standard format or clarify user config isolation.
- **SEC-003**: Consider using SecretStr for proxy username/password fields to prevent accidental credential exposure.

## Doc Updates Needed

None - no findings classified as DOC-UPDATE were identified.

---