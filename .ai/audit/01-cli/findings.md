# Phase 01 Audit Findings — CLI Entry Point & Command Layer

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/01-audit-cli.md
**Status:** complete
**Validated:** no

---

## Findings

### CLI-001: Logging is never configured — tracebacks leak to stderr and "Check logs for details" is misleading

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/app.py`, `src/mko_telepost/core/config_reader.py` |
| **Classification** | mandatory |

**Description:**

The CLI entry point (`app.py`) never configures the Python logging system — there is no
`logging.basicConfig()`, `logging.config.dictConfig()`, or any call to
`TelepostConfigReader.load_logging_config()` in the CLI startup path. A `log_config.yaml`
template is shipped and `TelepostConfigReader.load_logging_config()` is implemented, but
`load_logging_config` is referenced only in tests, never in production code.

Two direct consequences:

1. **Raw tracebacks leak to the user.** Every error path in `app.py` calls
   `logger.exception(...)` (lines 116, 170, 223). With no handlers attached to the
   `mko_telepost` logger or the root logger, Python's `lastResort` handler writes the
   full traceback to stderr. This directly violates Phase 01 Dimension 1
   ("Consistent error handling — No raw tracebacks leak to the user") and AGENTS.md
   ("Use custom exceptions ... Never silently swallow errors").

2. **"Check logs for details." is misleading.** The CLI prints
   `"✒ Configuration error. Check logs for details."` (line 117), but no log file is
   ever written and no log handler is configured — there is nothing to check. The
   `log_config.yaml` that would write a log file is never loaded.

**Evidence:**

Runtime verification — running the `run` command against a default placeholder config
(the state produced by `mko-telepost init`):

```
$ uv run mko-telepost run
Starting mko_telepost...
✒ Configuration error. Check logs for details.
---EXIT=1
```

stderr captured a full Pydantic `ValidationError` traceback (excerpt):

```
Configuration load failed
Traceback (most recent call last):
  File "...\src\mko_telepost\core\config_reader.py", line 150, in _validate_settings
    return TelepostSettings(**config_data)
  ...
pydantic_core._pydantic_core.ValidationError: 2 validation errors for TelepostSettings
  google_sheets.spreadsheet_id
    Value error, spreadsheet_id appears to be a placeholder value. ...
  chats
    Input should be a valid dictionary or instance of ChatsConfig ...
```

Source evidence:
- `src/mko_telepost/app.py` lines 29, 116-118, 169-172, 222-225 — `logger.exception()`
  calls with no logging setup anywhere in the file.
- `src/mko_telepost/core/config_reader.py` line 161 — `load_logging_config()` defined but
  never called from `app.py`, `telegram_service.py`, or `__init__.py` (verified via grep
  across `src/`; the only non-self caller is `tests/test_config_reader.py:113`).
- `src/mko_telepost/settings/log_config.yaml` — shipped but unused at runtime.

**Recommendation:**

Configure logging once at CLI startup before any service call, using the shipped
`log_config.yaml` via `TelepostConfigReader.load_logging_config()` (falling back to
`logging.basicConfig()` if the file is absent). This makes the "Check logs for details"
message true and routes `logger.exception()` output to the configured file handler
instead of the stderr lastResort handler, so no raw traceback reaches the terminal.
Effort: small. Priority: high — the entire friendly-error UX is currently non-functional
on every error path.

---

### CLI-002: User-facing guidance references wrong command name (`mko init` vs `mko-telepost init`)

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/config_reader.py`, `src/mko_telepost/core/init_service.py` |
| **Classification** | advisory |

**Description:**

The actual CLI entry point and registered Typer app name is `mko-telepost`
(`src/mko_telepost/app.py` line 35: `name="mko-telepost"`; `pyproject.toml` console
script). `app.py` itself consistently tells the user to run `mko-telepost init`
(lines 83, 103, 161). However, two core-layer modules emit user-facing guidance
referencing a non-existent `mko` command:

- `src/mko_telepost/core/config_reader.py` line 74 —
  `"Run 'mko init' to create default configuration."` (raised inside a `ConfigError`).
- `src/mko_telepost/core/init_service.py` module docstring line 5 —
  `"When user runs `mko init`, this module copies template files ..."`

When `config_reader._load_yaml` raises the `ConfigError` from line 72-75, the message
"Run 'mko init'" surfaces to the user (it is in the exception text). A user who copies
that command gets `mko: command not found` (or a shell error) — the working command is
`mko-telepost init`.

**Evidence:**

`src/mko_telepost/core/config_reader.py` lines 71-75:
```python
if not resolved.exists():
    raise ConfigError(
        f"Configuration file not found: {resolved}\n"
        f"Run 'mko init' to create default configuration."
    )
```

