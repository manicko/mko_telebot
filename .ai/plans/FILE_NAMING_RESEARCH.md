# File Naming Research: mko_telebot

## Research Date
2026-07-06

## 1. Current State Analysis

### 1.1 Package Structure
```
src/mko_telebot/
├── __init__.py
├── main.py              # Entry point wrapper
├── cli.py               # Typer CLI application
├── monitor.py           # Telegram monitoring orchestration
├── logging_setup.py     # Logging configuration setup
└── core/
    ├── __init__.py
    ├── errors.py        # Custom exceptions
    ├── models.py        # Root Pydantic settings model
    ├── telethon_models.py # Telethon-specific models
    ├── chats_config.py  # Channel monitoring models
    ├── config_reader.py # Configuration loading logic
    ├── task.py          # Task/runtime state class
    ├── parser.py        # Search pattern parser (AST)
    ├── paths.py         # Path management
    └── utils.py         # Generic utility functions
```

### 1.2 Naming Issues Identified

#### A) Underscore vs kebab-case inconsistency
- CLI command: `mko-telebot` (kebab-case)
- Package: `mko_telebot` (snake_case)
- User config directories: `mko_telepost` (different name in docs/README)

#### B) Redundant naming patterns
| File | Issue |
|------|-------|
| `telethon_models.py` | "models" suffix redundant (`telethon.py` is cleaner) |
| `chats_config.py` | "config" suffix redundant (`chats.py` is cleaner) |
| `config_reader.py` | "reader" suffix unnecessary (`config.py` is cleaner) |
| `logging_setup.py` | "setup" suffix unnecessary (`logging.py` is cleaner) |
| `task.py` | Generic name - unclear domain context |

#### C) Architecture naming misalignment
The AGENTS.md states architecture is: `app.py` → `telegram_service.py` → `gsheets_reader.py`
Current reality: `cli.py` → `monitor.py` → `core/*.py`

