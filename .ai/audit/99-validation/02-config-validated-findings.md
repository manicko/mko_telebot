# Phase 02 Audit Findings — Configuration (Validated)

**Source:** `.ai/audit/02-config/findings.md`
**Validator:** validator
**Date:** 2026-07-15

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 0 |
| LOW | 2 |

---

## Findings Validation

### CFG-001: ~~Per-channel defaults overwrite explicit values~~ [VALIDATED]

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Status** | Validated unchanged |

> **Validation Note:**
> - **Action:** Validated as HIGH severity SPEC-DEVIATION
> - **Evidence verified:** Lines 113-136 in `src/mko_telebot/core/channels.py`
> - **The shipped template** `src/mko_telebot/settings/config.yaml` defines `forward_to: []` and `keywords: []` in defaults
> - **Code behavior confirmed:** The `apply_defaults_to_channels` validator at lines 124-128 unconditionally applies default values for any field with `default_factory`, including list fields. When both defaults and channel values are present, `merged_data.update(update_data)` overwrites explicit values with defaults.
> - **Test gap confirmed:** No test exists for list field override behavior. The existing `test_explicit_overrides_preserved` (test_config_reader.py:547-558) only tests scalar fields (scan_interval, history_limit).

**Description:** Per-channel `keywords`/`forward_to` are unconditionally overwritten by `defaults` in `ChannelsConfig.apply_defaults_to_channels`. With the shipped template's empty-list defaults, every channel silently loses its forwarding targets, disabling the core feature.

**Recommendation:** Fix the list-field merge logic to preserve explicit non-empty per-channel values. Empty lists in YAML are valid user intent - distinguish "not specified" from "explicitly empty". Add test coverage for list overrides.

---

### CFG-002: ~~`init` copies example file~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | CFG-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Status** | Rejected |

> **Rejection reason:** The `keyw_config_example_keep.yaml` file serves as an example/documentation file. Per the project rule on "dead code", this file is referenced in its own header comment (lines 1-3) directing users to copy and customize it. The README and docs/11-guides/configuration.md describe `config.yaml` as the configuration file, not `keyw_config_example_keep.yaml`. Investigation of `src/mko_telebot/settings/` shows the template directory contains only flat YAML files (`config.yaml`, `telethon_config.yaml`, `log_config.yaml`, `keyw_config_example_keep.yaml`). No spec requires this file to be excluded. Copying this example file to the config directory is intentional - it provides users with a documented reference. Low operational impact, no functional defect. Same reasoning as CLI-007 rejection (flat template structure).

---

### CFG-003: ~~Logger names mismatch documentation~~ [RECLASSIFIED]

| Field | Value |
|-------|-------|
| **ID** | CFG-003 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Original Type** | BEST-PRACTICE |
| **Status** | Reclassified |

> **Validation Note:**
> - **Action:** Reclassified from BEST-PRACTICE to DOC-UPDATE
> - **Root logger fallback:** The `root` logger in `log_config.yaml` (line 62-65) has `handlers: ["console", "rotating_file"]`, which catches all unconfigured loggers including `mko_telebot.*`. Logging works correctly via this fallback.
> - **Documentation mismatch:** Lines 349-356 and 549-564 in `docs/11-guides/configuration.md` document `__main__` and `telebot` loggers as "Default Loggers", but these don't match the `mko_telebot.*` hierarchy from `__name__` usage.
> - **Code is correct:** All modules use `logger = logging.getLogger(__name__)` (verified in 9 files). The logging system works via `root` propagation, not the specific logger blocks.

**Recommendation:** Update documentation to reflect actual logger hierarchy (`mko_telebot.*`) or note that logging relies on the `root` configuration. The `__main__` entry is still useful for direct script execution, but `telebot` should be documented as unused or renamed to `mko_telebot`.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | CFG-001 |
| Reclassified | 1 | CFG-003 (BEST-PRACTICE → DOC-UPDATE) |
| Rejected | 1 | CFG-002 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| CFG-002 | init copies keyw_config_example_keep.yaml | Example file serves documented purpose; low operational impact; no functional defect |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| CFG-003 | BEST-PRACTICE | DOC-UPDATE | Code works correctly via root logger; documentation describes incorrect logger names |

---

## Cross-Phase Analysis

No conflicts detected with Phase 01 CLI findings. The CFG-001 bug would manifest at runtime (forwarding silently fails) but is correctly isolated to the configuration merge logic.

---

## Rollout Analysis

### Dependencies

- CFG-001 fix requires changes only to `src/mko_telebot/core/channels.py`
- No cross-cutting concerns; the validator runs after Pydantic validation in `load()`

### Sequencing

CFG-001 should be fixed before any production deployment:
- Users editing `config.yaml` to add channels with explicit `forward_to`/`keywords` will see silent failures
- The shipped template `config.yaml` has empty `forward_to: []` and `keywords: []` defaults, triggering this bug immediately

### Architectural Impact

- Current: Breaks core feature (message forwarding)
- Fix approach: Distinguish "field not specified" from "explicitly set to empty list"
- Recommended: Check if channel's list field differs from model's `FieldInfo.default` rather than just checking `default_factory`