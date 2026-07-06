# Phase 01: Monitoring CLI Refactor - Implementation Plan (Part 1/3)

**Plan Date:** 2025-01-20
**Status:** Ready for implementation

---

## Block 1: Error Classes Foundation

### Task 001: Create Custom Exception Classes

**File:** `src/mko_telebot/core/errors.py` (new)

Create custom exception hierarchy for mko_telebot:

```python
class MkoTelebotError(Exception):
    """Base exception for mko_telebot."""
    pass

class ConfigError(MkoTelebotError):
    """Raised when configuration is invalid or cannot be loaded."""
    pass

class TelegramAuthError(MkoTelebotError):
    """Raised when Telegram authentication fails."""
    pass

class TelegramServiceError(MkoTelebotError):
    """Raised when Telegram service operations fail."""
    pass

class StateError(MkoTelebotError):
    """Raised when state file operations fail."""
    pass
```

**Acceptance Criteria:**
- [ ] All 5 exception classes defined with proper inheritance
- [ ] English docstrings for each class
- [ ] `uv run ruff check src/mko_telebot/core/errors.py` passes

### Task 002: Update Existing Code to Use Exceptions

**Files:** `src/mko_telebot/core/task.py`, `src/mko_telebot/core/config_reader.py`, `src/mko_telebot/monitor.py`

Update exception handling to use custom exceptions:
- Import `StateError` in task.py
- Replace `logger.error` + return with `raise StateError` for state operations
- Import `ConfigError` in config_reader.py
- Raise `ConfigError` on YAML load failures or validation errors
- Import `TelegramServiceError` in monitor.py
- Raise on message forwarding failures

**Acceptance Criteria:**
- [ ] Custom exceptions raised in appropriate locations
- [ ] Backward compatibility maintained (no behavior change)
- [ ] All existing tests still pass

---

## Block 2: Logging Foundation

### Task 003: Add Logging to Parser Module

**File:** `src/mko_telebot/core/parser.py`

Add logging to parser module:
```python
import logging
logger = logging.getLogger(__name__)
```

Ensure `logger.exception()` is used in the search_match catch block (already present, verify).

**Acceptance Criteria:**
- [ ] Logger defined at module level
- [ ] Exception logged with context
- [ ] `uv run ruff check src/mko_telebot/core/parser.py` passes

### Task 004: Create Logging Config Template

**File:** `src/mko_telebot/settings/log_config.yaml` (new)

Create YAML logging config template:
```yaml
version: 1
disable_existing_loggers: false
formatters:
  standard:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stderr
  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: standard
    filename: logs/mkotb.log
    maxBytes: 10485760
    backupCount: 5
loggers:
  mko_telebot:
    level: DEBUG
    handlers: [console, file]
    propagate: false
root:
  level: INFO
  handlers: [console]
```

**Acceptance Criteria:**
- [ ] YAML file created in settings directory
- [ ] Console handler for user output (INFO+)
- [ ] File handler for debug logs
- [ ] Rotates at 10MB with 5 backups

---

# Part 2

# Phase 01: Monitoring CLI Refactor - Implementation Plan (Part 2/3)

---

## Block 3: Configuration Models

### Task 005: Create Chats Configuration Models

**File:** `src/mko_telebot/core/chats_models.py` (new)

Create typed models for channel configuration:

```python
class ChatDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_delay_minutes: int = Field(default=7, ge=0)
    delay_jitter_percent: int = Field(default=10, ge=0, le=100)
    max_photos: int = Field(default=1, ge=1, le=10)
    max_width: int = Field(default=1080, ge=100)
    max_height: int = Field(default=1920, ge=100)

class ChatConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: str
    forward_to: list[str]
    keywords: list[str]
    scan_interval: int = Field(default=420, ge=10)
    history_limit: int = Field(default=50, ge=10)
    history_days: int | None = Field(default=None, ge=1)
    overlap: int = Field(default=5, ge=1)

class ChatsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    defaults: ChatDefaults
    chats: list[ChatConfig]
```

**Acceptance Criteria:**
- [ ] All models use `model_config = ConfigDict(extra="forbid")`
- [ ] Field validators for business rules (ge, le constraints)
- [ ] Optional `history_days` field
- [ ] `uv run ruff check src/mko_telebot/core/chats_models.py` passes

### Task 006: Create Paths Module

**File:** `src/mko_telebot/core/paths.py` (new)

Adapt from `example.paths.py`:

```python
class PathResolver(BaseModel):
    base_dir: Path

    def resolve(self, path: Path | str) -> Path:
        path = Path(path).expanduser()
        if not path.is_absolute():
            path = self.base_dir / path
        return path.resolve()

class AppPaths(BaseModel):
    app_dir: Path
    user_dir: Path

    @property
    def user_settings_dir(self) -> Path: ...
    @property
    def app_settings_dir(self) -> Path: ...
    @property
    def app_config(self) -> Path: ...
    @property
    def log_config(self) -> Path: ...

APP_PATHS = AppPaths(...)
```

**Acceptance Criteria:**
- [ ] PathResolver with resolve() method
- [ ] AppPaths with properties for key paths
- [ ] Uses platformdirs for cross-platform user config directory
- [ ] `uv run ruff check src/mko_telebot/core/paths.py` passes

### Task 007: Create Init Service

**File:** `src/mko_telebot/core/init_service.py` (new)

Create init function:

