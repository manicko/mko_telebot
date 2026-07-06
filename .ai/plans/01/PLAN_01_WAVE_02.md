---
wave: 2
title: "Infrastructure — Path Management & Pydantic Models"
depends_on:
  - .ai/plans/01/PLAN_01_WAVE_01.md
files_modified:
  - src/mko_telebot/core/__init__.py
  - src/mko_telebot/core/paths.py
  - src/mko_telebot/core/models.py
  - src/mko_telebot/core/telethon_models.py
  - src/mko_telebot/core/chats_config.py
autonomous: true
---

# Wave 2 — Infrastructure

Create the path management module and typed Pydantic models for configuration. These modules
have zero runtime import-time side effects — they define types and constants only.

## must_haves

- `core/paths.py` exists with `AppPaths` model and `APP_PATHS` singleton — root_dir, user_dir, state_dir, session_dir, settings dirs, config file paths
- `core/telethon_models.py` exists with `ClientConfig` and `TelethonConfig` — typed fields, `SecretStr` for secrets, `ConfigDict(extra="forbid")`
- `core/chats_config.py` exists with `ChannelConfig`, `ChannelDefaults`, `ChatsConfig` — typed per-channel config, defaults merging
- `core/models.py` exists with `TelepostSettings` root model — combines telethon, monitoring, logging sections
- `core/__init__.py` exports new symbols

---

## Task 2.1 — Create path management module

<task id="T02_01_paths_module" wave="2" depends_on="[T01_02_create_errors]" risk="low">
  <description>
    Create `src/mko_telebot/core/paths.py` with a clean path management system.

    Extract path logic from the current `WorkingPaths` in `config_reader.py` into a dedicated module.

    The module must provide:

    1. `AppPaths(BaseModel)` — path management model:
       - `root_dir: Path` — package root (src/mko_telebot/)
       - `user_dir: Path` — user config dir via `platformdirs.user_config_dir("mko_telebot")`
       - Properties:
         - `app_settings_dir: Path` → root_dir / "settings"
         - `user_settings_dir: Path` → user_dir / "settings"
         - `state_dir: Path` → user_settings_dir / "state"
         - `session_dir: Path` → user_settings_dir / "sessions"
         - `log_dir: Path` → user_dir / "logs"
         - `config_file: Path` → user_settings_dir / "config.yaml"
         - `secrets_file: Path` → user_settings_dir / "secrets.yaml"
         - `log_config_file: Path` → user_settings_dir / "log_config.yaml"

    2. `APP_PATHS: AppPaths` — module-level singleton (safe: no I/O, pure path computation)

    3. `PathResolver` — utility class (matching the pattern from example.paths.py):
       - `__init__(self, base_dir: Path)`
       - `resolve(self, path: Path | str) -> Path` — resolves relative against base_dir
       - `ensure_dir(path: Path) -> Path` — static, mkdir parents
       - `ensure_file_parent(path: Path) -> Path` — static, mkdir parent

    Use `ConfigDict(extra="forbid")`, `model_config = ConfigDict(extra="forbid")`.

    Import: `from pathlib import Path; from platformdirs import user_config_dir; from pydantic import BaseModel, ConfigDict`
  </description>
  <targets>
    <file path="src/mko_telebot/core/paths.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="class" name="AppPaths" />
        <anchor type="variable" name="APP_PATHS" />
        <anchor type="class" name="PathResolver" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/paths.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/paths.py` — no errors</step>
    <step>Verify `APP_PATHS` singleton exists and is a fully initialized `AppPaths` instance</step>
    <step>Verify all six property paths resolve correctly (app_settings_dir, user_settings_dir, state_dir, session_dir, log_dir, config_file, secrets_file, log_config_file)</step>
  </verification>
</task>

---

## Task 2.2 — Create Telethon config models

<task id="T02_02_telethon_models" wave="2" depends_on="[T01_02_create_errors]" risk="low">
  <description>
    Create `src/mko_telebot/core/telethon_models.py` with typed Pydantic models for Telethon client configuration.

    Follow the exact pattern from `core/examples.telethon_models.py` (in the mko_telebot project, this reference implementation serves as the blueprint).

    Models:
    1. `ClientConfig(BaseModel)`:
       - `api_id: int = Field(..., gt=0)`
       - `api_hash: SecretStr = Field(..., min_length=1, max_length=64)`
       - `session: str = Field(default="mko_telebot")`
       - `app_version: str | None = None`
       - `device_model: str | None = None`
       - `system_version: str | None = None`
       - `system_lang_code: str | None = None`
       - `lang_code: str | None = None`
       - `model_config = ConfigDict(extra="forbid")`
       - Validator: reject placeholder values (YOUR_*, 12345)

    2. `TelethonConfig(BaseModel)`:
       - `is_user: bool = True`
       - `phone_or_token: SecretStr`
       - `max_retries: int = Field(default=3, ge=1, le=20)`
       - `client: ClientConfig`
       - `model_config = ConfigDict(extra="forbid")`
       - Validator: reject placeholder phone_or_token

    Export both classes in `__all__`.
  </description>
  <targets>
    <file path="src/mko_telebot/core/telethon_models.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="class" name="ClientConfig" />
        <anchor type="class" name="TelethonConfig" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/telethon_models.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/telethon_models.py` — no errors</step>
    <step>Verify `ClientConfig` has all 8 fields with proper types</step>
    <step>Verify `TelethonConfig` has `is_user`, `phone_or_token` (SecretStr), `max_retries`, `client`</step>
    <step>Verify `ConfigDict(extra="forbid")` on both models</step>
  </verification>
