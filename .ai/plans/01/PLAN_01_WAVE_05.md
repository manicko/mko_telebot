---
wave: 5
title: "Tests & Documentation"
depends_on:
  - .ai/plans/01/PLAN_01_WAVE_04.md
files_modified:
  - tests/test_parser.py
  - tests/test_config_reader.py
  - tests/test_cli.py
  - tests/test_errors.py
  - tests/conftest.py
  - README.md
  - docs/99-reference/cli-reference.md
  - docs/11-guides/configuration.md
  - src/mko_telebot/core/example.*
  - src/mko_telebot/core/examples.*
autonomous: false
note: >
  Test tasks depend on the full refactored codebase. Documentation can be drafted
  alongside Wave 4 but must be completed after all code changes.
---

# Wave 5 — Tests & Documentation

Expand test coverage for all new modules. Update documentation with CLI reference and
configuration guide. Clean up reference example files.

## must_haves

- `tests/test_errors.py` exists — tests exception hierarchy instantiation and inheritance
- `tests/test_config_reader.py` exists — tests TelepostConfigReader with mock files
- `tests/test_cli.py` exists — tests CLI command invocation (init, validate, config, version)
- All existing parser tests still pass
- `README.md` updated with CLI commands reference and installation instructions
- `docs/99-reference/cli-reference.md` exists — CLI command reference
- `docs/11-guides/configuration.md` exists — configuration guide with all fields
- Example files (`example.*`, `examples.*`) in core/ are cleaned up

---

## Task 5.1 — Add error hierarchy tests

<task id="T05_01_test_errors" wave="5" depends_on="[T01_02_create_errors]" risk="low">
  <description>
    Create `tests/test_errors.py` with tests for the new exception hierarchy.

    Test cases:
    1. `MkoTelebotError` is a subclass of `Exception`
    2. `ConfigError` is a subclass of `MkoTelebotError`
    3. `TelegramAuthError` is a subclass of `MkoTelebotError`
    4. `TelegramServiceError` is a subclass of `MkoTelebotError`
    5. `StateError` is a subclass of `MkoTelebotError`
    6. `ConfigError` accepts an optional `path` parameter
    7. All exceptions can be raised and caught as `MkoTelebotError`
    8. Exception messages are preserved correctly
  </description>
  <targets>
    <file path="tests/test_errors.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="function" name="test_mko_telebot_error_inheritance" />
        <anchor type="function" name="test_config_error_path" />
        <anchor type="function" name="test_exception_polymorphism" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run pytest tests/test_errors.py` — all tests pass</step>
    <step>Run `uv run ruff check tests/test_errors.py` — no errors</step>
  </verification>
</task>

---

## Task 5.2 — Add config reader tests

<task id="T05_02_test_config_reader" wave="5" depends_on="[T03_01_config_reader, T03_02_core_init]" risk="medium">
  <description>
    Create `tests/test_config_reader.py` with tests for the new `TelepostConfigReader`.

    Use `tmp_path` fixture (pytest built-in) to create temporary config directories.

    Test cases:
    1. `from_user_dir()` creates reader with default paths
    2. `load()` raises `ConfigError` when config file missing
    3. `load()` returns `TelepostSettings` with valid files
    4. `validate_files()` returns errors for missing files
    5. `validate_files()` returns empty list for valid setup
    6. `load_logging_config()` loads and resolves paths correctly
    7. Merged config.yaml + secrets.yaml correctly overlays TELETHON_API section
    8. `ConfigError` includes path in error message when path provided

    Create temp YAML fixtures:
    - `config.yaml` with MONITORING section
    - `secrets.yaml` with TELETHON_API section
    - `log_config.yaml` with basic logging config

    Import path:
    ```python
    from mko_telebot.core.config_reader import TelepostConfigReader
    from mko_telebot.core.errors import ConfigError
    from mko_telebot.core.paths import APP_PATHS
    ```
  </description>
  <targets>
    <file path="tests/test_config_reader.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="function" name="test_from_user_dir" />
        <anchor type="function" name="test_load_missing_config" />
        <anchor type="function" name="test_load_valid_config" />
        <anchor type="function" name="test_validate_files" />
        <anchor type="function" name="test_load_logging_config" />
        <anchor type="function" name="test_merged_config" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run pytest tests/test_config_reader.py` — all tests pass</step>
    <step>Run `uv run ruff check tests/test_config_reader.py` — no errors</step>
    <step>Run `uv run mypy tests/test_config_reader.py` — no errors</step>
  </verification>
