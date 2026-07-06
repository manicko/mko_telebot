# Phase 01 Research — Monitoring CLI Refactor

**Date:** 2026-07-06
**Project:** mko_telebot
**Phase Scope:** CLI entry point, logging strategy, error handling, config model organization, documentation

---

## 1. Typer CLI Framework

### 1.1 Subcommand Structure

Typer uses `app = typer.Typer()` with `@app.command()` decorators for subcommands and `@app.callback()` for shared options. Verified via Context7 (`/fastapi/typer`).

**Pattern:**
```python
import typer

app = typer.Typer(name="mko-telebot", help="...")

@app.command()
def init(force: bool = typer.Option(False, "--force", "-f", help="...")):
    ...

if __name__ == "__main__":
    app()
```

**Confidence:** HIGH — verified from Typer official docs.

### 1.2 Short Flags and Path Validation

Typer supports short flag aliases like `--force`/`-f` and `--config`/`-c`. For path arguments, Typer supports `exists=True`, `file_okay=True`, `dir_okay=False` validation directly on the `typer.Option`.

```python
config_path: Path | None = typer.Option(
    None, "--config", "-c", exists=True, file_okay=True, dir_okay=False,
    help="Path to custom configuration file"
)
```

**Confidence:** HIGH — verified from Context7 Typer path validation snippet.

### 1.3 Exit Codes

`typer.Exit(code=1)` raises an exception that terminates with the given exit code. Code 0 is success (default), code 1 is general error, code 130 is SIGINT (Ctrl+C). The example `app.py` already uses this pattern.

**Confidence:** HIGH — verified from Context7 `/fastapi/typer` terminating tutorial.

### 1.4 Rich Integration

Typer 0.6.0+ supports `rich_markup_mode="rich"` on the app constructor and `typer.echo()` for output. Rich is an optional Typer dependency (`typer[all]`). The project already imports from `rich.console.Console` and `rich.table.Table`.

**Confidence:** HIGH — verified from official Typer release notes and Context7.

### 1.5 Entry Point Registration

The CLI entry point is registered in `pyproject.toml` under `[project.scripts]` (or via `[tool.setuptools]`). Current `pyproject.toml` uses setuptools, so the console script registration format would be:

```toml
[project.scripts]
mko-telebot = "mko_telebot.app:app"
```

Currently `pyproject.toml` has no console scripts entry — this must be added.

**Confidence:** HIGH — standard setuptools convention.

---

## 2. Rich Console & Table Formatting

### 2.1 Console Markup

Rich uses BBCode-like markup: `[bold red]text[/bold red]`, `[green]OK[/green]`, `[cyan]path[/cyan]`. The `Console` class `print()` method renders this by default.

**Confidence:** HIGH — verified from Context7 `/textualize/rich` markup snippets.

### 2.2 Table API

Rich `Table` with `overflow="fold"` (or default `overflow` behavior) controls how long text wraps. The `config` command currently truncates paths. Recommendation: use `overflow="fold"` on path columns or no truncation.

```python
table.add_column("Path", style="white", overflow="fold")
```

**Confidence:** HIGH — verified from Context7 `/textualize/rich` table docs.

### 2.3 Current Pattern from Example

The `example.app.py` file already demonstrates the `config` command pattern with `console.print(table)` and proper `Console()` instantiation at module level.

**Confidence:** HIGH — direct evidence in codebase.

---

## 3. Pydantic v2 Configuration Models

### 3.1 ConfigDict(extra="forbid")

Forbids any undefined fields in Pydantic models. Verified via Context7 `/pydantic/pydantic`:

```python
from pydantic import BaseModel, ConfigDict

class MyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...
```

**Confidence:** HIGH — verified from official Pydantic docs.

### 3.2 SecretStr for Credentials

`pydantic.SecretStr` masks sensitive field values in repr/dumps. The `ClientConfig` in `examples.telethon_models.py` already uses this pattern:

```python
from pydantic import SecretStr

api_hash: SecretStr = Field(...)
```

Use `.get_secret_value()` to extract the plaintext value.

**Confidence:** HIGH — verified from Pydantic docs and codebase examples.

### 3.3 StrEnum for Fixed Values

Python 3.11+ has `enum.StrEnum` (backport via `str, enum.Enum` for older versions). Use for log levels, exit codes, etc. Project requires Python 3.14+, so `StrEnum` is available natively.

```python
from enum import StrEnum

class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
```

**Confidence:** HIGH — Python 3.11+ standard library.

### 3.4 ChatsConfig — Typed Model for Channels

Current `config_reader.py` has `channels: dict[str, Any]` in `MonitoringSettings`. Target pattern from `example.models.py` uses `ChatsConfig` with `ChatConfig` per-channel:

