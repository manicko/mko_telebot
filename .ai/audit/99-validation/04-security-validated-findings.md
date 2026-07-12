# Phase 04 Validated Audit Findings — Security & Secret Management

**Executor:** validator
**Source:** .ai/audit/04-security/findings.md
**Status:** complete
**Validated:** yes

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

> **Validation Note:**
> - **Action:** validated
> - **Detail:** No explicit path traversal validation exists for the session field. The mitigation via `.name` extraction in monitor_client.py is implicit and relies on pathlib behavior rather than defensive validation. This represents a valid security gap where input validation could be more explicit.
> - **See also:** INT-003 (proxy credentials - related credential protection concern)

**Description:** The `session` field in `ClientConfig` is validated only for placeholder values, but not for path traversal characters. An attacker could provide a session value like `../../../malicious` which would, while mitigated by `.name` extraction in `monitor_client.py`, represent a security gap where input validation is delegated to path handling rather than being explicit.

**Evidence:**
- `src/mko_telebot/core/telethon.py:55-63` - `validate_not_placeholder` only checks for `YOUR_` and `PLACEHOLDER_` prefixes, no path character checks
- `src/mko_telebot/monitor_client.py:36-41` - session path is handled by extracting `.name`, but no explicit validation exists at the model level
- The `ChannelConfig.validate_channel_name()` validator (channels.py:54-62) demonstrates the pattern used elsewhere in the codebase for path traversal prevention, but is not applied to session names

**Recommendation:** Add explicit path traversal validation for the session field in `ClientConfig.validate_not_placeholder()` or add a dedicated validator to reject `/`, `\`, and `..` characters in session names. This would align with the defensive pattern already used for channel names.

---

### SEC-002: Incomplete .gitignore Coverage for User Config Templates

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | .gitignore |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** validated
> - **Detail:** The `**user*.yamls` pattern (line 187) uses non-standard glob syntax and would not match `telethon_config.yaml` even if it were in the project directory. However, since user config files are stored via `platformdirs` in an external user directory (~/.config/), this represents a documentation/documentation inconsistency issue rather than an actual security vulnerability.
> - **See also:** docs/11-guides/configuration.md explicitly documents that user configs are stored outside project via platformdirs

**Description:** The `.gitignore` uses `**user*.yamls` (line 187) which is an unusual pattern. Standard glob patterns use `**/*.ext` for recursive matching. This pattern would only match files ending in `yamls` (not `.yaml`) at the root or with `user` prefix, missing the standard user config file `telethon_config.yaml`. However, since `telethon_config.yaml` is stored in the user's config directory via `platformdirs`, it is inherently outside the project.

**Evidence:**
- `.gitignore:187` - `**user*.yamls` pattern (typo in extension and malformed glob)
- `.gitignore:190-191` - `*token.json` and `*.session*` patterns cover token/session files correctly
- `docs/11-guides/configuration.md:53-72` - User config directory is platform-specific and outside project root

---

### SEC-003: Proxy Credentials Stored as Plain Strings Without Protection

| Field | Value |
|-------|-------|
| **ID** | SEC-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/telethon.py |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** merged
> - **Detail:** This finding addresses the same root cause as INT-003 (proxy credentials exposed without SecretStr protection). Merging into INT-003 which has broader scope including model_dump exposure.
> - **See also:** INT-003

**Description:** The proxy configuration in `ClientConfig` stores `username` and `password` as plain strings within a `dict[str, object]`, unlike `api_hash` and `phone_or_token` which use `SecretStr`. When `model_dump(mode='json')` is called in `monitor_client.py:32`, these credentials are exposed as plain text in the returned dictionary. If the config dict is ever logged (e.g., during debugging), these credentials would leak.

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

- SEC-001: Add explicit path traversal validation for the session field in `ClientConfig`
- SEC-002: Update `.gitignore` pattern `**user*.yamls` to standard format or clarify user config isolation
- SEC-003: Consider using SecretStr for proxy username/password fields to prevent accidental credential exposure

## Doc Updates Needed

None - no findings classified as DOC-UPDATE were identified.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | SEC-001, SEC-002 |
| Reclassified | 0 | — |
| Merged | 1 | SEC-003 → INT-003 |
| Rejected | 0 | — |

### Cross-Phase Conflicts Detected

| ID | Type | Conflict |
|----|------|----------|
| INT-003 | SPEC-DEVIATION | Same issue as SEC-003: proxy credentials exposed without SecretStr protection. Both findings correctly identify the same problem from different audit phases (integrations vs security). |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-----------|---------|
| SEC-003 | INT-003 (Phase 05) | Both findings address the same root cause: proxy username/password stored as plain strings in dict without SecretStr protection. INT-003 has broader scope including the model_dump exposure vectors. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | — |