# Phase 02 Audit Findings — Configuration & Pydantic Models

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/02-audit-config.md
**Status:** complete
**Validated:** no
**Mode:** problems-only

---

## Findings

### CFG-001: Relative `--config` path resolves against wrong directory (runtime failure)

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telepost/core/config_reader.py`, `src/mko_telepost/app.py` |
| **Classification** | mandatory |

**Description:** When a user invokes `mko-telepost run --config my_config.yaml` with a
relative path, Typer's `exists=True` flag validates the file against the **current
working directory** (click uses `os.path.exists`, which is CWD-relative). The file is
accepted by the CLI. But `TelepostConfigReader._load_yaml()` then calls
`self._resolve_path(path)`, which routes through `PathResolver.resolve()`, whose
`base_dir` is hardcoded to `APP_PATHS.user_dir` (see `paths.py` line where
`PathResolver(APP_PATHS.user_dir)` is constructed in `config_reader.__init__`). A
relative path is therefore resolved against `~/.config/mko_telepost/`, not against
CWD, and the reader raises `ConfigError("Configuration file not found: ...")`.

The user sees "Configuration not found" for a file that the CLI just accepted as
existing. This is a correctness/operational bug: the documented `--config` flag is
unusable with any relative path.

**Evidence:** Runtime reproduction (Windows, Python 3.14):

```
config_path stored: my_config.yaml
resolver base_dir: C:\Users\Om\AppData\Local\mko_telepost\mko_telepost
FAILED: ConfigError Configuration file not found:
  C:\Users\Om\AppData\Local\mko_telepost\mko_telepost\my_config.yaml
```

`config_reader.py`:
```python
self.resolver = PathResolver(APP_PATHS.user_dir)          # always user_dir
...
def _resolve_path(self, path: Path) -> Path:
    return self.resolver.resolve(path)                      # relative -> user_dir/...
```

`app.py` `run()` passes a relative `Path` straight through when `--config` is given:
```python
reader = TelepostConfigReader(config_path=config_path)     # config_path may be relative
```

**Recommendation:** Resolve `config_path` against the caller's CWD (e.g.
`config_path = config_path.resolve()`) before handing it to the reader, OR make
`TelepostConfigReader.__init__` resolve a relative `config_path` against CWD rather
than delegating relative resolution to `PathResolver` (which is documented as
user-dir-scoped). The reader's `PathResolver` should only own the resolution of
*values inside* the config (credentials_file, token_file, log filenames), not the
config file path itself.

---

### CFG-002: `validate=False` does not actually skip after-validators (misleading API)

| Field | Value |
|-------|-------|
| **ID** | CFG-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/config_reader.py` |
| **Classification** | advisory |

**Description:** `TelepostConfigReader.load(validate: bool = True)` exposes a flag
that is documented to skip after-validators when `False`. The `_validate_settings`
static method's docstring states:

> If False, use model_validate() which skips after validators.

This is factually wrong. Pydantic v2's `model_validate()` runs `@model_validator(
mode="after")` validators exactly the same way `__init__(**kwargs)` does. The flag
does not do what it claims. Runtime verification: calling
`TelepostSettings.model_validate(valid_data)` still fills `chat.min_delay_minutes`
from defaults (the `resolve_chat_defaults` after-validator fires).

A maintainer relying on this flag (e.g. to load a partially-formed config during
`init` before all chats are filled) will get validation they expected to skip.

**Evidence:** `config_reader.py`:
```python
if use_full_validation:
    return TelepostSettings(**config_data)
return TelepostSettings.model_validate(config_data)   # claim: skips after-validators
```

Runtime test:
```
After model_validate: chat.min_delay_minutes = 10.0   # after-validator DID run
```

Pydantic docs confirm `model_validate()` invokes the full validation pipeline
including `mode="after"` model validators.

**Recommendation:** Either remove the `validate` parameter entirely (it is only
used by tests; production always calls `reader.load()` with the default `True`),
or fix the docstring to reflect that both branches run full validation. The flag
carries no real semantic difference today.

---

### CFG-003: `HumanizationConfig` allows `base_delay_seconds > max_delay_seconds`

| Field | Value |
|-------|-------|
| **ID** | CFG-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/chat_models.py` |
| **Classification** | advisory |

**Description:** `HumanizationConfig.validate_delay_bounds` only enforces
`max_delay_seconds >= min_delay_seconds`. There is no cross-check against
`base_delay_seconds`, which is the seed for the actual humanization delay (per the
class docstring: "Base delay for human-like jitter"). A user can configure
`base_delay_seconds=500` with `max_delay_seconds=100`, and the model accepts it —
but the delay engine would then be allowed to produce delays above its own
`max_delay_seconds` bound, defeating the purpose of the cap.