```
TelepostSettings
  ├── telethon: TelethonConfig
  │     ├── is_user: bool
  │     ├── phone_or_token: SecretStr
  │     └── client: ClientConfig
  └── chats: ChatsConfig
        ├── defaults: ChatDefaults
        └── chats: list[ChatConfig]
```

**Important difference:** In the current mko_telebot codebase, the channel config is keyed by channel name (dict with DEFAULTS + channel entries), not a flat list. The typed model must support this structure — either via `dict[str, ChannelConfig]` or a custom model with `DEFAULTS` handling. The `config_reader.py` merges default settings per-channel at runtime.

**Confidence:** MEDIUM — the exact shape needs design. The `example.models.py` shows one approach (list-based). The existing code uses dict-based. The decision document says "typed `ChatsConfig` model" without specifying which shape. The planner must decide.

### 3.5 model_validator for Cross-Field Validation

`@model_validator(mode="after")` runs after field validators and receives the fully-validated model instance. Used for resolving defaults from the root settings model.

```python
@model_validator(mode="after")
def resolve_defaults(self) -> Self:
    # Fill per-channel defaults from global defaults
    ...
    return self
```

**Confidence:** HIGH — verified from Context7 `/pydantic/pydantic`.

---

## 4. Logging Strategy

### 4.1 Module-Level Logger Pattern

```python
import logging
logger = logging.getLogger(__name__)
```

Currently `monitor.py`, `parser.py`, and `task.py` all call `logging.config.dictConfig(CONFIG.LOGGING.model_dump())` at **module import time** — a side effect that prevents clean CLI startup sequence.

### 4.2 YAML dictConfig Loading

The `log_config.yaml` file defines formatters, handlers, loggers, and root config. It is loaded by `config_reader.py` but **never actually configured into the logging system** at startup (audit finding CLI-001: HIGH severity).

**Correct startup sequence:**

```python
# In app.py startup:
config_data = reader.load_logging_config()  # from YAML or defaults
logging.config.dictConfig(config_data)       # apply before any service call
```

### 4.3 Logger Name Mismatch

Audit CFG-006: The template `log_config.yaml` defines a logger named `"telebot"` but every module uses `logging.getLogger(__name__)` which produces `mko_telebot.*` names. The named logger section is dead config — all logs fall through to `root`.

**Fix required:** Rename the logger entry to `"mko_telebot"` so per-module loggers inherit through the hierarchy.

**Confidence:** HIGH — direct evidence in codebase + audit findings.

---

## 5. Error Handling Design

### 5.1 Current Issues

- `monitor.py` uses broad `except Exception` in 6+ places (lines 44, 63, 78, 93, 147, 180, 219)
- `start_client()` returns `True`/`False` instead of raising
- `config_reader.py` loads config at import time — any error crashes before CLI has control

### 5.2 Custom Exception Hierarchy

The `example.errors.py` shows the target pattern. Based on the phase decisions:

```
MkoTelebotError (base)
├── ConfigError
├── TelegramAuthError
├── TelegramServiceError
└── StateError
```

**Confidence:** HIGH — specified in phase decisions.

### 5.3 Exception Handling Pattern per CLI Command

Each command should:
1. Catch specific custom exceptions
2. Log full traceback via `logger.exception()`
3. Print user-friendly message via `console.print("[red]...[/red]")`
4. `raise typer.Exit(code=1)` to signal failure

**Current gap:** `logger.exception()` is called but without logging configuration (CLI-001), the traceback leaks to stderr via Python's `lastResort` handler.

**Confidence:** HIGH — verified from audit findings.

---

## 6. Configuration Model Organization — Detailed Findings

### 6.1 Current config_reader.py Structure

```python
class WorkingPaths(BaseSettings):
    root_dir, module_name, user_folder, default_settings, user_settings, state_dir, session_dir, config_files

PATHS = WorkingPaths()  # Module-level instantiation

class TelethonApiSettings(BaseModel):
    is_user, phone_or_token, client: dict[str, Any]

class MonitoringSettings(BaseSettings):
    channels: dict[str, Any]     # <-- needs typing
    channels_delay: int

class LoggingSettings(BaseModel):
    version, disable_existing_loggers, formatters, handlers, loggers, root   # all dict[str, Any]

class Config(BaseSettings):
    TELETHON_API, LOGGING, MONITORING

CONFIG = Config.load()   # Module-level side effect import
```

### 6.2 Target State

- `ChatsConfig` typed model replaces `dict[str, Any]` channels
- `ClientConfig` typed model replaces `dict[str, Any]` client
- `LoggingSettings` uses structured types via dictConfig-compatible models or stays as dict (dictConfig requires specific dict structure)
- Config loaded lazily on CLI command, not at import time
- `CONFIG = Config.load()` removed from module scope

### 6.3 Example: Typed ClientConfig

