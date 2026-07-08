---
name: 04-security-validated-findings
description: Security & Secret Management Audit Findings — Validated
agent: validator
status: validated
validated-by: validator
validation-date: 2026-07-08
source: .ai/audit/04-security/findings.md
---

# Phase 04 Audit Findings — Security & Secret Management (Validated)

**Executor:** auditor
**Template:** `.ai/audit/templates/audit-findings.md`
**Status:** validated
**Problems Only:** true — only findings that were reclassified, rejected, merged, or cross-phase issues are listed below.

---

## Findings

### SEC-001: ~~Template secrets.yaml allows empty credential values that bypass placeholder validation~~ [RECLASSIFIED]

> **Validation Note:**
> - **Action:** reclassified
> - **Original Type:** SPEC-DEVIATION
> - **New Type:** BEST-PRACTICE
> - **Detail:** The code does NOT allow empty credentials to bypass validation. All critical credential fields are protected by Pydantic field constraints:
>   - `api_id: int = Field(..., gt=0)` rejects `api_id: 0` with `"Input should be greater than 0"`
>   - `api_hash: SecretStr = Field(..., min_length=1, max_length=64)` rejects `""`
>   - `phone_or_token: SecretStr = Field(..., min_length=5)` rejects `""`
>
>   The finding's claim that `api_id: 0` "would pass validation despite being invalid" is **false** — `gt=0` catches it. Two non-critical optional fields (`session`, `device_model`, `system_version`) do accept empty strings, but these are not security-sensitive credentials.
>
>   The real improvement is template UX: using `YOUR_` prefixed placeholders instead of empty strings would give clearer error messages. This is a **best-practice improvement**, not a spec deviation.

| Field | Value |
|-------|-------|
| **ID** | SEC-001 |
| **Severity** | LOW (downgraded from CRITICAL) |
| **Type** | BEST-PRACTICE (was SPEC-DEVIATION) |
| **Affected Modules** | src/mko_telebot/settings/secrets.yaml, src/mko_telebot/core/telethon.py |
| **Classification** | advisory |

**Description:** The template `secrets.yaml` contains empty string values for credentials. While Pydantic's field constraints (`gt=0`, `min_length=1`, `min_length=5`) reject empty/invalid values for all critical credentials (`api_id`, `api_hash`, `phone_or_token`), the error messages are not as clear as they would be with `YOUR_`-prefixed placeholders. Three non-critical optional fields (`session`, `device_model`, `system_version`) accept empty strings without error — these should either have `min_length` constraints or use `YOUR_` placeholders.

**Evidence (code vs claims):**
- `secrets.yaml` lines 4-8: Empty strings for all fields, `api_id: 0`
- `telethon.py` line 24: `api_id: int = Field(..., gt=0)` — **rejects `0`** (finding claimed it "would pass validation")
- `telethon.py` line 25: `api_hash: SecretStr = Field(..., min_length=1, max_length=64)` — **rejects `""`**
- `telethon.py` line 82: `phone_or_token: SecretStr = Field(..., min_length=5)` — **rejects `""`**
- `telethon.py` line 28: `session: str = Field(default="first_session")` — **accepts `""`** (no min_length)
- `telethon.py` lines 29-35: `app_version`, `device_model`, `system_version`, `system_lang_code`, `lang_code` — **accept `""`** (no min_length)

**Recommendation:** Replace empty values in `secrets.yaml` template with `YOUR_`-prefixed placeholders (e.g., `YOUR_api_hash`, `YOUR_bot_token`) to trigger the existing placeholder validators with clear error messages. Add `min_length=1` to `session`, `app_version`, `device_model`, and `system_version` fields for consistency. Effort: trivial.

---

### SEC-002: Channel name used in state file path without sanitization enables path traversal [VALIDATED]

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Severity** | MEDIUM (retained from HIGH) |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py, src/mko_telebot/core/channels.py |
| **Classification** | mandatory |

**Description:** The `channel_name` value from `ChannelConfig` flows into file path construction without sanitization. A malicious `channel_name` containing path traversal sequences (e.g., `../../`) could write state files outside the intended state directory.

**Evidence:**
- `task.py` line 92: `self.state_file = state_dir / f"{self.channel_name}.json"` — unsanitized interpolation
- `channels.py` line 34: `name: str = Field(..., description="Channel identifier")` — no `field_validator` for path safety
- `task.py` line 46: `self.channel_name = config.name` — direct assignment from config
- Data flow: YAML config → `ChannelConfig.name` → `Task.channel_name` → `state_dir / f"{self.channel_name}.json"`
- `utils.py` line 52: `ensure_path_exists` creates parent dirs from the (possibly traversed) path
- `task.py` lines 149-150: `save_state()` writes to the unsanitized path via `aiofiles.open(str(self.state_file), "w")`

**Severity rationale (downgraded to MEDIUM):**
- The `channel_name` originates from the user's own `config.yaml` — this is NOT a remote attack vector
- In normal flow (`monitor.py` line 315), `resolve_channel_entity()` is called before `resolve_state_file()` — a path-traversal name would fail entity resolution first, preventing state file operations
- The vulnerability is exploitable only when `Task` is used programmatically (outside the normal flow) with a malicious `channel_name`
- This is a defense-in-depth / hardening issue, not a remotely exploitable vulnerability

**Recommendation:** Add a `field_validator` on `ChannelConfig.name` that rejects names containing `/`, `\`, or `..` patterns. Alternatively, sanitize in `Task.resolve_state_file()` by using a hash or stripping path separators from the filename. Effort: small.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | SEC-002 |
| Reclassified | 1 | SEC-001 (SPEC-DEVIATION → BEST-PRACTICE) |
| Merged | 0 | — |
| Rejected | 0 | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| SEC-001 | SPEC-DEVIATION | BEST-PRACTICE | Code validates all critical credentials via Pydantic field constraints (`gt=0`, `min_length`). Empty values do NOT bypass validation — they trigger proper error messages. The finding's claim that `api_id: 0` "would pass validation" is contradicted by `gt=0`. The improvement is template UX (use `YOUR_` placeholders), not a spec deviation. Non-critical optional fields (`session`, `device_model`, `system_version`) accept empty strings — a minor consistency improvement, not a security issue. |

### Required Fixes

- **SEC-002 (mandatory):** Add `field_validator` on `ChannelConfig.name` to reject path separators and `..` sequences before the value reaches file path construction.

### Advisory Recommendations

- **SEC-001 (advisory):** Replace empty values in `secrets.yaml` template with `YOUR_`-prefixed placeholders so the existing placeholder validators provide clear error messages. Optionally add `min_length=1` to non-critical optional fields (`session`, `app_version`, `device_model`, `system_version`) for consistency.

---

## Warnings

### Documentation
- No `docs/SPEC.md` found in the repository. Spec-referencing validation rules from the audit process could not be fully applied for SEC-001. The finding was validated against Pydantic model constraints (the source of truth) instead.

### Rollout Safety
- **SEC-002:** Adding a `field_validator` to `ChannelConfig.name` is backward-compatible. Existing valid configs will pass without changes. The validator should be strict but allow valid Telegram channel identifiers (`@username`, `t.me/...`, alphanumeric). Rollout risk: minimal.