---
wave: 4
title: "Monitor Refactoring & CLI Entry Point"
depends_on:
  - .ai/plans/01/PLAN_01_WAVE_03.md
files_modified:
  - src/mko_telebot/monitor.py
  - src/mko_telebot/cli.py
  - src/mko_telebot/__init__.py
  - src/mko_telebot/main.py
  - src/mko_telebot/logging_setup.py
  - pyproject.toml
autonomous: false
note: >
  Task 4.1 (monitor refactor) is HIGH risk — it rewrites the main monitoring entry point.
  Task 4.2 (CLI) is MEDIUM risk — it creates the new Typer app.
  Both must be validated together since the CLI depends on the refactored monitor.
---

# Wave 4 — Monitor Refactoring & CLI Entry Point

Refactor `monitor.py` to remove import-time side effects (TelegramClient creation at module level).
Create the CLI entry point (`cli.py`) with `init`, `validate`, `run`, `config`, `version` commands.
Create `logging_setup.py` for YAML-based logging initialization.

## must_haves

- `monitor.py` no longer creates `TelegramClient` at import time
- `monitor.py` no longer calls `logging.config.dictConfig()` at import time
- `monitor.py` functions accept `TelegramClient` and `TelepostSettings` as parameters
- `cli.py` exists with all five commands: `init`, `validate`, `run`, `config`, `version`
- `cli.py` uses `typer.Typer()` with `-c`/`-f`/`-v` short flags
- `logging_setup.py` provides `setup_logging(config_path)` function
- `pyproject.toml` has `[project.scripts]` entry point: `mko-telebot = mko_telebot.cli:app`
- `main.py` delegates to `cli.py`
- All existing monitoring behavior preserved

---

## Task 4.1 — Refactor monitor.py

