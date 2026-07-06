---
wave: 3
title: "Core Refactoring — Config Reader, Monitor, Logging Setup"
depends_on:
  - .ai/plans/01/PLAN_01_WAVE_02.md
files_modified:
  - src/mko_telebot/core/config_reader.py
  - src/mko_telebot/core/__init__.py
  - src/mko_telebot/core/task.py
  - src/mko_telebot/monitor.py
autonomous: false
note: >
  Task 3.1 (config_reader refactor) is HIGH risk. It rewrites the config loading
  pipeline. A research gate is inserted before Wave 4 execution to verify correctness.
---

# Wave 3 — Core Refactoring

Refactor `config_reader.py` to use the new typed models with lazy loading (no import-time I/O).
Refactor `monitor.py` to remove import-time side effects and use the new config reader.
Add logging initialization module.

**Important constraint:** `core/__init__.py` currently re-exports `CONFIG` and `PATHS` from
`config_reader.py`. After this wave, `CONFIG` is no longer created at import time — it must be
loaded explicitly. The `core/__init__.py` must be updated accordingly.

## must_haves

- `config_reader.py` rewritten: lazy loading via `TelepostConfigReader.load()`, no module-level CONFIG singleton
- `core/__init__.py` updated: no longer exports `CONFIG`, exports new symbols
- `monitor.py` no longer calls `logging.config.dictConfig()` at import time
- `monitor.py` no longer creates `TelegramClient` at import time
- `core/task.py` updated to accept config explicitly (no implicit CONFIG dependency)
- Task `resolve_state_file()` uses `APP_PATHS` from `core/paths.py` instead of `PATHS.state_dir`

---

## Task 3.1 — Refactor config_reader.py

<task id="T03_01_config_reader" wave="3" depends_on="[T02_01_paths_module, T02_04_root_model]" risk="high">
  <description>
    Rewrite `src/mko_telebot/core/config_reader.py` to use the new typed Pydantic models
    with lazy loading. No import-time I/O or singletons.

    The current file creates `PATHS = WorkingPaths()` and `CONFIG = Config.load()` at module level.
    These must be removed. `PATHS` is now in `paths.py`. `CONFIG` must be loaded explicitly.

    New `TelepostConfigReader` class:

    ```python
    class TelepostConfigReader:
        """Configuration reader for mko_telebot."""

        def __init__(
            self,
            config_path: Path | None = None,
            secrets_path: Path | None = None,
            log_config_path: Path | None = None,
        ):
            """
            Initialize reader with optional custom paths.
            Default paths come from APP_PATHS.
            """
            self.config_path = config_path or APP_PATHS.config_file
            self.secrets_path = secrets_path or APP_PATHS.secrets_file
            self.log_config_path = log_config_path or APP_PATHS.log_config_file
            self.resolver = PathResolver(APP_PATHS.user_dir)

        def load(self) -> TelepostSettings:
            """Load and validate full configuration."""
            # 1. Load config.yaml (MONITORING section)
            # 2. Load secrets.yaml (TELETHON_API section)
            # 3. Merge (secrets override config)
            # 4. model_validate(merged) into TelepostSettings
            #    Note: TelepostSettings uses validation_alias="TELETHON_API" and
            #    validation_alias="MONITORING", so model_validate accepts the
            #    uppercase YAML keys from existing config files directly.
            # 5. Resolve relative paths
            # 6. Return TelepostSettings

        def load_logging_config(self) -> dict[str, object]:
            """Load logging config from log_config.yaml with path resolution."""

        def validate_files(self) -> list[str]:
            """Validate that required files exist. Return list of error messages."""

        def load_config_yaml(self) -> dict[str, object]:
            """Load only config.yaml, return raw dict."""

        @classmethod
        def from_user_dir(cls) -> TelepostConfigReader:
            """Create reader with default user directory paths."""
    ```

    Methods to preserve from the old `Config.load()`:
    - Merge config.yaml (MONITORING section) and secrets.yaml (TELETHON_API section)
    - Resolve relative paths in handlers (log files)
    - Validate with Pydantic

    The old `Config`, `MonitoringSettings`, `LoggingSettings`, `TelethonApiSettings`,
    `WorkingPaths` classes must be removed from this file (they were the old dict-based approach).
    The new models are in `telethon_models.py`, `chats_config.py`, `models.py`.

    Keep `resolve_path` utility function — it's still needed for path resolution.
    Move `ensure_path_exists` to `paths.py` if not already there.

    Raise `ConfigError` (from errors.py) on validation failures with user-friendly messages.
  </description>
  <targets>
    <file path="src/mko_telebot/core/config_reader.py">
      <target type="class" name="Config">
        <action>replace_with">TelepostConfigReader</action>
      </target>
      <target type="class" name="MonitoringSettings">
        <action>delete</action>
      </target>
      <target type="class" name="LoggingSettings">
        <action>delete</action>
      </target>
      <target type="class" name="TelethonApiSettings">
        <action>delete</action>
      </target>
      <target type="class" name="WorkingPaths">
        <action>delete</action>
      </target>
      <target type="variable" name="CONFIG">
        <action>delete</action>
      </target>
      <target type="variable" name="PATHS">
        <action>delete</action>
      </target>
      <target type="variable" name="__all__">
        <action>update</action>
      </target>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/config_reader.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/config_reader.py` — no errors</step>
    <step>Verify no module-level CONFIG or PATHS singletons exist</step>
    <step>Verify TelepostConfigReader class exists with load(), load_logging_config(), validate_files(), from_user_dir() methods</step>
    <step>Verify ConfigError is raised for missing/bad config files</step>
  </verification>
</task>

<research_gate>
  <reason>Task 3.1 rewrites the entire config loading pipeline. Before Wave 4 can execute,
  the validator must confirm that `TelepostConfigReader.load()` correctly handles:
  - Merged config.yaml + secrets.yaml
  - Missing files (ConfigError)
  - Path resolution for log handlers
  - The existing config file format</reason>
</research_gate>

---

## Task 3.2 — Update core/__init__.py

<task id="T03_02_core_init" wave="3" depends_on="[T03_01_config_reader]" risk="low">
  <description>
    Update `src/mko_telebot/core/__init__.py`:

    Remove `CONFIG` from exports (it no longer exists at module level).
    Remove `PATHS` from imports (it's now in `paths.py`, or keep it if re-exporting from paths).

    New exports:
    ```python
    from mko_telebot.core.errors import MkoTelebotError, ConfigError, TelegramAuthError, TelegramServiceError, StateError
    from mko_telebot.core.paths import APP_PATHS, AppPaths, PathResolver
    from mko_telebot.core.models import TelepostSettings
    from mko_telebot.core.config_reader import TelepostConfigReader
    from mko_telebot.core.parser import search_match
    from mko_telebot.core.task import Task
    from mko_telebot.core.utils import load_config, merge_dicts, resolve_path, ensure_path_exists
    ```

    Keep backward compatibility: if anything still imports `CONFIG` from the old location,
    it will break — but all consumers in this phase will be updated to use the new config reader.
  </description>
  <targets>
    <file path="src/mko_telebot/core/__init__.py">
      <action>rewrite</action>
      <semantic_anchors>
        <anchor type="module" name="mko_telebot.core" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/__init__.py` — no errors</step>
    <step>Verify `from mko_telebot.core import TelepostConfigReader, APP_PATHS, TelepostSettings, MkoTelebotError, Task, search_match` all resolve</step>
    <step>Verify `from mko_telebot.core import CONFIG` now raises ImportError</step>
  </verification>