**Evidence:** `chat_models.py`:
```python
@field_validator("max_delay_seconds")
@classmethod
def validate_delay_bounds(cls, v: float, info: ValidationInfo) -> float:
    """Ensure max_delay_seconds >= min_delay_seconds."""
    if "min_delay_seconds" in info.data and info.data["min_delay_seconds"] > v:
        raise ValueError(...)
    return v            # no check vs base_delay_seconds
```

Runtime reproduction:
```
base_delay=500 max_delay=100 accepted: 500.0 100.0 (validator gap)
```

**Recommendation:** Extend the validator (or add a `model_validator(mode="after")`)
to assert `base_delay_seconds <= max_delay_seconds`, so the delay seed cannot
exceed the declared upper bound.

---

### CFG-004: Raw dict persisted as instance state in `TelegramPoster` (spec deviation)

| Field | Value |
|-------|-------|
| **ID** | CFG-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/telegram_poster.py` |
| **Classification** | advisory |

**Description:** `docs/SPEC.md` §4.2 states: "All settings are validated through
Pydantic v2 models. No raw dicts are used in business logic."
`AGENTS.md` repeats the same rule.

`TelegramPoster.__init__` violates this invariant by immediately converting the
validated `ClientConfig` Pydantic model into a plain dict via `model_dump()` and
storing it as mutable instance state (`self.client_config`). The dict is then
mutated in `create_client()` (`config["session"] = ...`) before being unpacked
into `TelegramClient(**config)`. The `SecretStr` for `api_hash` has to be
manually unwrapped via `get_secret_value()` precisely because the model was
flattened to a dict.

While the dict is constructed from a validated model (not from `yaml.safe_load`),
it is still a raw dict living in business logic, which is what the spec forbids.
The pattern also loses type safety on subsequent mutations.

**Evidence:** `telegram_poster.py`:
```python
def __init__(self, settings: TelethonConfig):
    self.settings = settings
    self.client_config = settings.client.model_dump()           # raw dict
    if "api_hash" in self.client_config:
        self.client_config["api_hash"] = settings.client.api_hash.get_secret_value()

def create_client(self) -> TelegramClient:
    config = self.client_config.copy()
    ...
    config["session"] = str(session_path)                        # mutate raw dict
    return TelegramClient(**config)
```

**Recommendation:** Keep the `TelethonConfig`/`ClientConfig` model as the source
of truth on the instance, and build the kwargs dict locally inside
`create_client()` (e.g. `TelegramClient(**model_dump_with_secrets_revealed)` at
the call site). This removes the persistent raw dict and the manual `SecretStr`
unwrapping, and keeps the model as the authoritative, typed representation.

---

### CFG-005: Template ships `api_id: 12345` with no placeholder guard

| Field | Value |
|-------|-------|
| **ID** | CFG-005 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/settings/app_config.yaml`, `src/mko_telepost/core/telethon_models.py` |
| **Classification** | advisory |

**Description:** The template `app_config.yaml` uses the `YOUR_` prefix convention
for every credential-like field (`YOUR_SPREADSHEET_ID_HERE`, `YOUR_API_HASH_HERE`,
`YOUR_PHONE_OR_BOT_TOKEN`, `YOUR_SESSION_NAME`, `YOUR_APP_VERSION`, ...), and the
Pydantic models reject any value starting with `YOUR_` via `field_validator`s.

`api_id` is the exception: the template ships `api_id: 12345` (a real-looking
integer), and `ClientConfig` only enforces `gt=0`. There is no placeholder check,
so a user who forgets to replace `12345` passes validation cleanly and only
discovers the problem at runtime when Telegram rejects the credentials. This is
inconsistent with the placeholder-guard pattern used for all sibling fields.

**Evidence:** `app_config.yaml`:
```yaml
client:
    api_id: 12345  # Replace with your API ID (must be > 0)
    api_hash: "YOUR_API_HASH_HERE"  # Replace with your API hash
```

`telethon_models.py`:
```python
api_id: int = Field(..., gt=0, description="Telegram API ID")   # no placeholder guard
@field_validator("api_hash")
def validate_api_hash(cls, v): ... v.startswith("YOUR_") ...   # guard exists for siblings
```

**Recommendation:** Either ship the template with a clearly-placeholder value
that the model can reject (e.g. an `api_id` sentinel via a separate int field
validator), or accept that `api_id` cannot follow the `YOUR_` string convention
and document this exception explicitly. The goal is that a user who runs `mko
run` without editing the template gets a config-time error, not a Telegram
runtime error.

---

### CFG-006: `log_config.yaml` template targets a non-existent logger name