From `examples.telethon_models.py`:
```python
class ClientConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_id: int = Field(..., gt=0)
    api_hash: SecretStr = Field(...)
    session: str = Field(default="first_session")
    device_model: str | None = None
    system_version: str | None = None
    system_lang_code: str | None = None
    lang_code: str | None = None
```

### 6.4 Module-Level Import Side Effects

**File** | **Side Effect** | **Severity**
----------|----------------|-------------
`core/__init__.py` | Imports `CONFIG, PATHS` from `config_reader` | HIGH
`core/config_reader.py` | `PATHS = WorkingPaths()`, `CONFIG = Config.load()` at import time | HIGH
`monitor.py` | `logging.config.dictConfig(...)` at import time | HIGH
`parser.py` | `logging.config.dictConfig(...)` at import time | MEDIUM
`task.py` | `logging.config.dictConfig(...)` at import time | MEDIUM (also at import)

All import-time side effects must be removed. Config should be loaded explicitly in the CLI command flow.

**Confidence:** HIGH — direct evidence in codebase.

---

## 7. CLI Commands — Analysis

### 7.1 `init` Command

Creates user config directory and copies template files from `settings/` to `~/.config/mko_telebot/settings/`.

- The `example.init_service.py` provides a ready-made pattern (`_copy_templates`, `init_project`)
- Need `--force/-f` flag to overwrite existing files
- Must respect `APP_PATHS` from `core/paths.py`

### 7.2 `validate` Command

Loads config, validates all files, exits 0 on success / 1 on failure.

- New command — no existing implementation
- Should load config, validate Pydantic models, check file existence
- Rich console output for pass/fail display

### 7.3 `run` Command

Starts the monitoring loop. Optional `--config/-c` path.

- Refactors `monitor.py` to be a service, not the entry point
- Needs to handle `--config` path resolution (audit CFG-001: relative paths must resolve against CWD)
- Currently `monitor.py` has `run_monitor()` and `launcher()` — these should become callable from the CLI

### 7.4 `config` Command

Shows configuration paths and current values as a Rich table.

- Audit CLI-003: Path column truncation — use `overflow="fold"`
- Must show current Pydantic model values

### 7.5 `version` Command

Shows version string via `importlib.metadata`.

- Already demonstrated in `example.app.py`

---

## 8. monitor.py Refactoring Requirements

### 8.1 Current Dependencies

