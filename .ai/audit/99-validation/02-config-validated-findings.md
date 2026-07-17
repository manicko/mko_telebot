---
name: 02-config-validated-findings
description: Validated audit findings — Configuration & Settings Models
agent: validator
alwaysApply: false
---

# Phase 02 Validated Findings — Configuration & Settings Models

**Validator:** validator
**Source:** `.ai/audit/02-config/findings.md`
**Status:** validated

---

## Findings

### CFG-001: `validate` command does not validate configuration schema (only file existence)

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/cli.py` (`validate()`), `src/mko_telebot/core/config.py` (`TelepostConfigReader.validate_files()`) |
| **Classification** | mandatory |

**Description:** The `validate` CLI command is documented (docs/99-reference/cli-reference.md:102) as "Check that configuration files exist and are valid", but its implementation only calls `validate_files()`, which checks that `config.yaml` and `telethon_config.yaml` *exist* — it never invokes `load()` / `TelepostSettings.model_validate()`. As a result, `validate` reports "Configuration files are valid" even when the YAML is schema-invalid (e.g., placeholder credentials, missing required fields, wrong types). Actual schema validation only runs inside the `run` command via `load()`.

**Evidence Verified:**
- `cli.py:96-104` — `validate()` only calls `reader.validate_files()` then prints success
- `config.py:148-159` — `validate_files()` only checks `self.config_path.exists()` and `self.secrets_path.exists()`
- `config.py:161-180` — `load()` performs Pydantic schema validation via `TelepostSettings.model_validate(merged)`
- Runtime test with schema-invalid `telethon_config.yaml` confirms `validate_files()` passes while `load()` fails with validation errors
- Documentation at `cli-reference.md:102` states "exist and are valid" (implying schema validation) but line 115 contradicts: "checks that both config.yaml and telethon_config.yaml exist"

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Finding is correct. Code discrepancy confirmed: `validate` only checks file existence, not schema validity. Doc line 102 correctly describes expected behavior; line 115 incorrectly narrows it to existence-only. Both code and doc inconsistency are issues.
> - **See also:** CFG-001 doc inconsistency with cli-reference.md:115

**Recommendation:** Make `validate` call `reader.load()` so it performs the same Pydantic validation the `run` command uses, then report the actual validation result. This removes the false-confidence gap where a user believes their config is valid, only to have `run` fail at startup. Effort: small. Priority: recommended.

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

**Evidence Verified:**
- `cli.py:62-79` — The loop iterates all files in `src/mko_telebot/settings/` and copies them, with special handling only for `telethon_config.yaml` (preserved on re-run)
- `config.py:161-180` (`load()`) reads only `self.config_path` and `self.secrets_path` — no reference to `keyw_config_example_keep.yaml`
- `keyw_config_example_keep.yaml` contains a `CHANNELS:` block at line 5, which is identical to the structure in `config.yaml`, creating a misleading duplicate
- Documentation at `cli-reference.md:75` describes the file as "Keyword configuration example (kept as reference)" but does not warn it is not loaded

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Finding is correct. The file is copied but never read by the config loader. Users editing this file will see their changes ignored because `load()` only processes `config.yaml`. The presence of `CHANNELS` block creates a silent footgun.
> - **See also:** Documentation could clarify this is a non-loaded reference file

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

**Evidence Verified:**
- `settings/log_config.yaml:1-2` — Uses `{` opening brace and `"LOGGING":{` JSON-style flow mapping
- `settings/log_config.yaml:3,6-16` — Inline `#` comments inside flow mappings
- `config.py:198` — Uses `yaml.safe_load()` which currently parses this format
- Documentation at `configuration.md:301-330` shows the expected format as standard block YAML under `LOGGING:`
- Documentation at `cli-reference.md:540-587` also shows block-style YAML format

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Finding is correct. The file uses non-standard flow-style JSON syntax while documentation assumes block-style YAML. Although `yaml.safe_load()` currently tolerates this, it is inconsistent with project conventions and could break with stricter YAML parsers.
> - **See also:** Example in cli-reference.md:540-587 shows the correct block-style format

**Recommendation:** Rewrite `log_config.yaml` in standard block-style YAML (no `{`/`}` braces, no inline comments inside mappings) to match `config.yaml`/`telethon_config.yaml` and the documented YAML expectation. Keep the optional `LOGGING` wrapper key handling in `load_logging_config()` since tests rely on it. Effort: trivial. Priority: recommended.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 3 | CFG-001, CFG-002, CFG-003 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None — all findings were validated as correct.

### Merged Findings

None — no findings share the same root cause.

### Reclassified Findings

None — no findings required reclassification.