```python
def init_project(force: bool = False) -> Path:
    """Initialize user configuration directory.

    Creates:
    - User settings directory
    - State directory
    - Session directory
    - Copies default config templates

    Args:
        force: Overwrite existing files if True.

    Returns:
        Path to user config directory.
    """
```

**Acceptance Criteria:**
- [ ] Creates all required directories
- [ ] Copies config.yaml template if not exists
- [ ] Copies log_config.yaml template if not exists
- [ ] `--force` flag overwrites existing files
- [ ] `uv run ruff check src/mko_telebot/core/init_service.py` passes

---

## Block 4: CLI Application

### Task 008: Create CLI Application

**File:** `src/mko_telebot/app.py` (new)

Typer CLI with commands:

```python
app = typer.Typer(name="mko-telepost", help="Telegram monitoring tool")

@app.command()
def init(force: bool = False):
    """Initialize configuration."""

@app.command()
def validate(config: Path | None = None):
    """Validate configuration and exit with code."""

@app.command()
def run(config: Path | None = None):
    """Start monitoring."""

@app.command()
def config():
    """Show configuration paths and values."""

@app.command()
def version():
    """Show version info."""
```

**Acceptance Criteria:**
- [ ] All 5 commands implemented
- [ ] `console.print()` only in this file (Rich)
- [ ] Uses `logger` for internal logging
- [ ] `uv run ruff check src/mko_telebot/app.py` passes
- [ ] `uv run python -m mko_telebot.app --help` works

---

# Part 3

# Phase 01: Monitoring CLI Refactor - Implementation Plan (Part 3/3)

---

## Block 5: Tests

### Task 009: Add Task Persistence Tests

**File:** `tests/test_task.py` (new)

Tests for Task class:

```python
def test_load_state_valid(tmp_path):
    """Test loading state from valid JSON file."""

def test_load_state_missing_file():
    """Test handling of missing state file."""

def test_save_state_creates_file(tmp_path):
    """Test state file creation."""

def test_resolve_channel_entity_success(mock_client):
    """Test entity resolution with valid client."""

def test_resolve_targets_entities_partial_failure(mock_client):
    """Test partial failure in target resolution."""
```

**Acceptance Criteria:**
- [ ] Tests use pytest fixtures
- [ ] Tests cover success and error paths
- [ ] `uv run pytest tests/test_task.py` passes

### Task 010: Add Config Loading Tests

**File:** `tests/test_config.py` (new)

Tests for configuration loading:

```python
def test_load_valid_config(tmp_path):
    """Test loading valid config YAML."""

def test_config_missing_required_field():
    """Test ConfigError raised for missing fields."""

def test_config_placeholder_rejection():
    """Test rejection of placeholder credentials."""

def test_path_resolution_relative():
    """Test relative path resolution."""
```

**Acceptance Criteria:**
- [ ] Tests for valid/invalid configs
- [ ] Placeholder value detection tested
- [ ] `uv run pytest tests/test_config.py` passes

### Task 011: Add Error Path Tests

**File:** `tests/test_errors.py` (new)

Tests for error handling:

```python
def test_all_exceptions_inherit_from_base():
    """Test all custom exceptions inherit from MkoTelebotError."""

def test_exception_messages():
    """Test exception messages are user-friendly."""
```

**Acceptance Criteria:**
- [ ] Exception hierarchy verified
- [ ] `uv run pytest tests/test_errors.py` passes

---

## Block 6: Documentation

### Task 012: Expand README

**File:** `README.md`

Add sections:
- **Configuration File Reference:** YAML format for config.yaml
- **CLI Command Reference:** Usage examples for all commands
- **Keyword Pattern Grammar:** Syntax documentation (wildcards, OR, exclusion)
- **Troubleshooting:** Common errors, log locations, recovery steps

**Acceptance Criteria:**
- [ ] All 4 documentation sections added
- [ ] Examples with actual commands
- [ ] Grammar rules documented

### Task 013: Add Module Docstrings

**Files:** `src/mko_telebot/core/parser.py`, `src/mko_telebot/core/task.py`, `src/mko_telebot/core/errors.py`

Add/improve docstrings:
- Document AST node types and their purpose
- Document Task attributes and semantics
- Document when to raise each exception type

**Acceptance Criteria:**
- [ ] All public classes/functions have docstrings
- [ ] Docstrings explain intent, not just mechanics
- [ ] English only in docstrings

---

## Final Validation

After all tasks:
1. `uv run python -m mko_telebot.app --help` - verify CLI works
2. `uv run mko-telepost init --force` - verify config creation
3. `uv run mko-telepost validate` - verify config validation
4. `uv run pytest tests/` - verify all tests pass
5. `uv run ruff check src/` - verify code style
6. `uv run mypy src/` - verify type checking

---

## Task Summary

| Task | File | Priority |
|------|------|----------|
| 001 | core/errors.py | High |
| 002 | task.py, config_reader.py, monitor.py | High |
| 003 | core/parser.py | Medium |
| 004 | settings/log_config.yaml | Medium |
| 005 | core/chats_models.py | High |
| 006 | core/paths.py | High |
| 007 | core/init_service.py | High |
| 008 | app.py | High |
| 009 | tests/test_task.py | Medium |
| 010 | tests/test_config.py | Medium |
| 011 | tests/test_errors.py | Low |
| 012 | README.md | Medium |
| 013 | parser.py, task.py, errors.py | Low |

---

_Phase: 01-monitoring-refactor_
_Plan created: 2025-01-20_