`monitor.py` imports from `mko_telebot.core`:
- `CONFIG` (module-level — must change to lazy loading)
- `PATHS` (module-level — acceptable as it's pure path construction)
- `Task` (class — fine)
- `search_match` (function — fine)
- `utils` (module — fine)

### 8.2 Functions to Extract/Refactor

| Function | Status | Action |
|----------|--------|--------|
| `start_client()` | `except Exception` | Add specific `TelegramAuthError` |
| `build_message_link()` | `except Exception` | Specific handler or remove try/except entirely |
| `build_sender_tag()` | `except Exception` | Specific handler or remove try/except entirely |
| `forward_to_users()` | Mix of `FloodWaitError` and `Exception` | OK — specific handlers for FloodWait, use `TelegramServiceError` for others |
| `process_messages()` | `except Exception` | Specific handler per failure mode |
| `process_task()` | Good — has `FloodWaitError` handler | Keep pattern, add typed hints |
| `main_loop()` | Config-dependent | Must accept config as parameter instead of reading `CONFIG` |
| `run_monitor()` | Config-dependent | Parameterize |
| `launcher()` | Entry point | **Remove** — replaced by Typer CLI |

### 8.3 Key Refactoring Pattern

```python
async def run_monitor(settings: TelepostSettings) -> None:
    """Start the monitoring loop with given configuration."""
    ...

# CLI command calls:
@app.command()
def run(config_path: Path | None = None):
    settings = load_config(config_path)
    asyncio.run(run_monitor(settings))
```

**Confidence:** HIGH — standard pattern, already shown in `example.app.py`.

---

## 9. Audit Findings That Must Be Resolved in Phase 01

| ID | Severity | Area | Required Change |
|----|----------|------|-----------------|
| **CLI-001** | HIGH | Logging | Configure `logging.config.dictConfig()` at CLI startup before any service call |
| **CLI-002** | MEDIUM | CLI | Replace "mko init" references with "mko-telebot init" in user-facing messages |
| **CLI-003** | LOW | CLI | Fix `config` table path truncation with `overflow="fold"` |
| **CFG-001** | HIGH | Config | Fix relative `--config` path resolution against CWD, not `user_dir` |
| **CFG-006** | LOW | Logging | Rename logger in `log_config.yaml` from `"telebot"` to `"mko_telebot"` |

**Confidence:** HIGH — all findings extracted from validated audit reports.

---

## 10. Dependency Audit

**Current dependencies (from pyproject.toml):**
- `aiofiles>=25` — async file I/O for state persistence
- `platformdirs>=4` — cross-platform user config directory
- `pydantic>=2` — data validation
- `pydantic-settings>=2` — settings management (BaseSettings)
- `PyYAML>=6` — YAML config loading
- `telethon>=1` — Telegram client
- **Missing: `typer`, `rich`** — must be added for CLI

**Required additions for Phase 01:**
- `typer>=0.12` (stable version in 2025-2026)
- `rich>=13` (rich table/console support)

**Confidence:** MEDIUM — version numbers are informed estimates. Actual version selection should check current PyPI at implementation time.

---

## 11. Key Architectural Decisions for Planner

### 11.1 Lazy Configuration Loading

**Current:** `CONFIG = Config.load()` at module import → cascading side effects.
**Target:** Config loaded explicitly per CLI command.

```python
# In CLI command:
def _load_config(config_path: Path | None) -> TelepostSettings:
    reader = TelepostConfigReader(config_path)
    logging.config.dictConfig(reader.load_logging_config())
    return reader.load()
```

### 11.2 ConfigReader vs Direct Model Loading

Two approaches:
1. **ConfigReader class** (as in `example.config_reader.py`): encapsulates YAML loading, path resolution, logging config — cleaner, tested pattern
2. **Direct model_validate**: simpler but lacks path resolution, logging injection

**Recommendation:** Use the `ConfigReader` class pattern. It provides `validate_files()`, `load_logging_config()`, and path resolution.

### 11.3 ChatsConfig Model Shape

**Decision needed:**
- Dict-based: `channels: dict[str, ChannelConfig]` with `"DEFAULTS"` key — preserves backward compatibility
- List-based: `chats: ChatsConfig` with `defaults` and `chats: list[ChatConfig]` — matches `example.models.py`

The existing config files use the dict format. Migration requires either dynamic config conversion or a custom model validator.

### 11.4 Module Restructuring

**Recommendation:**

```
src/mko_telebot/
├── __init__.py
├── app.py                  # NEW — Typer CLI app (replace main.py role)
├── main.py                 # KEEP as thin launcher OR REMOVE
├── monitor.py              # REFACTOR — remove entry point, keep monitoring logic
├── core/
│   ├── __init__.py         # FIX — remove CONFIG import side effect
│   ├── config_reader.py    # REWRITE — lazy loading, typed models
│   ├── errors.py           # NEW — custom exception hierarchy
│   ├── models.py           # NEW — Pydantic models (extract from config_reader)
│   ├── paths.py            # NEW or KEEP — APP_PATHS (already in config_reader)
│   ├── parser.py           # KEEP — fix import side effect
│   ├── task.py             # KEEP — fix import side effect
│   └── utils.py            # KEEP
```

**Confidence:** MEDIUM — the exact file structure is at the planner's discretion. The phase context says "KiloCode's Discretion" for exact CLI implementation details.

---

## 12. Risks and Uncertainties

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing `CONFIG` import from `core/__init__.py` breaks existing consumers (`monitor.py`, `parser.py`, `task.py`) | HIGH | Refactor all consumers to accept config as parameter instead of module-level singleton |
| Async `monitor.py` functions need config parameter instead of module-level `CONFIG` | MEDIUM | Parameterize all async functions with `settings: TelepostSettings` |
| Converting `dict[str, Any]` channels to typed model may break config file format | MEDIUM | Use `model_validator` to transform dict to typed model, or use dict-based model |
| Logging reconfiguration after startup may drop existing handlers | LOW | Configure logging once at the earliest possible CLI entry point |
| `parser.py` and `task.py` both call `logging.config.dictConfig` at import time | LOW | Remove those calls; logging is configured once at CLI startup |
| Tests import `CONFIG` from `core/__init__.py` | MEDIUM | Tests need refactoring to inject config instead of relying on module-level singleton |

---

## 13. Summary of Confidence Ratings

| Area | Confidence | Source |
|------|-----------|--------|
| Typer subcommand pattern | HIGH | Context7 + codebase example |
| Rich table/console markup | HIGH | Context7 + codebase example |
| Pydantic ConfigDict(extra="forbid") | HIGH | Context7 |
| Pydantic SecretStr | HIGH | Context7 + codebase examples |
| StrEnum availability | HIGH | Python 3.14+ standard library |
| Logging dictConfig | HIGH | Python stdlib docs + codebase |
| CLI-001/002/003 findings | HIGH | Audit validation reports |
| CFG-001/006 findings | HIGH | Audit validation reports |
| Import-time side effects | HIGH | Direct codebase evidence |
| ChatsConfig exact model shape | MEDIUM | Decision needed on dict vs list |
| Module restructuring | MEDIUM | Planner discretion per phase context |
| Typer/Rich exact versions | MEDIUM | PyPI should be checked at implementation |