</task>

---

## Task 5.3 — Add CLI tests

<task id="T05_03_test_cli" wave="5" depends_on="[T04_03_cli_entry]" risk="medium">
  <description>
    Create `tests/test_cli.py` with tests for the CLI commands.

    Use `typer.testing.CliRunner` for invoking commands.

    Test cases:
    1. `--help` shows all five commands (init, validate, run, config, version)
    2. `version` shows version string
    3. `config` shows table with paths
    4. `validate` exits with code 1 when config missing
    5. `init` creates config directory with template files (use `--force` + tmp dir)

    Import:
    ```python
    from typer.testing import CliRunner
    from mko_telebot.cli import app
    ```
  </description>
  <targets>
    <file path="tests/test_cli.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="function" name="test_cli_help" />
        <anchor type="function" name="test_cli_version" />
        <anchor type="function" name="test_cli_config" />
        <anchor type="function" name="test_cli_validate_missing" />
        <anchor type="function" name="test_cli_init" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run pytest tests/test_cli.py` — all tests pass</step>
    <step>Run `uv run ruff check tests/test_cli.py` — no errors</step>
  </verification>
</task>

---

## Task 5.4 — Update existing parser tests

<task id="T05_04_update_parser_tests" wave="5" depends_on="[T01_03_parser_no_side_effects]" risk="low">
  <description>
    Verify that the existing `tests/test_parser.py` and `tests/conftest.py` still pass
    after the import-time side effect removal in parser.py.

    Update `conftest.py` if needed:
    The current conftest uses `from src.mko_telebot.core.parser import search_match`.
    This should still work since the module no longer has import-time side effects.
    No code changes should be needed — this is a verification-only task.

    If any test fails due to the refactoring, fix the test (but DO NOT change parser.py).
    Production code is king — only fix tests.
  </description>
  <targets>
    <file path="tests/conftest.py">
      <action>verify</action>
    </file>
    <file path="tests/test_parser.py">
      <action>verify</action>
    </file>
  </targets>
  <verification>
    <step>Run `uv run pytest tests/test_parser.py` — all tests pass (including slow/fuzz)</step>
  </verification>
</task>

---

## Task 5.5 — Clean up example files

<task id="T05_05_cleanup_examples" wave="5" depends_on="[T04_03_cli_entry]" risk="low">
  <description>
    Remove the reference example files from `src/mko_telebot/core/` that were pre-existing
    documentation from the mko_telepost project. These are no longer needed as their patterns
    have been implemented in the new code.

    Files to remove:
    - `src/mko_telebot/core/example.errors.py` (replaced by core/errors.py)
    - `src/mko_telebot/core/example.models.py` (replaced by core/models.py + core/telethon_models.py + core/chats_config.py)
    - `src/mko_telebot/core/example.paths.py` (replaced by core/paths.py)
    - `src/mko_telebot/core/example.init_service.py` (pattern absorbed into cli.py init command)
    - `src/mko_telebot/core/examples.config_reader.py` (replaced by core/config_reader.py)
    - `src/mko_telebot/core/examples.task.py` (replaced by core/task.py)
    - `src/mko_telebot/core/examples.telethon_models.py` (replaced by core/telethon_models.py)
    - `src/mko_telebot/core/examples.types.py` (not needed — type aliases in telethon_models.py)
    - `src/mko_telebot/example.app.py` (replaced by cli.py)

    Use `git rm` or `Remove-Item` to delete these files.
  </description>
  <targets>
    <file path="src/mko_telebot/core/example.errors.py">
      <action>delete</action>
    </file>
    <file path="src/mko_telebot/core/example.models.py">
      <action>delete</action>
    </file>
    <file path="src/mko_telebot/core/example.paths.py">
      <action>delete</action>
    </file>
    <file path="src/mko_telebot/core/example.init_service.py">
      <action>delete</action>
    </file>
    <file path="src/mko_telebot/core/examples.config_reader.py">
      <action>delete</action>
    </file>
    <file path="src/mko_telebot/core/examples.task.py">
      <action>delete</action>
    </file>
    <file path="src/mko_telebot/core/examples.telethon_models.py">
      <action>delete</action>
    </file>
    <file path="src/mko_telebot/core/examples.types.py">
      <action>delete</action>
    </file>
    <file path="src/mko_telebot/example.app.py">
      <action>delete</action>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/` — no errors after deletion</step>
    <step>Verify all 9 example files are deleted</step>
    <step>Verify no imports reference deleted files</step>
  </verification>
