---
name: 02-config-findings
description: Phase 02 audit findings — Configuration & Settings Models
agent: audit-executor
alwaysApply: false
---

# Phase 02 Audit Findings — Configuration & Settings Models

**Executor:** audit-executor
**Template:** .kilo/commands/audit/phases/02-audit-config.md
**Status:** complete
**Validated:** no

---

## Findings

### CFG-001: `validate` command does not validate configuration schema (only file existence)

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION / RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/cli.py` (`validate()`), `src/mko_telebot/core/config.py` (`TelepostConfigReader.validate_files()`) |
| **Classification** | mandatory |

**Description:** The `validate` CLI command is documented (docs/99-reference/cli-reference.md:102) as "Check that configuration files exist and are valid", but its implementation only calls `validate_files()`, which checks that `config.yaml` and `telethon_config.yaml` *exist* — it never invokes `load()` / `TelepostSettings.model_validate()`. As a result, `validate` reports "Configuration files are valid" even when the YAML is schema-invalid (e.g., placeholder credentials, missing required fields, wrong types). Actual schema validation only runs inside the `run` command via `load()`.

**Evidence:** Runtime check (Phase R1/R2) — with a schema-invalid `telethon_config.yaml` (`api_id: 1`, `api_hash: "short"`, `phone_or_token: "x"`):
```
$ r.validate_files()
validate_files() PASSED despite schema-invalid content
$ r.load()
Configuration validation failed: 2 validation errors for TelepostSettings
  TELETHON_API.phone_or_token: Value error, phone_or_token appears to be a placeholder value
  TELETHON_API.client.api_hash: Value should have at least 32 items ...
```
`cli.py:96-104` — `validate()` only calls `reader.validate_files()` then prints success. The doc at cli-reference.md:115 confirms the intended scope is "checks that both config.yaml and telethon_config.yaml exist", contradicting the command's own description (line 102) and the user-facing success message "Configuration files are valid."

**Recommendation:** Make `validate` call `reader.load()` (and `load_logging_config()` if present) so it performs the same Pydantic validation the `run` command uses, then report the actual validation result. This removes the false-confidence gap where a user believes their config is valid, only to have `run` fail at startup. Effort: small. Priority: recommended.

---

### CFG-002: `init` copies `keyw_config_example_keep.yaml` into the user config dir as an orphan file

| Field | Value |
|-------|-------|
| **ID** | CFG-002 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/cli.py` (`init()`), `src/mko_telebot/settings/keyw_config_example_keep.yaml` |
| **Classification** | advisory |

**Description:** `init()` copies *every* file in `APP_PATHS.app_settings_dir` to the user settings dir (cli.py:62-79). This includes `keyw_config_example_keep.yaml`, which contains a `CHANNELS:` top-level block. However, `TelepostConfigReader.load()` only merges `config.yaml` + `telethon_config.yaml`; it never reads `keyw_config_example_keep.yaml`. The copied file is therefore dead weight in the user's config directory and, because it also carries a `CHANNELS` section, can mislead users into editing the wrong file (their channel edits to `keyw_config_example_keep.yaml` are silently ignored).

**Evidence:** `cli.py:62` — `for item in src.iterdir(): if not item.is_file(): continue` copies all four settings files including `keyw_config_example_keep.yaml`. `config.py:161-180` (`load()`) reads only `self.config_path` and `self.secrets_path`. The file is documented as "Keyword configuration example (kept as reference)" (cli-reference.md:75) but is nonetheless physically copied into the live config dir.

**Recommendation:** Either (a) exclude `keyw_config_example_keep.yaml` from the copy loop (copy only the loadable templates + keep the example only as an in-package reference), or (b) document explicitly that it is a non-loaded reference and must not be edited as config. Option (a) is cleaner and avoids the silent-ignore footgun. Effort: trivial. Priority: recommended.

---

### CFG-003: `log_config.yaml` is JSON-style markup with inline `#` comments, not valid-by-intent YAML

| Field | Value |
|-------|-------|
| **ID** | CFG-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/settings/log_config.yaml`, `src/mko_telebot/core/config.py` (`load_logging_config()`) |
| **Classification** | advisory |

**Description:** `log_config.yaml` is written as a JSON object using `{...}` flow mappings plus inline `#` comments (lines 1-67). PyYAML's `safe_load` happens to tolerate inline comments inside flow collections, so it currently parses, but this is fragile and inconsistent with the rest of the codebase's YAML style and with the documentation, which treats it as a normal YAML file (docs/11-guides/configuration.md:301). A stricter or alternative YAML loader (or a future refactor using a faster C loader, or a YAML style linter) could break it. It also mixes two syntaxes, which is confusing for maintainers.

**Evidence:** `settings/log_config.yaml:1-2` —
```
{
  "LOGGING":{
    # Always 1. Schema versioning may be added in a future release of logging
    "version": 1,
```
Runtime check (Phase R2) confirmed it parses today (`load_logging_config()` returns the expected dict and `logging.config.dictConfig()` applies it), so this is a maintainability/fragility concern rather than a live defect.

**Recommendation:** Rewrite `log_config.yaml` in standard block-style YAML (no `{`/`}` braces, no inline comments inside mappings) to match `config.yaml`/`telethon_config.yaml` and the documented YAML expectation. Keep the optional `LOGGING` wrapper key handling in `load_logging_config()` since tests rely on it. Effort: trivial. Priority: recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 0 |
| LOW | 2 |

## Mandatory Fixes

- **CFG-001** (HIGH): `validate` command must perform real schema validation, not just file-existence checks.

## Advisory Recommendations

- **CFG-002** (LOW): Stop copying `keyw_config_example_keep.yaml` into the live user config dir, or document that it is a non-loaded reference.
- **CFG-003** (LOW): Convert `log_config.yaml` from JSON-flow-with-comments to standard block-style YAML.

## Doc Updates Needed

- **CFG-001**: docs/99-reference/cli-reference.md:102 vs :115 are inconsistent. If `validate` remains existence-only, the command description (line 102) must be corrected to "Check that configuration files exist"; if it is fixed to validate schema (recommended), no doc change is needed beyond the existing accurate wording. Either way the internal inconsistency must be resolved.
- **CFG-002**: docs already describe the file as "kept as reference" but do not state it is copied yet never loaded — clarify or remove the copy.
