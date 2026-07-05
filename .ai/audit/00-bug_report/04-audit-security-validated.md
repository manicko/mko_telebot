---
name: 04-security
description: Security & Secret Management audit findings (validated)
executor: auditor
validated_by: validator
validated_date: 2026-06-30
---

# Phase 04 Audit Findings — Security & Secret Management (Validated)

**Executor:** auditor  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** complete  
**Validated:** yes  
**Validated by:** validator

---

## Findings

### SEC-01: Path Validation Checks Existence Before Security Containment

| Field | Value |
|-------|-------|
| **ID** | SEC-01 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telepost/core/post_processor.py |
| **Classification** | mandatory |

**Description:** The `_validate_photo_path` method in `PostProcessor` checks file existence (`resolved.exists()`) before checking path containment (`is_relative_to`). This order allows an attacker controlling Google Sheets data to probe for file existence in directories outside the allowed base, receiving different error messages for existing vs non-existing files.

**Evidence:**
```python
# src/mko_telepost/core/post_processor.py:78-86
# Check file existence before security check
if not resolved.exists():
    raise ValueError(f"Photo path does not exist: {photo_path}")

# Use is_relative_to for proper path containment (SEC-03 fix)
if not resolved.is_relative_to(allowed_resolved):
    raise ValueError(
        f"Photo path '{photo_path}' escapes allowed directory '{allowed_base}'"
    )
```

The code first raises "does not exist" for missing files, then "escapes allowed directory" for existing files outside the base. An attacker can distinguish between:
- Files that exist outside the allowed directory (get "escapes" error)
- Files that don't exist anywhere (get "does not exist" error)

**Recommendation:** Swap the order of checks — perform the path containment check BEFORE checking file existence. This ensures a consistent "escapes allowed directory" error for any path outside the allowed base, regardless of whether the file exists.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** The finding is technically correct. The code at lines 78-86 of post_processor.py does check existence before containment. While the impact is limited (Google Sheets data source is typically trusted), the concern is valid for defense-in-depth. Swapping the check order would provide more consistent error behavior for path traversal attempts.
> - **See also:** SPEC.md §4.7 (Security Measures)

---

### SEC-02: Model Dump Exposes Secret Values in Memory

| Field | Value |
|-------|-------|
| **ID** | SEC-02 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telepost/core/telegram_poster.py |
| **Classification** | advisory |

**Description:** The `TelegramPoster.__init__` method calls `settings.client.model_dump()` which by default exposes the raw value of `SecretStr` fields in the resulting dictionary. While this is necessary for Telethon integration, the exposed secret values remain in `self.client_config` (a module-level dictionary) for the lifetime of the `TelegramPoster` instance.

**Evidence:**
```python
# src/mko_telepost/core/telegram_poster.py:33-36
self.client_config = settings.client.model_dump()
if "api_hash" in self.client_config:
    self.client_config["api_hash"] = settings.client.api_hash.get_secret_value()
```

The `model_dump()` call returns a dict with `"api_hash": SecretStr("...")` but then `get_secret_value()` is called to extract the plaintext. This exposes the api_hash in `self.client_config` until the object is garbage collected.

**Recommendation:** While this is necessary for Telethon compatibility, document this as an intentional design trade-off. Consider adding a `clear_secrets()` method or context manager pattern to zero out credentials after client creation if security isolation is critical.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** The finding is technically correct. `model_dump()` preserves `SecretStr` objects, and `get_secret_value()` extracts plaintext. However, this exposure is necessary for Telethon integration - the `TelegramClient` constructor requires plaintext values for `api_hash`. The secret is stored in `self.client_config` for the lifetime of the `TelegramPoster` instance, which is required for `create_client()` to work. This is an accepted trade-off documented in SPEC.md §4.7 and §4.12.
> - **See also:** SPEC.md §4.7 (Security Measures), SPEC.md §4.12

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 1 |

## Mandatory Fixes

- SEC-01: Path validation order should be reversed to prevent file existence probing

## Advisory Recommendations

- SEC-02: Current implementation is acceptable; the secret exposure is necessary for Telethon library compatibility and is an intentional design trade-off

---

## Verification Summary

- **R1 — Credential Leak Search:** No hardcoded real credentials found. Test fixtures use obviously fake values (e.g., `"a" * 32` for api_hash, `12345` for api_id).
- **R2 — Logger Audit:** No secret values logged. All logger calls checked; only paths are logged, not credential contents.
- **R3 — File Permission Check:** `.gitignore` properly excludes `*.session`, `*.session-journal`, `token.json`, `credentials.json`.
- **R4 — Import Verification:** All modules import without side effects.
- **R5 — Linter and Type Checker:** ruff check passed, mypy passed.
- **R6 — Test Suite:** 224 tests passed.

### Positive Controls Verified

| Control | Status |
|---------|--------|
| SecretStr for api_hash | Implemented |
| SecretStr for phone_or_token | Implemented |
| Placeholder rejection (YOUR_*) | Implemented |
| Path traversal protection | Implemented (with order issue noted in SEC-01) |
| .session files in .gitignore | Implemented |
| token.json in .gitignore | Implemented |
| credentials.json in .gitignore | Implemented |
| Restrictive file permissions | Implemented via file_permissions.py |
| Error message sanitization | Implemented in config_reader.py |
| Session path in USER_DIR | Implemented |
| Token path in USER_DIR | Implemented |

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | SEC-01, SEC-02 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| — | — | — |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | — |

---

## Validation Notes

Both findings were validated as technically correct:

1. **SEC-01** confirms a real ordering issue in path validation. The security check (`is_relative_to`) should precede the existence check to prevent information disclosure about files outside the allowed directory. This is a MEDIUM severity issue because:
   - The Google Sheets data source is typically trusted (user-controlled)
   - The attack requires an attacker to control Google Sheets content
   - However, defense-in-depth principles suggest fixing this for robustness

2. **SEC-02** correctly identifies that `SecretStr` values are briefly exposed in `TelegramPoster.client_config`. However, this is necessary for Telethon library compatibility (which requires plaintext `api_hash`), and the exposure duration is limited to the lifetime of the `TelegramPoster` instance. This aligns with the documented design trade-offs in SPEC.md §4.7 and is acceptable as an advisory concern.