</task>

---

## Task 2.3 — Create channels config models

<task id="T02_03_chats_config" wave="2" depends_on="[T01_02_create_errors]" risk="low">
  <description>
    Create `src/mko_telebot/core/chats_config.py` with typed models for per-channel monitoring configuration.

    The current `monitor.py` uses `dict[str, Any]` for channels and `dict[str, Any]` for per-channel settings.
    Replace this with typed Pydantic models.

    Models:

    1. `LogLevel(StrEnum)`:
       - Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
       - Uses `from enum import StrEnum`

    2. `ChannelConfig(BaseModel)`:
       - `name: str` — channel identifier (@username or t.me/...)
       - `forward_to: list[str] = Field(default_factory=list)` — target entities
       - `keywords: list[str] = Field(default_factory=list)` — keyword patterns
       - `scan_interval: int = Field(default=420, ge=60)`
       - `history_limit: int = Field(default=50, ge=1)`
       - `history_days: int | None = None`
       - `overlap: int = Field(default=5, ge=1)`
       - `model_config = ConfigDict(extra="forbid")`

    3. `ChatsConfig(BaseModel)`:
       - `defaults: ChannelDefaults` — embedded defaults model
       - `channels: dict[str, ChannelConfig]` — keyed by channel name
       - `channels_delay: int = Field(default=30, ge=1, description="Delay between channel scans in seconds")`
       - `stagger_start_seconds: int = Field(default=5, ge=0)`
       - `model_config = ConfigDict(extra="forbid")`
       - `@model_validator(mode="after")` that: removes "DEFAULTS" if present in channels dict (it's handled separately)

    4. `ChannelDefaults(BaseModel)`:
       - Same fields as `ChannelConfig` except `name` is not needed
       - `forward_to: list[str] = Field(default_factory=list)`
       - `keywords: list[str] = Field(default_factory=list)`
       - `scan_interval: int = Field(default=420, ge=60)`
       - `history_limit: int = Field(default=50, ge=1)`
       - `history_days: int | None = None`
       - `overlap: int = Field(default=5, ge=1)`
       - `model_config = ConfigDict(extra="forbid")`

  </description>
  <targets>
    <file path="src/mko_telebot/core/chats_config.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="class" name="LogLevel" />
        <anchor type="class" name="ChannelConfig" />
        <anchor type="class" name="ChannelDefaults" />
        <anchor type="class" name="ChatsConfig" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/chats_config.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/chats_config.py` — no errors</step>
    <step>Verify `ChatsConfig` model_validator strips "DEFAULTS" from channels dict</step>
    <step>Verify `ChannelConfig` has all 7 configuration fields</step>
  </verification>
</task>

---

## Task 2.4 — Create root settings model

<task id="T02_04_root_model" wave="2" depends_on="[T02_02_telethon_models, T02_03_chats_config]" risk="low">
  <description>
    Create `src/mko_telebot/core/models.py` with the root `TelepostSettings` Pydantic model.

    This model represents the complete validated application configuration:

    ```python
    class TelepostSettings(BaseModel):
        model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)
        telethon: TelethonConfig
        monitoring: ChatsConfig
    ```

    **IMPORTANT — Field aliases for backward compatibility:**
    Existing config files use uppercase YAML keys (`TELETHON_API`, `MONITORING`).
    Add `validation_alias` so Pydantic accepts both old and new key names during `model_validate()`:
    ```python
    class TelepostSettings(BaseModel):
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            str_strip_whitespace=True,
            populate_by_name=True,
        )
        telethon: TelethonConfig = Field(validation_alias="TELETHON_API")
        monitoring: ChatsConfig = Field(validation_alias="MONITORING")
    ```
    This allows `model_validate({"TELETHON_API": ..., "MONITORING": ...})` to match
    the new field names while reading existing config files without modification.

    Import `TelethonConfig` from `mko_telebot.core.telethon_models`.
    Import `ChatsConfig` from `mko_telebot.core.chats_config`.

    Export both in `__all__`.
  </description>
  <targets>
    <file path="src/mko_telebot/core/models.py">
      <action>create</action>
      <semantic_anchors>
        <anchor type="class" name="TelepostSettings" />
        <anchor type="import" module="mko_telebot.core.telethon_models" name="TelethonConfig" />
        <anchor type="import" module="mko_telebot.core.chats_config" name="ChatsConfig" />
      </semantic_anchors>
    </file>
  </targets>
  <verification>
    <step>Run `uv run ruff check src/mko_telebot/core/models.py` — no errors</step>
    <step>Run `uv run mypy src/mko_telebot/core/models.py` — no errors</step>
    <step>Verify TelepostSettings has telethon and monitoring fields with correct types</step>
  </verification>
</task>

---

## Wave 2 Validation

1. Run `uv run ruff check src/mko_telebot/core/` — no errors
2. Run `uv run mypy src/mko_telebot/core/` — no errors
3. Verify all four new files exist (paths.py, telethon_models.py, chats_config.py, models.py)
4. Verify no module-level I/O or logging init in any new file