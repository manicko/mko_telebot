---
name: 01-cli-findings
description: CLI Audit Findings
agent: auditor
status: complete
---

# Phase 01 Audit Findings — CLI Entry Point & Command Layer

**Executor:** auditor
**Template:** `.ai/audit/templates/audit-findings.md`
**Status:** complete
**Validated:** no

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

**Description:** The template `config.yaml` file uses JSON-style syntax with single-quoted strings (e.g., `'channels_delay': 30`) inside curly braces `{}`, which is invalid YAML. While Python's `yaml.safe_load()` can parse this hybrid format, it causes parsing difficulties and the structure itself has validation issues: `channels_delay` is incorrectly nested inside `channels` dict, and the `DEFAULTS` entry contains `stagger_start_seconds` which is not a valid field for `ChannelConfig` (it belongs to `ChannelsConfig`).

**Evidence:**
- File `src/mko_telebot/settings/config.yaml` line 1-18 uses JSON-like syntax with single quotes
- When parsed, `CHANNELS.channels_delay` ends up nested under `channels` instead of at the `CHANNELS` level
- The `DEFAULTS` entry includes `stagger_start_seconds` (line 6) which triggers `extra_forbidden` validation error

**Recommendation:** Rewrite template config files using proper YAML syntax. Move `stagger_start_seconds` to the correct location in ChannelsConfig, and either remove DEFAULTS from the template or place it under a `defaults` key. Priority: medium-effort — requires updating template files to be valid YAML and match the Pydantic model structure.

---

### CLI-002: Dead code in monitor.py — launcher() function never invoked

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | MEDIUM |
| **Type** | DOC-UPDATE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `launcher()` function in `monitor.py` (lines 343-352) is guarded by `if __name__ == "__main__"` but is never used as an entry point. The `pyproject.toml` (line 156) configures `mko-telebot = "mko_telebot.cli:app"` as the CLI entry point, making the `launcher()` function dead code.

**Evidence:**
- `pyproject.toml` line 156: `mko-telebot = "mko_telebot.cli:app"`
- No references to `launcher` in codebase except its own definition (grep found only `monitor.py` lines 343, 356)
- `cli.py` `run` command directly calls `asyncio.run(run_monitor(...))`

**Recommendation:** Remove the `launcher()` function and the `if __name__ == "__main__"` block from `monitor.py` to eliminate dead code. Effort: trivial (single function deletion).

---

### CLI-003: KeyboardInterrupt handling missing exit code in run command

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/cli.py |
| **Classification** | advisory |

**Description:** The `run` command catches `KeyboardInterrupt` (lines 97-100) and prints a status message but does not raise `typer.Exit(code=1)` to indicate abnormal termination. This could cause the CLI to return exit code 0 on user interruption.

**Evidence:** `cli.py` lines 97-100:
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

**Description:** The `run()` command only catches `ConfigError` (lines 88-94) but `TelegramServiceError` and `StateError` can be raised during runtime when resolving channel entities (task.py lines 74, 86, 102) or other Telegram operations. These exceptions would propagate to the CLI layer and display raw tracebacks to users, violating the "no raw tracebacks leak to the user" invariant.

**Evidence:**
- `cli.py` line 19 imports only `ConfigError` from errors module
- `cli.py` lines 88-94 show try/except catching only `ConfigError`
- `task.py` lines 74-76 raise `TelegramServiceError` in `resolve_targets_entities`
- `task.py` lines 86-88 raise `TelegramServiceError` in `resolve_channel_entity`
- `task.py` lines 102-104 raise `StateError` in `resolve_state_file`

**Recommendation:** Either catch `MkoTelebotError` (base class) in the `run()` command to handle all custom exceptions gracefully, or add explicit handling for `TelegramServiceError` and `StateError` with user-friendly error messages. Effort: small.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 2 |
| LOW | 0 |

## Mandatory Fixes

- CLI-004: Unhandled exceptions in run command could leak tracebacks to users

## Advisory Recommendations

- CLI-001: Template config.yaml uses invalid YAML/JSON syntax causing parse errors
- CLI-002: Dead code in monitor.py — launcher() function never invoked
- CLI-003: KeyboardInterrupt handling missing exit code in run command

## Doc Updates Needed

- CLI-002: Consider documenting that launcher() was removed or explaining its original purpose if retention is intended