</task>

---

## Task 3.3 — Refactor task.py to use new config system

<task id="T03_03_task_refactor" wave="3" depends_on="[T02_01_paths_module, T02_03_chats_config]" risk="medium">
  <description>
    Refactor `src/mko_telebot/core/task.py`:

    1. Replace usage of `PATHS.state_dir` with `APP_PATHS.state_dir` from `core/paths.py`
    2. Remove import of `PATHS` from the old location
    3. Replace bare `except Exception` with specific exception handlers:
       - `except Exception as e:` in `resolve_targets_entities` → `TelegramServiceError`
       - `except Exception as e:` in `resolve_channel_entity` → `TelegramAuthError`
       - `except Exception as e:` in `resolve_state_file` → `StateError`
       - `except Exception as e:` in `load_state` → `StateError`
       - `except Exception as e:` in `save_state` → `StateError`
    4. The `__init__` method should accept a `ChannelConfig` instance instead of individual parameters

    **Cross-wave sequencing note:** The only caller of `Task()` is `monitor.py`'s `main_loop()`,
    which constructs `Task` from dict keys. That caller is refactored in Wave 4 (Task 4.1).
    Between this task and Wave 4 execution, `monitor.py` will be in a broken state.
    Run Wave 3 validation first, then immediately execute Wave 4 to restore consistency.
    The `main_loop()` caller update in Task 4.1 must accept the new `Task.__init__(config: ChannelConfig)` signature.
    5. Import `ChannelConfig` from `chats_config`
    6. Import `TelegramServiceError`, `StateError`, `TelegramAuthError` from `errors`
    7. Import `APP_PATHS` from `paths`

    Note: The `from mko_telebot.core import CONFIG` import is no longer needed
    (it was only used for the logging dictConfig call which was removed in Wave 1).
    The remaining `from mko_telebot.core import utils` import must be kept.
  </description>
  <targets>
    <file path="src/mko_telebot/core/task.py">
      <target type="import" name="from mko_telebot.core import CONFIG">
        <action>remove</action>
      </target>
      <target type="import" name="from mko_telebot.core import PATHS">
        <action>remove</action>
      </target>
      <target type="import" name="from mko_telebot.core.paths import APP_PATHS">
        <action>add</action>
      </target>
      <target type="import" name="from mko_telebot.core.errors import TelegramAuthError, TelegramServiceError, StateError">
        <action>add</action>
      </target>
      <target type="import" name="from mko_telebot.core.chats_config import ChannelConfig">
        <action>add</action>
      </target>
      <target type="variable" name="state_dir = Path(PATHS.state_dir)">
        <action>replace">state_dir = Path(APP_PATHS.state_dir)</action>
      </target>
      <target type="code_block" name="Task.__init__ signature">
        <action>update">def __init__(self, config: ChannelConfig)</action>
      </target>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/task.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/task.py` — no errors</step>
    <step>Verify Task.__init__ accepts ChannelConfig instead of individual params</step>
    <step>Verify `except Exception` is replaced with specific Telethon/State error types</step>
    <step>Verify `state_dir` references `APP_PATHS.state_dir`</step>
  </verification>
</task>

---

## Wave 3 Validation

1. Run `uv run ruff check src/mko_telebot/` — no errors
2. Run `uv run mypy src/mko_telebot/` — no errors
3. Run `uv run pytest tests/` — all existing tests pass (parser tests import search_match directly from core/parser.py)
4. Verify `config_reader.py` has no module-level CONFIG or PATHS singletons
5. Verify `monitor.py` is unchanged by this wave (it will be refactored in Wave 4)
6. Verify all custom exceptions are properly imported and used in task.py