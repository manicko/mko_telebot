---
wave: 1
title: "Foundation — Dependencies & Error Hierarchy"
depends_on: []
files_modified:
  - pyproject.toml
  - src/mko_telebot/core/errors.py
  - src/mko_telebot/core/parser.py
  - src/mko_telebot/core/task.py
autonomous: true
---

# Wave 1 — Foundation

Add new dependencies and create the exception hierarchy. Fix import-time side effects in parser.py and task.py.

## must_haves

- `pyproject.toml` has `typer>=0.12` and `rich>=13` in `[project] dependencies`
- `core/errors.py` exists with `MkoTelebotError` base class and `ConfigError`, `TelegramAuthError`, `TelegramServiceError`, `StateError` subclasses
- `core/parser.py` no longer calls `logging.config.dictConfig()` at import time
- `core/task.py` no longer calls `logging.config.dictConfig()` at import time
- All existing tests pass

---

## Task 1.1 — Add typer and rich dependencies

<task id="T01_01_add_deps" wave="1" depends_on="[]" risk="low">
  <description>
    Add `typer>=0.12` and `rich>=13` to the `[project] dependencies` list in `pyproject.toml`.
    These are required for the CLI entry point and user-facing console output.
  </description>
  <targets>
    <file path="pyproject.toml">
      <target type="config_key" name="project.dependencies">
        <action>append</action>
        <value>"typer>=0.12"</value>
        <value>"rich>=13"</value>
      </target>
    </file>
  </targets>
  <verification>
    <step>Run `uv pip list` and confirm typer and rich are available</step>
    <step>Run `uv run ruff check pyproject.toml` — no errors</step>
  </verification>
</task>

---

## Task 1.2 — Create exception hierarchy

<task id="T01_02_create_errors" wave="1" depends_on="[]" risk="low">
  <description>
    Create `src/mko_telebot/core/errors.py` with the following exception hierarchy:

    - `MkoTelebotError(Exception)` — base exception for all project errors
    - `ConfigError(MkoTelebotError)` — configuration loading/validation failures
    - `TelegramAuthError(MkoTelebotError)` — Telegram authentication/connection failures
    - `TelegramServiceError(MkoTelebotError)` — message forwarding/sending failures
    - `StateError(MkoTelebotError)` — state file persistence failures

    Each class must have a docstring explaining when it is raised.
    `ConfigError` should accept an optional `path: Path | None` parameter.
  </description>
  <targets>
    <file path="src/mko_telebot/core/errors.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="module" name="mko_telebot.core.errors" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/errors.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/errors.py` — no errors</step>
    <step>Verify all five exception classes exist with proper inheritance</step>
  </verification>
</task>

---

## Task 1.3 — Remove import-time side effects from parser.py

<task id="T01_03_parser_no_side_effects" wave="1" depends_on="[]" risk="medium">
  <description>
    Remove the import-time side effect in `src/mko_telebot/core/parser.py`:

    The current code at module level calls:
    ```python
    logging.config.dictConfig(CONFIG.LOGGING.model_dump())
    ```

    This must be removed. The `logger = logging.getLogger(__name__)` line must stay.
    The `from mko_telebot.core import CONFIG` import must be removed (it was only used for the logging setup).

    The `search_match` function already catches all exceptions and logs them — logging is already initialized
    by the time the monitor calls `search_match`. If logging is not initialized, the root logger handles it.
  </description>
  <targets>
    <file path="src/mko_telebot/core/parser.py">
      <target type="import" name="logging.config.dictConfig">
        <action>remove</action>
      </target>
      <target type="import" name="from mko_telebot.core import CONFIG">
        <action>remove</action>
      </target>
      <target type="import" name="import logging.config">
        <action>remove</action>
      </target>
      <target type="code_line" name="logging.config.dictConfig(CONFIG.LOGGING.model_dump())">
        <action>remove</action>
      </target>
      <target type="import" name="import logging">
        <action>keep</action>
        <note>logger = logging.getLogger(__name__) must stay</note>
      </target>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/parser.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/parser.py` — no errors</step>
    <step>Run `uv run pytest tests/test_parser.py` — all tests pass</step>
    <step>Verify `import logging.config` is removed from parser.py</step>
    <step>Verify `from mko_telebot.core import CONFIG` is removed from parser.py</step>
    <step>Verify `logger = logging.getLogger(__name__)` remains</step>
  </verification>
</task>

---

## Task 1.4 — Remove import-time side effects from task.py

<task id="T01_04_task_no_side_effects" wave="1" depends_on="[]" risk="medium">
  <description>
    Remove the import-time side effect in `src/mko_telebot/core/task.py`:

    The current code at module level:
    ```python
    logging.config.dictConfig(CONFIG.LOGGING.model_dump())
    ```

    This must be removed. The `logger = logging.getLogger(__name__)` line must stay.
    The `from mko_telebot.core import CONFIG` import must be kept (it's needed for `PATHS`).
    The `from mko_telebot.core import PATHS` import must be kept (it's needed for `state_dir`).

    Remove `import logging.config` since it's no longer needed at module level.
    The `state_dir = Path(PATHS.state_dir)` line must stay (it's used at module level for the class).
  </description>
  <targets>
    <file path="src/mko_telebot/core/task.py">
      <target type="import" name="import logging.config">
        <action>remove</action>
      </target>
      <target type="code_line" name="logging.config.dictConfig(CONFIG.LOGGING.model_dump())">
        <action>remove</action>
      </target>
      <note>Keep: import logging, from mko_telebot.core import CONFIG, PATHS, utils, logger = logging.getLogger(__name__)</note>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/task.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/task.py` — no errors</step>
    <step>Verify `import logging.config` is removed from task.py</step>
    <step>Verify `logger = logging.getLogger(__name__)` remains</step>
  </verification>
</task>

---

## Wave 1 Validation

1. Run `uv run ruff check src/mko_telebot/core/` — no errors
2. Run `uv run mypy src/mko_telebot/core/` — no errors
3. Run `uv run pytest tests/` — all tests pass
4. Confirm `pyproject.toml` has `typer>=0.12` and `rich>=13`
5. Confirm `core/errors.py` exists with all five exception classes
6. Confirm no module-level `logging.config.dictConfig()` calls remain in `parser.py` or `task.py`