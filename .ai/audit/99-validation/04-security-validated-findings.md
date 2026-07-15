# Phase 04 Validation Report — Security

**Source:** `.ai/audit/04-security/findings.md`
**Validator:** validator agent
**Date:** 2026-07-15

---

## Validated Findings

### SEC-001: `init --force` overwrites user's Telegram credentials

| Field | Value |
|-------|-------|
| **ID** | SEC-001 |
| **Original Type** | SPEC-DEVIATION |
| **Validated Type** | SPEC-DEVIATION |
| **Severity** | MEDIUM |

> **Validation Note:**
> - **Action:** Validated
> - **Evidence:** `cli.py:57-65` iterates all files in `app_settings_dir/settings` and copies them to `user_settings_dir/settings` without discrimination. `telethon_config.yaml` is included in `settings/` (confirmed: it exists at `src/mko_telebot/settings/telethon_config.yaml:44` lines). Documentation in `cli-reference.md:67-74` lists `telethon_config.yaml` as a template file copied but does not warn about credential loss risk. The issue is real: users with real credentials lose them on `init --force`.
> - **See also:** CLI-007 (similar concern about template overwriting)

**Status:** APPROVED as SPEC-DEVIATION — the code behavior (overwriting credentials file) should change OR documentation should explicitly warn about irreversible credential loss.

---

### SEC-002: Stray `test.session` in repo root

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Original Type** | BEST-PRACTICE |
| **Validated Type** | SPEC-DEVIATION |
| **Severity** | LOW |

> **Validation Note:**
> - **Action:** Reclassified
> - **Detail:** The `test.session` file (28,672 bytes) exists at repository root and is ignored by `.gitignore` (`*.session*` on line 184). Sessions are correctly stored in `APP_PATHS.session_dir` (`monitor_client.py:46: session_path = APP_PATHS.session_dir / session_path.name`), so the guard exists. However, this file should be removed from the repository as it represents an accidental commit. Per "Dead code" policy, this is a leftover artifact, not dead code.
> - **See also:** Session handling in `monitor_client.py:40-48`

**Status:** RECLASSIFIED as SPEC-DEVIATION — file cleanup required, but session path guard already exists in code.

---

### SEC-003: No file permission enforcement on credentials

| Field | Value |
|-------|-------|
| **ID** | SEC-003 |
| **Original Type** | BEST-PRACTICE |
| **Validated Type** | BEST-PRACTICE |
| **Severity** | LOW |

> **Validation Note:**
> - **Action:** Validated
> - **Evidence:** No permission enforcement code found in codebase. `cli.py`, `config.py`, `paths.py`, and `telethon.py` contain no `chmod`, `stat`, or mode-related logic. `telethon_config.yaml` contains `SecretStr`-protected fields (`telethon.py:103-104`, `180-181`), but file permissions are OS-default. On POSIX multi-user systems, this exposes credentials to other users.
> - **See also:** `docs/11-guides/configuration.md:230` warns "Treat this file like a password — never commit it to version control" but no permission guidance.

**Status:** APPROVED as BEST-PRACTICE — valid improvement for multi-user POSIX systems.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | SEC-001, SEC-003 |
| Reclassified | 1 | SEC-002 |
| Merged | 0 | — |
| Rejected | 0 | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|----------|
| SEC-002 | BEST-PRACTICE | SPEC-DEVIATION | File exists in repo as accidental artifact; guard code exists but file cleanup is required. |

### Cross-Finding Analysis

- **SEC-001** overlaps with **CLI-007** (both concern template file overwriting), but focus differs: SEC-001 addresses credential loss, CLI-007 addresses silent skipping of subdirectories.
- **SEC-002** is isolated — no cross-phase dependency.
- **SEC-003** is isolated — no cross-phase dependency.

### Rollout Safety Notes

All findings in this phase involve:
- **Non-breaking changes:** SEC-001 and SEC-003 are additive/safety improvements; no API changes.
- **No rollout dependencies:** These fixes can be implemented independently.
- **Low risk:** Changes are defensive; rollback is trivial.

---

## Required Fixes

| Priority | Finding | Action |
|----------|---------|--------|
| MEDIUM | SEC-001 | Either (a) exclude `telethon_config.yaml` from `--force` overwrite in `cli.py:init()`, or (b) add explicit warning in documentation that `--force` overwrites ALL template files including credentials. |
| LOW | SEC-002 | Remove `test.session` from repository root (`rm test.session`). It is already gitignored. |
| LOW | SEC-003 | Add optional permission restriction (0600 for file, 0700 for directory) when creating `user_settings_dir`. |

---

## Advisory Recommendations

No additional recommendations beyond the mandatory fixes.