`src/mko_telepost/core/init_service.py` lines 4-7:
```python
"""
Init service for mko_telepost.

Handles initialization of user configuration directory with default templates.
When user runs `mko init`, this module copies template files ...
```

Contrast with the consistent `mko-telepost init` used in
`src/mko_telepost/app.py` lines 83, 103, 257, 262.

**Recommendation:**

Update the two `mko init` references to `mko-telepost init` so all user-facing
guidance points at the command that actually exists. This is a doc/message fix in
core modules — keep `app.py` as the source of truth for the command name.
Effort: trivial. Priority: medium — prevents a dead-end error message for users who
hit the config-not-found path.

---

### CLI-003: `config` command truncates path columns so distinct paths look identical

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/app.py` |
| **Classification** | advisory |

**Description:**

The `config` command (`src/mko_telepost/app.py` lines 228-265) renders a Rich
`Table` whose "Path" column is auto-sized to the terminal width. On a typical
80-column terminal, the three most important rows are truncated to the same prefix:

```
┌───────────────────┬────────────────────────────────────────────────┬────────┐
│ Setting           │ Path                                           │ Status │
├───────────────────┼────────────────────────────────────────────────┼────────┤
│ User Config       │ C:\Users\Om\AppData\Local\mko_telepost\mko_te… │ ✓      │
│ User Settings Dir │ C:\Users\Om\AppData\Local\mko_telepost\mko_te… │ ✓      │
│ Config File       │ C:\Users\Om\AppData\Local\mko_telepost\mko_te… │ ✓      │
└───────────────────┴────────────────────────────────────────────────┴────────┘
```

`User Config` (`USER_DIR`) and `User Settings Dir` (`USER_DIR/settings`) are
different paths, but the truncated display makes them visually identical — the
`settings` suffix that distinguishes them is cut off. The command's entire purpose
is to show users where their config lives, so the truncation defeats it.

**Evidence:**

Runtime verification — `uv run mko-telepost config` output (above), captured on a
standard-width terminal. The distinguishing `\settings` suffix on
`user_settings_dir` (`src/mko_telepost/core/paths.py` line 100-101) is truncated
away.

Source: `src/mko_telepost/app.py` lines 235-265 construct the table with default
column widths and no overflow rule.

**Recommendation:**

For the `config` command specifically, either (a) widen/weight the Path column so
paths are not truncated, or (b) wrap long paths instead of truncating (Rich supports
`overflow="fold"` or `no_wrap=False`). The Status column can be narrower since it only
holds "✓" or a short message. Effort: trivial. Priority: low — cosmetic, but the
command is the primary way users discover their config location.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 1 |

## Mandatory Fixes

- **CLI-001** — Configure logging at CLI startup so `logger.exception()` does not
  leak tracebacks to stderr and the "Check logs for details." message has a real log
  to point at.

## Advisory Recommendations

- **CLI-002** — Align `mko init` references in `config_reader.py` and
  `init_service.py` with the real `mko-telepost init` command.
- **CLI-003** — Stop truncating path columns in the `config` table so distinct
  paths are distinguishable.

## Doc Updates Needed

- **CLI-002** also covers the `init_service.py` module docstring (`mko init` →
  `mko-telepost init`).

---

## Runtime Verification Record

| Step | Command | Result |
|------|---------|--------|
| R1 — Import | `uv run python -c "from mko_telepost import app; ..."` | OK — `IMPORT OK` |
| R2 — CLI Help | `mko-telepost --help` and each subcommand `--help` | OK — exit 0 for all 5 invocations |
| R3 — Linter | `uv run ruff check src/mko_telepost/app.py` | OK — `All checks passed!` (exit 0) |
| R3 — Type check | `uv run mypy src/mko_telepost/app.py` | OK — `Success: no issues` (exit 0) |
| R4 — Tests | `uv run pytest tests/ -q` | OK — `224 passed in 2.00s` (exit 0) |
| Runtime probe | `uv run mko-telepost run` (invalid config) | FAIL — leaks traceback to stderr (evidence for CLI-001) |
| Runtime probe | `uv run mko-telepost config` | OK exit 0, but truncated paths (evidence for CLI-003) |
| Runtime probe | `uv run mko-telepost version` | OK — `mko_telepost version 1.0.0` |

Layer boundary check: grep for `from mko_telepost.app` / `import app` /
`from .app` / `from ..app` inside `src/mko_telepost/core/` returned **no matches** —
no reverse imports from CLI into core/service. Dependency direction
(CLI → Service → Core) is intact.

