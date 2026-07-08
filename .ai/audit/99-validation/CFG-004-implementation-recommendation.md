---
name: CFG-004-implementation-recommendation
description: Implementation recommendation for CFG-004 secrets.yaml placeholder values
agent: researcher
status: complete
related: CFG-004
---

# CFG-004 Implementation Recommendation — Valid Sentinel Values

**Research Date:** 2026-07-08  
**Related Finding:** .ai/audit/99-validation/02-config-validated-findings.md → CFG-004

---

## Problem Summary

The template `secrets.yaml` contains values that fail Pydantic validation:
- `api_id: 0` — fails `gt=0` constraint
- `phone_or_token: ""` — fails `min_length=5` constraint
- `api_hash: ""` — fails `min_length=1` constraint

Additionally, the original recommendation to use `"YOUR_*"` sentinel values would fail the custom placeholder-detection validators in `telethon.py` (lines 42-46, 94-100).

---

## Current Validator Constraints

From `src/mko_telebot/core/telethon.py`:

| Field | Basic Constraints | Custom Validator Logic |
|-------|-------------------|---------------------|
| `api_id` | `int`, `gt=0` | Rejects value `12345` specifically |
| `api_hash` | `SecretStr`, `min_length=1`, `max_length=64` | Rejects values starting with `YOUR_` |
| `phone_or_token` | `SecretStr`, `min_length=5` | Rejects values starting with `YOUR_` |
| `session`, `app_version`, `device_model`, `system_version` | Optional `str` fields | Rejects values starting with `YOUR_` |

---

## Flow Analysis

The `init` command (`cli.py:34-70`) copies template files to user directory **without validation**. The `validate` command (`cli.py:73-82`) explicitly validates, raising `ConfigError` on failure. Users are expected to edit templates before running the application.

This means the templates must:
1. Contain valid sentinel values that pass all validators (so users can validate after editing)
2. Be clearly identifiable as placeholders to prevent accidental use

---

## Evaluation of Options

### Option A: Different Sentinel Prefix (e.g., `PLACEHOLDER_*`)

**Implementation:** Change sentinel values to use a prefix that does NOT trigger the `YOUR_` check.

| Field | Current Template | Proposed Sentinel | Passes Validation? |
|-------|------------------|-------------------|-------------------|
| `api_id` | `0` | `1` | ✅ (gt=0, not 12345) |
| `api_hash` | `""` | `"PLACEHOLDER_REPLACE_ME"` | ✅ (17 chars, not YOUR_*) |
| `phone_or_token` | `""` | `"PLACEHOLDER_REPLACE_ME"` | ✅ (17 chars >= 5, not YOUR_*) |
| `session` | `""` | `""` (omit, use default) | ✅ |

**Pros:**
- No code changes required
- Existing validators catch real placeholder values (`YOUR_*`, `12345`)
- Simple, minimal change

**Cons:**
- Users could theoretically run with `PLACEHOLDER_*` values (unlikely with clear naming)

### Option B: `mode="before"` Validator Skipping Sentinels

**Implementation:** Modify validators to skip validation when sentinel pattern detected.

**Pros:**
- Could use `None` or empty as sentinel

**Cons:**
- Requires code changes across multiple validators
- Adds complexity to validation logic
- Violates "Production code is king" principle (adds code for template-only concern)

### Option C: Separate Template Validation Mode

**Implementation:** Add `is_template=True` config option to bypass validation.

**Pros:**
- Clean separation of concerns

**Cons:**
- Significant architecture change
- Users must remember to enable validation after editing
- Over-engineering for a simple template file

---

## Recommendation: Option A — Use `PLACEHOLDER_*` Prefix

**Selected for:** Simplicity, zero code changes, follows existing patterns.

### Implementation

### Note on `session` field

The `session` field has a default value `"first_session"` in `ClientConfig`, so it can be omitted entirely from the template. The empty string `""` in the current template is technically valid (no min_length constraint, and `""` does not start with `YOUR_`), but providing a sentinel guides users toward a meaningful value.

### Refined Recommended Template

Update `src/mko_telebot/settings/secrets.yaml`:

```json
{
  "TELETHON_API": {
    "is_user": true,
    "phone_or_token": "PLACEHOLDER_REPLACE_ME",
    "client": {
      "api_id": 1,
      "api_hash": "PLACEHOLDER_REPLACE_ME"
    }
  }
}
```

Fields `session`, `device_model`, `system_version` should be omitted to use their defaults, since the template's empty string values provide no user guidance.

---

## Actions Required

1. Update `src/mko_telebot/settings/secrets.yaml` with valid sentinel values
2. (Optional) Add inline comments in the YAML to guide users on required replacements
3. Update documentation in `docs/11-guides/configuration.md` to reflect the new sentinel pattern (if needed)