</task>

---

## Task 5.6 — Update README

<task id="T05_06_update_readme" wave="5" depends_on="[T04_03_cli_entry]" risk="low">
  <description>
    Update `README.md` with:
    1. Updated installation instructions (uv-based)
    2. CLI commands reference (init, validate, run, config, version)
    3. Configuration section with file locations
    4. Keyword grammar section (preserve the existing content)
    5. Troubleshooting section

    Preserve all existing content about keyword matching, forwarding, state persistence.
    Add new sections after existing content:

    ```markdown
    ## Installation

    ```bash
    git clone https://github.com/<your-repo>/mko_telebot.git
    cd mko_telebot
    uv sync
    ```

    ## CLI Usage

    mko-telebot init        # Initialize user configuration
    mko-telebot validate    # Validate configuration
    mko-telebot run         # Start monitoring
    mko-telebot config      # Show configuration paths
    mko-telebot version     # Show version

    ### Options
    -c, --config PATH       Path to custom configuration file
    -f, --force             Overwrite existing files
    -v, --verbose           Verbose output
    ```
  </description>
  <targets>
    <file path="README.md">
      <action>update</action>
      <semantic_anchors>
        <anchor type="section" name="## Key Features" />
        <anchor type="section" name="## ⚙️ Setup Instructions" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Verify README.md has CLI commands section after existing content</step>
    <step>Verify all five CLI commands are documented</step>
    <step>Verify keyword grammar section is preserved</step>
  </verification>
</task>

---

## Task 5.7 — Create CLI reference documentation

<task id="T05_07_docs_cli_reference" wave="5" depends_on="[T04_03_cli_entry]" risk="low">
  <description>
    Create `docs/99-reference/cli-reference.md` with detailed CLI command reference.

    Include:
    - Command descriptions
    - All options and flags
    - Exit codes
    - Examples
    - Configuration file locations
  </description>
  <targets>
    <file path="docs/99-reference/cli-reference.md">
      <action>create</action>
    </file>
  </targets>
  <verification>
    <step>Verify cli-reference.md exists with complete command reference</step>
  </verification>
</task>

---

## Task 5.8 — Create configuration guide

<task id="T05_08_docs_config_guide" wave="5" depends_on="[T03_01_config_reader]" risk="low">
  <description>
    Create `docs/11-guides/configuration.md` with configuration file reference.

    Include:
    - File locations (config.yaml, secrets.yaml, log_config.yaml)
    - config.yaml fields: MONITORING section with all channel options
    - secrets.yaml fields: TELETHON_API section with all telethon options
    - log_config.yaml fields: logging configuration structure
    - Example config files
    - Path resolution rules
    - Secrets handling (SecretStr)
  </description>
  <targets>
    <file path="docs/11-guides/configuration.md">
      <action>create</action>
    </file>
  </targets>
  <verification>
    <step>Verify configuration.md exists with all config file documentation</step>
  </verification>
</task>

---

## Wave 5 Validation

1. Run `uv run pytest tests/` — all tests pass
2. Run `uv run ruff check .` — no errors
3. Run `uv run mypy src/mko_telebot/` — no errors
4. Verify `tests/test_errors.py`, `tests/test_config_reader.py`, `tests/test_cli.py` exist
5. Verify all 9 example files are removed
6. Verify README.md has CLI commands section
7. Verify `docs/99-reference/cli-reference.md` and `docs/11-guides/configuration.md` exist