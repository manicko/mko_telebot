---
name: 01-cli-validated-findings
description: Validated CLI Audit Findings
agent: validator
status: complete
---

# Phase 01 Validated Findings — CLI Entry Point & Command Layer

**Validator:** validator
**Source:** `.ai/audit/01-cli/findings.md`
**Status:** complete

---

## Findings

### CLI-001: Template config.yaml uses invalid YAML/JSON syntax causing parse errors

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/settings/config.yaml |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** Partially validated — core issue confirmed, but description has inaccuracies.
> - **Detail:** See below for corrected evidence and corrections to the original finding.

**Corrected Description:** The template `config.yaml` file uses JSON-flow-style syntax with single-quoted keys inside curly braces `{}`. This is **invalid YAML** — `yaml.safe_load()` throws `ScannerError("mapping values are not allowed here")` on line 2, column 11. The file cannot be parsed at all in its current form. Additionally, even if the YAML syntax were corrected to proper block format, the `DEFAULTS` entry inside `channels` contains `stagger_start_seconds`, which is not a valid field for `ChannelConfig` (which has `extra="forbid"`). Pydantic v2 validates nested model fields before running `@model_validator`, so the `strip_defaults_from_channels` validator that removes the `DEFAULTS` key never gets a chance to run — it fails with `extra_forbidden` on `channels.DEFAULTS.stagger_start_seconds`.

**Corrections to original finding:**
1. ~~"Python's yaml.safe_load() can parse this hybrid format"~~ — **FALSE.** Verified: `yaml.safe_load()` throws `ScannerError` on the current template. The file is unparseable.
2. ~~"channels_delay is incorrectly nested inside channels dict"~~ — **FALSE.** In the template, `channels_delay` is at the same level as `channels`, both inside `CHANNELS`. This correctly maps to `ChannelsConfig.channels_delay` and `ChannelsConfig.channels` respectively. The nesting is correct.

**Evidence (verified):**
- `yaml.safe_load()` on `src/mko_telebot/settings/config.yaml` → `ScannerError: mapping values are not allowed here`
- With corrected YAML block syntax, `ChannelsConfig.model_validate()` fails with: `channels.DEFAULTS.stagger_start_seconds — Extra inputs are not permitted [type=extra_forbidden]` because `ChannelConfig` (with `extra="forbid"`) does not have a `stagger_start_seconds` field
- `ChannelsConfig` has a `@model_validator(mode="after")` that strips `DEFAULTS`, but Pydantic v2 validates nested `ChannelConfig` models during field validation, which occurs before the model validator runs

**Recommendation:** Rewrite template config.yaml using proper YAML block syntax. The `DEFAULTS` entry should only contain fields valid for `ChannelConfig` (remove `stagger_start_seconds`). `stagger_start_seconds` is a field of `ChannelsConfig`, not per-channel config.

---

### CLI-002: ~~Dead code in monitor.py — launcher() function never invoked~~ [RECLASSIFIED]

> **Reclassification reason:** Reclassified from `DOC-UPDATE` to `BEST-PRACTICE`. The `launcher()` function is dead code: it is never imported, never called, and not referenced in `pyproject.toml`, any config template, or documentation. Cross-referencing against SPEC.md (does not exist), Pydantic models, StrEnum values, and config templates yields zero references. This is not a documentation issue — the code should be removed. `BEST-PRACTICE` is the correct type for removing dead code to reduce maintenance surface.

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE *(reclassified from DOC-UPDATE)* |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `launcher()` function in `monitor.py` (lines 343-352) is guarded by `if __name__ == "__main__"` but is never used as an entry point. The `pyproject.toml` (line 156) configures `mko-telebot = "mko_telebot.cli:app"` as the CLI entry point. No code imports or references `launcher()`. The `run_monitor()` function is called directly from `cli.py`.

**Evidence (verified):**
- `pyproject.toml` line 156: `mko-telebot = "mko_telebot.cli:app"`
- grep across all source code (`src/`): only `monitor.py` lines 343 (definition) and 356 (if-main guard) match
- No imports of `launcher` in any file
- `cli.py` `run()` command calls `asyncio.run(run_monitor(settings, client))` directly
- `launcher()` is not referenced in any documentation, config template, or model

**Recommendation:** Remove the `launcher()` function and the `if __name__ == "__main__"` block from `monitor.py`. Effort: trivial.

---

### CLI-003: KeyboardInterrupt handling missing exit code in run command

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/cli.py |
| **Classification** | advisory |

**Validation Status:** VALIDATED — accepted as-is.

**Description:** The `run` command catches `KeyboardInterrupt` (lines 97-100) and prints a status message but does not raise `typer.Exit(code=1)` to indicate abnormal termination. This causes the CLI to return exit code 0 on user interruption.

**Evidence (verified):** `cli.py` lines 97-100:
```python
    try:
        asyncio.run(run_monitor(settings, client))
    except KeyboardInterrupt:
        console.print("[yellow]Monitoring stopped by user.[/yellow]")
```
No `raise typer.Exit(code=1)` follows the console.print.

**Recommendation:** Add explicit exit code after KeyboardInterrupt handling: `raise typer.Exit(code=130)` (standard exit code for SIGINT) or `raise typer.Exit(code=1)`. Effort: trivial.

---

### CLI-004: Unhandled exceptions in run command could leak tracebacks to users

| Field | Value |
|-------|-------|
| **ID** | CLI-004 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/cli.py, src/mko_telebot/monitor.py |
| **Classification** | mandatory |

**Validation Status:** VALIDATED — accepted as-is.

**Description:** The `run()` command only catches `ConfigError` (lines 88-94) but `TelegramServiceError` and `StateError` can be raised during runtime when resolving channel entities (`core/task.py` lines 74, 86, 102) or other Telegram operations. These exceptions would propagate to the CLI layer and display raw tracebacks to users.

**Evidence (verified):**
- `cli.py` line 19: imports only `ConfigError` from `mko_telebot.core.errors`
- `cli.py` lines 88-94: `try/except` catches only `ConfigError`
- `cli.py` lines 97-100: attempts to catch only `KeyboardInterrupt`
- `core/task.py` lines 74-76: `resolve_targets_entities` raises `TelegramServiceError`
- `core/task.py` lines 86-88: `resolve_channel_entity` raises `TelegramServiceError`
- `core/task.py` lines 102-104: `resolve_state_file` raises `StateError`
- `core/errors.py`: `MkoTelebotError` is the base class — `ConfigError`, `TelegramServiceError`, `StateError`, `TelegramAuthError` all inherit from it

**Recommendation:** Either catch `MkoTelebotError` (base class) in the `run()` command to handle all custom exceptions gracefully, or add explicit handling for `TelegramServiceError` and `StateError` with user-friendly error messages. Effort: small.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | CLI-003, CLI-004 |
| Reclassified | 1 | CLI-002 (DOC-UPDATE → BEST-PRACTICE) |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None.

### Merged Findings

None.

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| CLI-002 | DOC-UPDATE | BEST-PRACTICE | The `launcher()` function is genuinely dead code — not referenced in pyproject.toml, imports, config templates, or docs. This is a code quality issue (remove dead code), not a docs-vs-code mismatch. `BEST-PRACTICE` is the correct classification per spec cross-reference rule: SPEC.md does not exist, no models/configs reference launcher. |

### Cross-Phase Conflicts

None detected.

### Rollout Safety Issues

None detected.