#### D) Log level enum in wrong location
`chats_config.py` contains `LogLevel` enum which should be in `logging.py` (but file doesn't exist at root level).

## 2. Modern Python Naming Best Practices

### 2.1 Module Naming (PEP 8 + Modern Conventions)
- **Use snake_case** for module names (PEP 8): `config_reader.py` ✓
- **Avoid redundant suffixes**: `models.py` not `models_model.py`, `utils.py` not `utils_functions.py`
- **Prefer domain descriptors over technical terms**: `telegram.py` over `telethon_service.py`
- **Keep files focused**: Single responsibility principle applies to file organization

### 2.2 Package Naming (2024 Standards)
- Package name in `pyproject.toml` should match import name: `mko_telebot`
- CLI command name should be derived from package: `mko-telebot` (automatic conversion)
- User config directory should match package name: `~/.config/mko_telebot/` (NOT `mko_telepost`)

### 2.3 Naming Consistency Principles
1. **One concept per file** - if `chats_config.py` has both config AND LogLevel, they're split
2. **Flat is better than nested** - but not at expense of clarity
3. **Use `__all__` exports** - already implemented correctly
4. **Type-annotated names** - models use proper typing

## 3. Domain Analysis

The application purpose: "Telegram classified monitor" scans Telegram channels for keyword matches and forwards messages.

Key domains:
1. **CLI** - Typer-based commands (init, validate, run, config, version)
2. **Telegram/Telethon** - Client connection, message processing, forwarding
3. **Configuration** - YAML loading, Pydantic validation, path resolution
4. **Monitoring** - Channel scanning, message matching, state persistence
5. **Parsing** - Search expression syntax (OR, AND via adjacency, wildcards, exclusions)

## 4. Priority Recommendations

### 4.1 IMMEDIATE (Must Fix)

| Current | Recommended | Reason |
|---------|-------------|--------|
| `src/mko_telebot/core/chats_config.py` | `src/mko_telebot/core/chats.py` | Remove redundant "config" suffix; `chats.py` clearly holds channel configuration models |
| `src/mko_telebot/core/telethon_models.py` | `src/mko_telebot/core/telethon.py` | Remove redundant "models" suffix; module name describes the configuration domain |
| `src/mko_telebot/core/config_reader.py` | `src/mko_telebot/core/config.py` | Remove redundant "reader" suffix; the file IS the config loading logic |
| `src/mko_telebot/logging_setup.py` | `src/mko_telebot/logging.py` | Remove redundant "setup" suffix; module describes logging functionality |
| `src/mko_telebot/core/task.py` | `src/mko_telebot/core/task.py` | **MOVE TO `src/mko_telebot/monitor.py`** - Task class belongs in monitor layer (it orchestrates monitoring operations) |
| `src/mko_telebot/core/models.py` | `src/mko_telebot/core/models.py` | **KEEP AS IS** - Root settings model correctly placed in core |

### 4.2 DOCUMENTATION FIX (Must Fix)

The README and configuration guide reference `mko_telepost` but the package is `mko_telebot`:
- `~/.config/mko_telepost/` → `~/.config/mko_telebot/`
- All documentation references must use `mko_telebot` consistently

### 4.3 STRUCTURE FIX (Recommended)

Current structure groups all models in `core/`. Better organization:

```
src/mko_telebot/
├── __init__.py
├── main.py          # Entry point
├── cli.py           # CLI commands
├── logging.py       # Logging setup (renamed from logging_setup.py)
├── telegram.py      # Telegram client + monitoring (combined from monitor.py + core/telethon.py)
└── core/
    ├── __init__.py
    ├── models.py    # ONLY root TelepostSettings model
    ├── config.py    # ONLY TelepostConfigReader + resolve_path
    ├── chats.py     # ChatConfig, ChannelDefaults, LogLevel
    ├── errors.py    # MkoError, ConfigError, TelegramAuthError, etc.
    ├── paths.py     # AppPaths, PathResolver, APP_PATHS
    └── parser.py    # PatternParser, ASTNode types, search_match
```

## 5. Exact Renaming Plan

### 5.1 Files to Rename (Priority Order)

```
1. src/mko_telebot/logging_setup.py         → src/mko_telebot/logging.py
2. src/mko_telebot/core/chats_config.py      → src/mko_telebot/core/chats.py
3. src/mko_telebot/core/telethon_models.py   → src/mko_telebot/core/telethon.py
4. src/mko_telebot/core/config_reader.py     → src/mko_telebot/core/config.py
```

### 5.2 Import Updates Required After Rename

After renaming, update these imports:

**In `core/__init__.py`:**
```python
# Remove: from .chats_config import ...
# Add:   from .chats import ...

# Remove: from .telethon_models import ...
# Add:   from .telethon import ...

# Remove: from .config_reader import ...
# Add:   from .config import ...
```

**In `cli.py`:**
```python
# Remove: from mko_telebot.logging_setup import ...
# Add:   from mko_telebot.logging import ...
```

**In `logging.py` (new name):**
```python
# Remove: from mko_telebot.core.config_reader import ...
# Add:   from mko_telebot.core.config import ...
```

**In `monitor.py`:**
```python
# Keep telethon imports as-is since they come from core
```

### 5.3 Code Migration for task.py

The `Task` class should move from `core/task.py` to be integrated into the monitoring layer:

**Option A (Recommended):** Move `Task` class into `src/mko_telebot/telegram.py` after merging monitor.py
- Delete `core/task.py` entirely
- The Task class orchestrates Telegram monitoring operations

**Option B:** Keep `core/task.py` but rename to `monitoring.py`
- Only if separation between core models and monitoring runtime is intentional

## 6. Implementation Plan

### 6.1 Phase 1: Non-breaking Renames (can be done separately)
1. Rename `logging_setup.py` → `logging.py` (update imports in cli.py)
2. Rename `chats_config.py` → `chats.py` (update imports in core/__init__.py, models.py)
3. Rename `telethon_models.py` → `telethon.py` (update imports in core/__init__.py, models.py)
4. Rename `config_reader.py` → `config.py` (update imports in core/__init__.py, logging.py)

### 6.2 Phase 2: Architecture Refactor (requires coordination)
1. Consolidate `monitor.py` + `core/telethon.py` → `telegram.py` (new file)
2. Move `Task` class from `core/task.py` → `telegram.py`
3. Delete `core/task.py`

### 6.3 Phase 3: Documentation Fixes
1. Fix all `mko_telepost` references → `mko_telebot` in README.md
2. Fix all `mko_telepost` references → `mko_telebot` in docs/11-guides/configuration.md

## 7. Verification Commands

After implementing renames:
```bash
uv run ruff check src/mko_telebot/
uv run mypy src/mko_telebot/
uv run pytest tests/ -q
```

## 8. Summary (Single Priority Recommendation)

**Primary file rename mapping:**
```
logging_setup.py     → logging.py
chats_config.py      → chats.py  
telethon_models.py   → telethon.py
config_reader.py     → config.py
```

These changes follow the principle: **module name should describe WHAT it contains, not HOW it works.** A file named `chats.py` holds chat-related data. `chats_config.py` redundantly says "this is configuration for chats" - but all files in `core/` ARE configuration, making the suffix meaningless.

The documentation inconsistency (`mko_telepost` vs `mko_telebot`) is a critical bug that confuses users during setup and must be fixed.