<task id="T04_01_monitor_refactor" wave="4" depends_on="[T03_01_config_reader, T03_03_task_refactor]" risk="high">
  <description>
    Refactor `src/mko_telebot/monitor.py` to remove all import-time side effects.

    **Current problems at module level:**
    1. `logging.config.dictConfig(CONFIG.LOGGING.model_dump())` — import-time logging init
    2. `CONFIG.TELETHON_API.client["session"] = session_path` — mutates config at import time
    3. `client: TelegramClient = TelegramClient(...)` — creates Telethon client at import time
    4. `task_queue: asyncio.Queue[Task] = asyncio.Queue()` — creates queue at import time
    5. `process_lock: asyncio.Lock = asyncio.Lock()` — creates lock at import time

    **Required changes:**

    1. Remove ALL import-time side effects (dictConfig calls, client creation, queue/lock creation,
       config mutation). Only the following remain at module level:
       - Standard library imports: `import asyncio`, `import logging`, `import random`, `from pathlib import Path`
       - Framework imports: `from telethon import TelegramClient`
       - Project imports that are pure type/function references (no I/O side effects):
         `from mko_telebot.core.parser import search_match`
         `from mko_telebot.core.task import Task`
         `from mko_telebot.core.paths import APP_PATHS, PathResolver`
         `from mko_telebot.core.models import TelepostSettings`
         `from mko_telebot.core.errors import TelegramAuthError, TelegramServiceError`
         `from telethon.errors import FloodWaitError`
       - `logger = logging.getLogger(__name__)`
       - **REMOVED**: `from mko_telebot.core import CONFIG`, `from mko_telebot.core import PATHS`,
         `logging.config.dictConfig(...)`, `TelegramClient(...)`, `asyncio.Queue()`, `asyncio.Lock()`,
         any config mutation statements
       - No other statements at module level (no config loading, no client instantiation, no queue creation)

    2. The `start_client()` function must accept `TelegramClient` parameter:
       ```python
       async def start_client(client: TelegramClient) -> bool:
       ```

    3. The `launcher()` function becomes the main entry point:
       ```python
       async def run_monitor(settings: TelepostSettings, client: TelegramClient) -> None:
           """Run the monitoring system with provided settings and client."""
       ```

    4. Replace broad `except Exception` with specific exceptions:
       - `start_client` → `TelegramAuthError`
       - `forward_to_users` → `TelegramServiceError`
       - `process_messages` → log and continue (no exception needed)
       - `process_task` → `TelegramServiceError`

    5. Create a new `create_client(settings: TelepostSettings) -> TelegramClient` helper:
       ```python
       def create_client(settings: TelepostSettings) -> TelegramClient:
           """Create and configure a Telethon client from settings."""
           config = settings.telethon.client
           session_path = APP_PATHS.session_dir / config.session
           PathResolver.ensure_file_parent(session_path)
           return TelegramClient(
               session=str(session_path),
               api_id=config.api_id,
               api_hash=config.api_hash.get_secret_value(),
               device_model=config.device_model,
               system_version=config.system_version,
               app_version=config.app_version,
               system_lang_code=config.system_lang_code,
               lang_code=config.lang_code,
           )
       ```

    6. The `main_loop()` function must accept `settings` and `client`:
       ```python
       async def main_loop(settings: TelepostSettings, client: TelegramClient, queue: asyncio.Queue) -> None:
       ```

    7. The `process_and_reschedule` function must accept `client`:
       ```python
       async def process_and_reschedule(task: Task, client: TelegramClient, queue: asyncio.Queue) -> None:
       ```
  </description>
  <targets>
    <file path="src/mko_telebot/monitor.py">
      <semantic_anchors>
        <anchor type="function" name="create_client" />
        <anchor type="function" name="start_client" />
        <anchor type="function" name="run_monitor" />
        <anchor type="function" name="main_loop" />
        <anchor type="function" name="launcher" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/monitor.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/monitor.py` — no errors</step>
    <step>Verify no module-level code except imports and logger</step>
    <step>Verify `create_client` function exists and returns TelegramClient</step>
    <step>Verify `run_monitor` accepts `settings` and `client` parameters</step>
    <step>Verify no `CONFIG` references remain in monitor.py</step>
  </verification>
</task>

---

## Task 4.2 — Create logging setup module

<task id="T04_02_logging_setup" wave="4" depends_on="[T03_01_config_reader]" risk="low">
  <description>
    Create `src/mko_telebot/logging_setup.py` with a centralized logging initialization function.

    ```python
    """Logging configuration for mko_telebot."""

    import logging.config
    from pathlib import Path

    from mko_telebot.core.paths import APP_PATHS
    from mko_telebot.core.config_reader import TelepostConfigReader


    def setup_logging(config_path: Path | None = None) -> None:
        """Initialize logging from YAML configuration.
        
        Loads log_config.yaml from user config directory (or custom path)
        and configures logging via dictConfig. Falls back to basic config
        if the log config file doesn't exist.
        
        Args:
            config_path: Optional custom path to log_config.yaml.
        """
        reader = TelepostConfigReader(log_config_path=config_path)
        raw_config = reader.load_logging_config()
        # Strip LOGGING wrapper key — log_config.yaml has top-level "LOGGING:" key,
        # but dictConfig() expects version/formatters/handlers at top level directly
        log_config = raw_config.get("LOGGING", raw_config) if isinstance(raw_config, dict) else raw_config
        if log_config:
            logging.config.dictConfig(log_config)
        else:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
    ```

    This provides a single call `setup_logging()` that must be called early in the CLI entry point.
  </description>
  <targets>
    <file path="src/mko_telebot/logging_setup.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="function" name="setup_logging" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/logging_setup.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/logging_setup.py` — no errors</step>
    <step>Verify `setup_logging` function exists and accepts optional Path</step>
  </verification>
</task>

---

## Task 4.3 — Create CLI entry point