| Field | Value |
|-------|-------|
| **ID** | CFG-006 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/settings/log_config.yaml` |
| **Classification** | advisory |

**Description:** The logging template defines a named logger `"teleposter"` with
`propagate: false` and attaches the `console` + `rotating_file` handlers to it.
But every module in the package obtains its logger via
`logging.getLogger(__name__)`, producing loggers rooted at `mko_telepost.*`. No
logger named `teleposter` is ever created, so the `"teleposter"` block is dead
configuration — all real log records fall through to the `root` logger. The file
handler ends up duplicated via the root logger rather than the intended named
logger. The template also ships `"filename": "logs/log.log"` as a relative path,
which only works because `config_reader._resolve_log_paths` resolves it against
`user_dir`.

**Evidence:** `log_config.yaml`:
```json
"loggers": {
    "teleporter": {"level": "INFO", "propagate": false, "handlers": ["console", "rotating_file"]}
}
```
Grep across `src/`: every `logging.getLogger(__name__)` call yields
`mko_telepost.*`; there is no `getLogger("teleporter")` anywhere.

**Recommendation:** Rename the template logger to `mko_telepost` (matching the
package root) so the named-logger configuration actually applies, or remove the
`loggers` block and rely on `root`. This makes handler attachment deterministic
and avoids the silent fallthrough to root.

---

### CFG-007: `HumanizationConfig` bounds are asymmetric and incomplete

| Field | Value |
|-------|-------|
| **ID** | CFG-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/chat_models.py` |
| **Classification** | advisory |

**Description:** The numeric bounds on `HumanizationConfig` are inconsistent:
- `min_delay_seconds` has `ge=0.5` but **no upper bound** (`le` missing).
- `max_delay_seconds` has `le=3600` but **no lower bound** (`ge` missing).
- `micro_break_seconds` has `ge=30.0` but **no upper bound**.
- `base_delay_seconds` and `jitter_spread` are bounded on both sides, unlike the
  fields above.

The asymmetry makes the model harder to reason about (a maintainer cannot assume
"every delay field has both bounds") and lets nonsense values through (e.g.
`min_delay_seconds=3500` with `max_delay_seconds=3600` is accepted even though
`min` far exceeds the documented "Minimum delay bound" intent).

**Evidence:** `chat_models.py`:
```python
min_delay_seconds: float = Field(default=5.0, ge=0.5)                       # no le
max_delay_seconds: float = Field(default=600.0, le=3600)                    # no ge
micro_break_seconds: float = Field(default=120.0, ge=30.0)                 # no le
base_delay_seconds: float = Field(default=30.0, ge=1.0, le=3600)           # both bounds
```

**Recommendation:** Add the missing `ge`/`le` bounds so every delay field is
symmetric and self-documenting. Low effort, improves config-time catching of
typo'd values.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 3 |

## Mandatory Fixes

- **CFG-001** — Relative `--config` path resolves against `user_dir` instead of
  CWD, breaking the documented `--config` flag for any relative path. Fix the
  path resolution entry point so the user-provided config file is found.

## Advisory Recommendations

- **CFG-002** — `validate=False` flag in `config_reader.load()` does not skip
  after-validators as documented; the flag is semantically a no-op. Remove the
  flag or correct the docstring.
- **CFG-003** — `HumanizationConfig` accepts `base_delay_seconds >
  max_delay_seconds`; add a cross-field validator so the delay seed cannot
  exceed the declared upper bound.
- **CFG-004** — `TelegramPoster` persists a raw `model_dump()` dict as instance
  state, violating the SPEC's "no raw dicts in business logic" invariant. Keep
  the Pydantic model as the source of truth and build kwargs at the call site.
- **CFG-005** — Template ships `api_id: 12345` without a placeholder guard,
  inconsistent with the `YOUR_` convention used for all sibling credential
  fields. Add a guard or document the exception.
- **CFG-006** — `log_config.yaml` targets a logger named `teleposter` that no
  module ever creates; rename to `mko_telepost` or drop the `loggers` block.
- **CFG-007** — `HumanizationConfig` numeric bounds are asymmetric (some fields
  have only `ge`, others only `le`). Add the missing bounds for consistency.

## Doc Updates Needed

- **CFG-002** — The `_validate_settings` docstring claim that `model_validate()`
  skips after-validators is false; the docstring must be corrected (or the flag
  removed) so the documented behavior matches Pydantic v2 semantics.

---

## Runtime Verification Summary

- **R1 (Model instantiation):** Performed. `extra="forbid"`, `chat_id=0`
  placeholder rejection, and `max < min` rejection all work as documented.
  Discovered CFG-003 (base_delay > max_delay accepted) and CFG-005 (api_id
  placeholder gap) during instantiation.
- **R2 (Config loading):** Performed. Discovered CFG-001 (relative `--config`
  path resolves against `user_dir`, not CWD) via runtime reproduction.
- **R3 (Linter/Type checker):** `uv run ruff check` and `uv run mypy` on all
  seven config-related modules — both clean ("All checks passed!" / "Success: no
  issues found in 7 source files").
- **R4 (Tests):** `uv run pytest -k "config or model or init or path or reader"`
  — 132 passed, 92 deselected. No failures.
