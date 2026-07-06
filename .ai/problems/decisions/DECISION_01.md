# Phase 01: Monitoring CLI Refactor - Context

**Gathered:** 2025-01-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor the Telegram message monitoring module to:
1. Add comprehensive logging throughout all modules
2. Add CLI entry point with `init`, `validate`, `run`, `config` commands
3. Replace raw dict configuration with Pydantic models
4. Add custom exception hierarchy
5. Expand test coverage
6. Expand documentation with configuration and CLI reference

Existing monitoring functionality (keyword matching, message forwarding, state persistence) must be preserved.
</domain>

<decisions>
## Implementation Decisions

### CLI Command Structure

- Four commands: `init`, `validate`, `run`, `config`, `version`
- `init` creates user config directory with templates
- `validate` loads config, validates all files, exits 0 on success, 1 on failure
- `run` starts the monitoring loop with optional `--config` path
- `config` displays configuration paths and current values in a table format
- Short flags: `-c` for config, `-f` for force, `-v` for verbose

### Logging Strategy

- YAML-based dictConfig loaded at startup
- Per-module loggers: `logger = logging.getLogger(__name__)`
- Log levels: DEBUG for internals, INFO for user actions, WARNING/ERROR for issues
- Console output via Rich for user-facing messages only
- File output for persistent logs

### Error Handling Design

- Custom exception hierarchy in `core/errors.py`:
  - `MkoTelebotError` (base)
  - `ConfigError` for configuration issues
  - `TelegramAuthError` for auth/connection failures
  - `TelegramServiceError` for message forwarding failures
  - `StateError` for state file issues
- Replace broad `except Exception` with specific handlers
- Log full stack traces for internal errors, user-friendly messages for CLI

### Configuration Model Organization

- Replace `dict[str, Any]` channels with typed `ChatsConfig` model
- Use `StrEnum` for any fixed values (log levels)
- Use `SecretStr` for credentials
- Keep `TelepostSettings` as root model with proper field types
- All models use `model_config = ConfigDict(extra="forbid")`

### Documentation Scope

- README sections: Installation, Configuration, CLI Commands, Keyword Grammar, Troubleshooting
- Docstrings in English on all public functions
- Inline comments for complex logic (parser AST nodes)
</decisions>

<specifics>
## Specific Requirements

- Preserve all existing monitoring behavior (keyword matching, forwarding, state)
- No changes to the parser grammar or matching logic
- CLI must work with existing config file format
- Tests must use uv/pytest framework
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

_Phase: 01-monitoring-refactor_
_Context gathered: 2025-01-20_


# Phase 01: Monitoring CLI Refactor - Research

**Research Date:** 2025-01-20  
**Status:** Complete

---

## Current Architecture Analysis

### Working Module (monitor.py + core/)

The existing module provides Telegram channel monitoring with:

- **monitor.py (310 lines):** Main monitoring loop, message processing, forwarding logic
- **core/parser.py (404 lines):** Complex pattern matching with DSL (wildcards, OR, exclusion)
- **core/task.py (151 lines):** Per-channel task state management with JSON persistence
- **core/config_reader.py (122 lines):** Pydantic settings but uses raw dicts for channels config

**Current limitations:**
1. No CLI interface - runs directly via `python -m mko_telebot.monitor`
2. Configuration loading at module import time (side effects)
3. No centralized error handling - uses generic Exception catches
4. Settings uses `Any` types in places (channels: `dict[str, Any]`)
5. Minimal documentation beyond README

### Example Files (Target Architecture)

The `example.*` files show a refactored target:

- **example.app.py:** Typer CLI with `init`, `run`, `config`, `version` commands
- **example.models.py:** Clean Pydantic models with proper typing
- **example.errors.py:** Custom exception hierarchy
- **example.paths.py:** Pydantic-based path management
- **examples.telethon_models.py:** Typed Telethon configuration

---

## Modern Best Practices

### 1. CLI with Typer

**Recommended patterns:**
- `console.print()` (Rich) only in CLI layer
- `logger = logging.getLogger(__name__)` everywhere else
- Commands: `init`, `run`, `validate`, `config` for monitoring context
- Config dump via `--dump-config` flag for debugging

### 2. Pydantic v2 Models

**Recommended patterns:**
- Use `BaseModel` for configuration (not `dict[str, Any]`)
- Use `StrEnum` for fixed values (log levels, modes)
- Use `SecretStr` for credentials
- Validator methods for business rules
- `model_config = ConfigDict(extra="forbid")` for strict validation

### 3. Error Handling

**Custom exceptions hierarchy:**
```
MkoTelebotError (base)
├── ConfigError       - configuration issues
├── TelegramAuthError - auth/connection failures  
├── TelegramServiceError - message forwarding failures
└── StateError         - state file issues
```

### 4. Logging Strategy

**Modern approach:**
- YAML-based dictConfig for flexibility
- Console handler for CLI output
- File handler for persistent logs
- Per-module loggers (`logger = logging.getLogger(__name__)`)
- Log levels: DEBUG for internals, INFO for user actions, WARNING/ERROR for issues

### 5. Testing Patterns

**Current tests:**
- test_parser.py uses Hypothesis for property-based testing
- conftest.py provides fixtures

**Needed additions:**
- Unit tests for Task state persistence
- Integration tests for config loading
- Tests for error paths
- Tests for logging output

---

## Refactoring Path

### Block 1: Logging Foundation
- Add logging to all modules without it (parser, task)
- Create YAML logging config template
- Remove print() calls, use logger consistently

### Block 2: CLI Layer (app.py)
- Create Typer CLI entry point
- `init` - copy config templates to user dir
- `validate` - load and validate config, exit with code
- `run` - start monitoring
- `config` - show config paths and current values

### Block 3: Pydantic Models
- Replace raw dict config for channels with typed models
- Create `ChatsConfig`, `ChatConfig`, `ChatDefaults` models
- Use `StrEnum` for any fixed values

### Block 4: Error Classes
- Create `core/errors.py` with custom exceptions
- Replace broad Exception catches
- Add context to error messages

### Block 5: Documentation
- Expand README with:
  - Configuration reference
  - CLI command reference
  - Keyword pattern grammar
  - Troubleshooting guide