<task id="T04_03_cli_entry" wave="4" depends_on="[T04_01_monitor_refactor, T04_02_logging_setup]" risk="medium">
  <description>
    Create `src/mko_telebot/cli.py` — the Typer CLI application with five commands.

    Follow the pattern from `src/mko_telebot/example.app.py` (reference implementation).

    **Commands:**

    1. `init`:
       - `--force` / `-f` flag
       - Creates user config directory with template files from package settings
       - Uses `shutil.copy2` to copy config.yaml, secrets.yaml, log_config.yaml from app_settings_dir to user_settings_dir
       - Reports which files were created/skipped
       - Raises `typer.Exit(1)` on failure

    2. `validate`:
       - `--config` / `-c` path option
       - Loads config via `TelepostConfigReader`
       - Calls `validate_files()` to check file existence
       - Exits 0 on success, 1 on failure
       - Prints validation errors via Rich console

    3. `run`:
       - `--config` / `-c` path option
       - `--verbose` / `-v` flag
       - Calls `setup_logging()` first
       - Resolves `--config` path against CWD: `config_path = config_path.resolve()` before passing to reader (CFG-001: resolves relative paths against CWD, not user_dir)
       - Loads config via `TelepostConfigReader`
       - Creates client via `create_client(settings)`
       - Starts client via `start_client(client)`
       - Runs `run_monitor(settings, client)`
       - Handles `KeyboardInterrupt` gracefully
       - Raises `typer.Exit(1)` on failure

    4. `config`:
       - Displays Rich Table with:
         - Package directory
         - User config directory
         - Config file path + status
         - Secrets file path + status
         - Log config file path + status
         - State directory + status
         - Session directory + status
       - Uses `overflow="fold"` for path columns

    5. `version`:
       - Shows version from `importlib.metadata.version("mko_telebot")`

    **Global setup:**
    ```python
    app = typer.Typer(
        name="mko-telebot",
        help="CLI tool for monitoring Telegram channels with keyword filters",
        add_completion=False,
    )
    console = Console()
    ```

    **Entry point:**
    ```python
    def main() -> None:
        app()
    
    if __name__ == "__main__":
        main()
    ```

    Add `[project.scripts]` to `pyproject.toml`:
    ```toml
    [project.scripts]
    mko-telebot = "mko_telebot.cli:app"
    ```

    For the `init` command, copy template files from `APP_PATHS.app_settings_dir` to
    `APP_PATHS.user_settings_dir`. The template files are:
    - config.yaml
    - secrets.yaml
    - log_config.yaml

    For `validate`, use `typer.Exit(code=1)` on failure.

    Import `Console`, `Table` from `rich`.
    Import `typer`.
    Import `setup_logging` from `mko_telebot.logging_setup`.
    Import `TelepostConfigReader`, `APP_PATHS` from `mko_telebot.core`.
    Import `TelegramAuthError`, `ConfigError` from `mko_telebot.core.errors`.
    Import `run_monitor`, `create_client` from `mko_telebot.monitor`.
  </description>
  <targets>
    <file path="src/mko_telebot/cli.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="function" name="init" />
        <anchor type="function" name="validate" />
        <anchor type="function" name="run" />
        <anchor type="function" name="config" />
        <anchor type="function" name="version" />
        <anchor type="function" name="main" />
        <anchor type="variable" name="app" />
        <anchor type="variable" name="console" />
      </semantic_anchors>
    </file>
    <file path="pyproject.toml">
      <target type="config_key" name="project.scripts">
        <action>add</action>
        <value>'    mko-telebot = "mko_telebot.cli:app"'</value>
      </target>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/cli.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/cli.py` — no errors</step>
    <step>Run `uv run mko-telebot --help` — shows help with all five commands</step>
    <step>Run `uv run mko-telebot version` — shows version string</step>
    <step>Run `uv run mko-telebot config` — shows table with paths</step>
    <step>Verify `[project.scripts]` in pyproject.toml</step>
  </verification>
</task>

---

## Task 4.4 — Update main.py

<task id="T04_04_main_update" wave="4" depends_on="[T04_03_cli_entry]" risk="low">
  <description>
    Update `src/mko_telebot/main.py` to delegate to the CLI entry point:

    ```python
    """Entry point for mko_telebot."""
    from mko_telebot.cli import main

    if __name__ == "__main__":
        main()
    ```

    This preserves backward compatibility for `python -m mko_telebot.main`.
  </description>
  <targets>
    <file path="src/mko_telebot/main.py">
      <action>rewrite</action>
      <semantic_anchors>
        <anchor type="module" name="mko_telebot.main" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/main.py` — no errors</step>
    <step>Run `python -c "from mko_telebot.main import main; print('OK')"` — outputs OK</step>
  </verification>
</task>

---

## Wave 4 Validation

1. Run `uv run ruff check src/mko_telebot/` — no errors
2. Run `uv run mypy src/mko_telebot/` — no errors
3. Run `python -m mko_telebot.cli --help` — shows CLI help
4. Run `python -m mko_telebot.cli version` — shows version
5. Run `python -m mko_telebot.cli config` — shows table
6. Verify `monitor.py` has no module-level side effects (no CONFIG, no client creation, no dictConfig)
7. Verify `cli.py` has all five commands with correct signatures