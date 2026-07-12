---
id: configuration-guide
domain: guide
tags:
  - config
  - yaml
  - settings
  - telethon
  - monitoring
related:
  - cli-reference
---

# Configuration Guide

**Applies to:** `mko-telebot` v0.1+

This document describes all configuration files used by mko-telebot: their locations, schema, field descriptions, path resolution rules, and how sensitive values are handled.

---

## Table of Contents

1. [File Locations & Path Resolution](#file-locations--path-resolution)
2. [`config.yaml` — Monitoring Configuration](#configyaml--monitoring-configuration)
3. [Keyword Pattern Syntax](#keyword-pattern-syntax)
4. [`telethon_config.yaml` — Telethon API Credentials](#telethon_configyaml--telethon-api-credentials)
5. [Proxy Configuration](#proxy-configuration)
6. [`log_config.yaml` — Logging Configuration](#log_configyaml--logging-configuration)
7. [SecretStr Handling](#secretstr-handling)
8. [Validation Rules](#validation-rules)
9. [Example Files](#example-files)

---

## File Locations & Path Resolution

### Default Package Settings

The application ships with default config files inside the package at:

```
src/mko_telebot/settings/
├── config.yaml
├── telethon_config.yaml
└── log_config.yaml
```

These are templates. **Do not edit them in-place** — they are overwritten on package upgrades.

### User Config Directory

User-specific config files live in the platform-specific user config directory, resolved via [`platformdirs`](https://pypi.org/project/platformdirs/):

| Platform | Path |
|----------|------|
| Linux    | `~/.config/mko_telebot/settings/` |
| macOS    | `~/Library/Application Support/mko_telebot/settings/` |
| Windows  | `C:\Users\<USER>\AppData\Local\mko_telebot\mko_telebot\settings\` |

The application creates the following subdirectory structure:

```
<mko_telebot_user_dir>/
├── settings/
│   ├── config.yaml          ← User overrides for monitoring
│   ├── telethon_config.yaml ← Telethon credentials (sensitive)
│   ├── log_config.yaml      ← Logging configuration
│   ├── state/               ← Persistent application state
│   └── sessions/            ← Telethon session files
└── logs/                    ← Log output files
```

### Path Resolution Rules

The `TelepostConfigReader` resolves paths in the following order:

1. **Home-directory expansion:** `~` / `~user` in paths is expanded first via `Path.expanduser()`.
2. **Absolute paths:** If the path is already absolute (starts with `/` or drive letter), it is used as-is.
3. **Relative paths:** Resolved against the **user settings directory** (`~/.config/mko_telebot/settings/` by default).
4. **Log file paths:** Relative `filename` values in `log_config.yaml` handlers are resolved against the **log directory** (`~/.config/mko_telebot/logs/`).

If a required file is missing, `ConfigError` is raised with the file path in the error message.

### Automatic Config Selection

The `TelepostConfigReader.from_user_dir()` factory method automatically sets up paths pointing to the user config directory:

| Property | Default Path |
|----------|-------------|
| `config_path` | `<user_dir>/config.yaml` |
| `telethon_config_path` | `<user_dir>/telethon_config.yaml` |
| `log_config_path` | `<user_dir>/log_config.yaml` |

---

## `config.yaml` — Monitoring Configuration

This file defines the **CHANNELS** section of the application — which channels to watch, how often to scan, and how to filter/forward messages.

### Top-Level Structure

```yaml
CHANNELS:
  channels_delay: <int>
  stagger_start_seconds: <int>
  defaults:
    scan_interval: <int>
    history_limit: <int>
    history_days: <int | null>
    overlap: <int>
    forward_to: <list[str]>
    keywords: <list[str]>
  channels:
    <channel_name>:
      ...
```

The root key `CHANNELS` maps to `ChannelsConfig` in the Pydantic model. Note that `defaults` is a top-level key under `CHANNELS` — it is **not** nested under `channels`. Channel-specific entries go under the `channels` key.

### Defaults Configuration

The `defaults` field provides fallback values for all channels. Each channel inherits these values unless it explicitly overrides a field. The key is `defaults` (lowercase) at the `CHANNELS` level.

If you use the uppercase `DEFAULTS` key inside `channels`, it is automatically removed during validation (handled by the `strip_defaults_from_channels` model validator), but the recommended approach is to use the lowercase `defaults` key at the top level for clarity.

### Field Reference

#### `ChannelsConfig` (top-level monitoring)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `channels_delay` | `int` | `30` | Delay in seconds between successive channel scans. Minimum: 1. |
| `stagger_start_seconds` | `int` | `5` | Stagger offset in seconds to distribute initial scan start times across channels. |
| `channels` | `dict` | _required_ | Map of channel name → `ChannelConfig`. See below. |
| `defaults` | `ChannelDefaults` | `{}` | Default settings inherited by every channel. Configurable via `defaults` key (see ChannelDefaults). |

#### `ChannelDefaults`

Applied to every channel that does not override a given field. Configurable as a top-level key under `CHANNELS`.

| Field | Type | Default | Valid Range | Description |
|-------|------|---------|-------------|-------------|
| `scan_interval` | `int` | `420` | ≥ 60 | Interval in seconds between scanning the channel for new messages. |
| `history_limit` | `int` | `50` | ≥ 1 | Maximum number of historical messages to fetch on first scan. |
| `history_days` | `int` or `null` | `null` | any positive int | Number of days of historical messages to fetch. `null` means no day-based limit. When set, messages older than this cutoff are excluded from scanning. |
| `overlap` | `int` | `5` | ≥ 1 | Number of overlapping messages between consecutive scans — avoids gaps from messages arriving during a scan. |
| `forward_to` | `list[str]` | `[]` | — | List of target entities (channel @username, chat ID, or t.me link) to forward matched messages to. |
| `keywords` | `list[str]` | `[]` | — | Keyword patterns for filtering messages. Only messages matching at least one keyword are forwarded. An empty list forwards all messages. |

#### `ChannelConfig` (per-channel entry)

Each key inside `channels` defines a monitored channel. All fields from `ChannelDefaults` apply here, plus:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | _required_ | Channel identifier — can be a Telegram @username, a `t.me/...` link, or a numeric chat ID. This field is typically inferred from the dict key, but can be set explicitly for custom display names. Path traversal characters (`/`, `\`, `..`) are rejected for security. |

All other fields (`scan_interval`, `history_limit`, `history_days`, `overlap`, `forward_to`, `keywords`) default to the values set in `defaults` if not explicitly overridden.

---

## Keyword Pattern Syntax

The keyword filtering system supports a flexible pattern syntax for matching messages. Keywords are evaluated using the `PatternParser` engine.

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `|` | OR — matches either side | `(barcelona \| барселона)` matches "barcelona" OR "барселона" |
| `-` | Exclusion — excludes matches | `-rent*` excludes messages containing words starting with "rent" |
| `()` | Grouping — groups subexpressions | `(bike* \| велосипед)` groups OR alternatives |
| `*` | Wildcard — matches any non-space characters | `bike*` matches "bike", "biker", "bicycle" but not "bike rental" |

### Pattern Types

| Pattern Type | Behavior | Example |
|--------------|----------|---------|
| Exact match | Whole word match with word boundaries | `alert` matches "alert" but not "alerts" |
| Wildcard | `*` matches non-space characters | `bike*` matches "bike", "biker", "bicycle" |
| Sequence (implicit) | Space-separated terms act as AND | `barcelona bicycle` requires both terms present |
| OR expression | Pipe-separated alternatives act as OR | `barcelona\|барселона` matches either |

### Evaluation Semantics

1. **Exclusions first**: Any exclusion pattern matching the text causes the whole expression to fail (returns `False`).
2. **Inclusions next**: All inclusion patterns must have their required patterns found in the text (unordered).
3. **Empty expression**: An empty keyword string or `null` returns `False` (no match).

### Example Patterns

```text
(barcelona | барселона) (bicycle | bike | велосипед) -rent* -repair* -service*
```

This matches messages containing "Barcelona" AND "bicycle" (in English or Russian), but excludes posts about rentals, repairs, or services.

---

## `telethon_config.yaml` — Telethon API Credentials

This file holds the **TELETHON_API** section — credentials needed to connect to Telegram via the Telethon library.

### Top-Level Structure

```yaml
TELETHON_API:
  is_user: <bool>
  phone_or_token: "<str>"
  max_retries: <int>
  client:
    session: "<str>"
    api_id: <int>
    api_hash: "<str>"
    app_version: "<str>"
    device_model: "<str>"
    system_version: "<str>"
    system_lang_code: "<str>"
    lang_code: "<str>"
    proxy:
      proxy_type: "<str>"
      addr: "<str>"
      port: <int>
      username: "<str>"
      password: "<str>"
      rdns: <bool>
```

The root key `TELETHON_API` maps to `TelethonConfig` in the Pydantic model.

### Field Reference

#### `TelethonConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `is_user` | `bool` | `true` | `true` = authenticate as a user account (phone-based auth). `false` = authenticate as a bot (bot token auth). |
| `phone_or_token` | `str` (SecretStr) | _required_ | Phone number with country code (e.g. `+79123456789`) for user accounts, or bot token (e.g. `123456:ABC-DEF1234...`) for bots. Stored as a SecretStr — see [SecretStr Handling](#secretstr-handling). Minimum length: 5 characters. |
| `max_retries` | `int` | `5` | Maximum number of retry attempts when sending messages fails. Valid range: 1–20. Implements exponential backoff with jitter. |
| `client` | `ClientConfig` | _required_ | Telethon client configuration (see below). |

#### `ClientConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session` | `str` | `"first_session"` | Session name or path. Determines the session file name used by Telethon to persist authentication. Path traversal characters (`/`, `\`, `..`) are rejected for security. |
| `api_id` | `int` | _required_ | Telegram API ID. Obtain from [my.telegram.org/apps](https://my.telegram.org/apps). Must be a positive integer. The placeholder value `12345` is rejected. |
| `api_hash` | `str` (SecretStr) | _required_ | Telegram API hash. Obtain from [my.telegram.org/apps](https://my.telegram.org/apps). Stored as a SecretStr. Minimum length: 32, max length: 64. Values starting with `YOUR_` are rejected as placeholders. |
| `device_model` | `str` or `null` | `null` | Device model string sent to Telegram (optional). Values starting with `YOUR_` are rejected. |
| `system_version` | `str` or `null` | `null` | System version string sent to Telegram (optional). Values starting with `YOUR_` are rejected. |
| `system_lang_code` | `str` or `null` | `null` | System language code (e.g. `en-US`). |
| `lang_code` | `str` or `null` | `null` | Telegram interface language code (e.g. `ru`). |
| `app_version` | `str` or `null` | `null` | Application version string sent to Telegram (optional). |
| `proxy` | `ProxyConfig` or `null` | `null` | Proxy configuration for Telethon SOCKS4/SOCKS5/HTTP proxy. Uses dedicated `ProxyConfig` Pydantic model with SecretStr for credentials. Requires `proxy_type`, `addr`, `port`. Optional: `username`, `password`, `rdns`. See [Proxy Configuration](#proxy-configuration). |

---

## Proxy Configuration

Telethon supports SOCKS4, SOCKS5, and HTTP proxies via the `proxy` field in `ClientConfig`. Requires `python-socks[asyncio]` package (optional dependency available via `pip install -e ".[proxy]"`).

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `proxy_type` | `str` | Proxy type: `"socks5"`, `"socks4"`, or `"http"` |
| `addr` | `str` | Proxy server IP address or hostname (non-empty) |
| `port` | `int` | Proxy server port (1-65535) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `username` | `str` (SecretStr) | Authentication username (if required). Stored as SecretStr to prevent credential exposure. |
| `password` | `str` (SecretStr) | Authentication password (if required). Stored as SecretStr to prevent credential exposure. |
| `rdns` | `bool` | Remote DNS resolution (SOCKS5 only, default: `true`) |

### SOCKS5 Example

```yaml
TELETHON_API:
  client:
    proxy:
      proxy_type: "socks5"
      addr: "127.0.0.1"
      port: 1080
      username: "user"
      password: "pass"
```

#### Installation

```bash
uv pip install -e ".[proxy]"
```

---

## `log_config.yaml` — Logging Configuration

This file follows the standard Python [`logging.config.dictConfig()`](https://docs.python.org/3/library/logging.config.html#logging-config-dictconfig) format wrapped in a `LOGGING` key.

### Top-Level Structure

```yaml
LOGGING:
  version: 1
  disable_existing_loggers: false
  formatters:
    <formatter_name>:
      class: "logging.Formatter"
      format: "<format_string>"
      datefmt: "<date_format>"
  handlers:
    <handler_name>:
      class: "<handler_class>"
      level: "<LEVEL>"
      formatter: "<formatter_name>"
      # Handler-specific kwargs...
  loggers:
    <logger_name>:
      level: "<LEVEL>"
      handlers: [<handler_name>, ...]
      propagate: <bool>
  root:
    level: "<LEVEL>"
    handlers: [<handler_name>, ...]
```

### Field Reference

| Section | Description |
|---------|-------------|
| `version` | Always `1`. Reserved for schema versioning. |
| `disable_existing_loggers` | Set to `false` to avoid silencing third-party loggers. |
| `formatters` | Map of formatter name → formatter config. Each uses `class: "logging.Formatter"` with optional `format` and `datefmt` strings. |
| `handlers` | Map of handler name → handler config. Supports any Python `logging.Handler` subclass. Common handlers: `logging.StreamHandler`, `logging.handlers.RotatingFileHandler`. Handler kwargs are passed directly to the class constructor. |
| `loggers` | Map of logger name → logger config. Each specifies `level`, `handlers`, and `propagate`. |
| `root` | Root logger configuration (fallback for all unconfigured loggers). |

### Default Handlers

| Handler | Class | Level | Description |
|---------|-------|-------|-------------|
| `console` | `logging.StreamHandler` | `INFO` | Outputs to stdout (`ext://sys.stdout`). |
| `rotating_file` | `logging.handlers.RotatingFileHandler` | `INFO` | Writes to a file with rotation at 2 MB (`maxBytes: 2000000`), keeping 2 backups (`backupCount: 2`). Encoding: UTF-8. |

### Default Loggers

| Logger | Level | Handlers | Propagate |
|--------|-------|----------|-----------|
| `__main__` | `INFO` | `rotating_file` | `false` |
| `tests` | `INFO` | `rotating_file` | `false` |
| `telebot` | `INFO` | `console`, `rotating_file` | `false` |
| _root_ | `INFO` | `console`, `rotating_file` | — |

### Path Resolution for Log Files

Handler `filename` values that are relative paths are automatically resolved against the application log directory (`~/.config/mko_telebot/logs/`). For example, `filename: "log.log"` becomes `~/.config/mko_telebot/logs/log.log`.

---

## SecretStr Handling

Sensitive fields use Pydantic's [`SecretStr`](https://docs.pydantic.dev/latest/concepts/fields/#secret-fields) type to prevent credential exposure in logs, error messages, and serialization output.

### Sensitive Fields

| Field | Location | Purpose |
|-------|----------|---------|
| `phone_or_token` | `telethon_config.yaml` → `TELETHON_API.phone_or_token` | Phone number or bot token |
| `api_hash` | `telethon_config.yaml` → `TELETHON_API.client.api_hash` | Telegram API hash |
| `username` | `telethon_config.yaml` → `TELETHON_API.client.proxy.username` | Proxy authentication username |
| `password` | `telethon_config.yaml` → `TELETHON_API.client.proxy.password` | Proxy authentication password |

### How SecretStr Works

- **In memory:** The value is stored as a `SecretStr` object. Accessing the string through standard attribute access returns `'**********'` — the actual value is hidden.
- **Retrieving the value:** To get the plaintext value in code, call `.get_secret_value()` on the field.
- **Serialization:** By default, `SecretStr` fields serialize as `'**********'` in model dumps unless explicitly configured to show the value.
- **No encryption in transit:** `SecretStr` masks values in logs, error messages, and serialized output. It does **not** encrypt or decrypt data — the raw value is stored in memory.

### Placeholder Detection

The application rejects placeholder values to prevent accidental use of template credentials:

- **api_id:** The value `12345` is rejected as a template placeholder.
- **api_hash:** Any value starting with `YOUR_` is rejected.
- **phone_or_token:** Any value starting with `YOUR_` is rejected.
- **device_model, system_version, session, proxy username/password:** Any value starting with `YOUR_` or `PLACEHOLDER_` is rejected.

If any field fails validation, a `ConfigError` with a descriptive message is raised during `load()`.

---

## Validation Rules

The configuration is validated against Pydantic v2 models when `TelepostConfigReader.load()` is called. The validation pipeline:

1. **Required files check** — both `config.yaml` and `telethon_config.yaml` must exist.
2. **YAML parsing** — both files are parsed with `yaml.safe_load()`. Malformed YAML raises `ConfigError`.
3. **Deep merge** — `telethon_config.yaml` is merged into `config.yaml` (telethon values win on conflict).
4. **Pydantic validation** — the merged dict is validated against `TelepostSettings`, which recursively validates:
   - `TelethonConfig` (from `TELETHON_API` key)
   - `ClientConfig` (from `TELETHON_API.client` key)
   - `ChannelsConfig` (from `CHANNELS` key)
5. **Model validators** run custom checks:
   - Extra fields at any level are rejected (extra="forbid" on all models)
   - Channel names are validated to prevent path traversal attacks
   - Placeholder values are rejected (see [SecretStr Handling](#secretstr-handling))

### Common Validation Errors

| Error | Cause |
|-------|-------|
| `Required config file not found` | Missing `config.yaml` in user settings dir |
| `Required telethon config file not found` | Missing `telethon_config.yaml` in user settings dir |
| `Configuration file not found` | Missing file at the specified path |
| `Malformed YAML in configuration file` | Syntax error in YAML |
| `api_hash appears to be a placeholder value` | `api_hash` value starts with `YOUR_` |
| `api_id value 12345 is a template placeholder` | `api_id` is still the template value |
| `phone_or_token appears to be a placeholder value` | `phone_or_token` value starts with `YOUR_` |
| `Invalid channel name: contains forbidden path character` | Channel name contains `/`, `\`, or `..` |
| `proxy_type must be one of {...}` | Invalid proxy type value |
| `rdns must be a boolean if provided` | `rdns` field has non-boolean value |

---

## Example Files

### Minimal `config.yaml`

```yaml
CHANNELS:
  channels_delay: 30
  stagger_start_seconds: 5
  defaults:
    scan_interval: 420
    history_limit: 50
    history_days: 2
    overlap: 5
    forward_to: []
    keywords: []
  channels: {}
```

### Full `config.yaml` with Multiple Channels

```yaml
CHANNELS:
  channels_delay: 30
  stagger_start_seconds: 5
  defaults:
    scan_interval: 420
    history_limit: 50
    history_days: 2
    overlap: 5
    forward_to: []
    keywords: []

  my_channel:
    name: "@my_channel"
    scan_interval: 300
    keywords:
      - "alert"
      - "important"
    forward_to:
      - "@admin_chat"

  another_channel:
    name: "https://t.me/another_channel"
    history_days: 7
    forward_to:
      - 123456789
```

### Minimal `telethon_config.yaml`

```yaml
TELETHON_API:
  is_user: true
  phone_or_token: "PLACEHOLDER_REPLACE_ME"
  client:
    api_id: 1
    api_hash: "PLACEHOLDER_REPLACE_ME"
    system_lang_code: "en-US"
    lang_code: "ru"
```

### Full `telethon_config.yaml` (User Account)

```yaml
TELETHON_API:
  is_user: true
  phone_or_token: "+79123456789"
  max_retries: 5
  client:
    session: "my_session"
    api_id: 123456
    api_hash: "0123456789abcdef0123456789abcdef"
    device_model: "PC"
    system_version: "Windows 10"
    system_lang_code: "en-US"
    lang_code: "ru"
```

### Full `telethon_config.yaml` (Bot)

```yaml
TELETHON_API:
  is_user: false
  phone_or_token: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
  max_retries: 5
  client:
    session: "my_bot_session"
    api_id: 123456
    api_hash: "0123456789abcdef0123456789abcdef"
    system_lang_code: "en-US"
    lang_code: "ru"
```

### Full `log_config.yaml`

```yaml
LOGGING:
  version: 1
  disable_existing_loggers: false
  formatters:
    basic:
      class: "logging.Formatter"
      format: "%(asctime)s - %(levelname)s - %(message)s - %(name)s"
      datefmt: "%d-%m-%y %I:%M:%S %p"
  handlers:
    console:
      class: "logging.StreamHandler"
      formatter: "basic"
      level: "INFO"
      stream: "ext://sys.stdout"
    rotating_file:
      class: "logging.handlers.RotatingFileHandler"
      level: "INFO"
      formatter: "basic"
      filename: "log.log"
      maxBytes: 2000000
      backupCount: 2
      encoding: "utf-8"
  loggers:
    __main__:
      handlers:
        - "rotating_file"
      level: "INFO"
      propagate: false
    tests:
      level: "INFO"
      handlers:
        - "rotating_file"
      propagate: false
    telebot:
      level: "INFO"
      handlers:
        - "console"
        - "rotating_file"
      propagate: false
  root:
    level: "INFO"
    handlers:
      - "console"
      - "rotating_file"
```