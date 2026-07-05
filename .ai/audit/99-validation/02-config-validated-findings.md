# Phase 02 Audit Findings — Configuration & Pydantic Models (VALIDATED)

**Executor:** validator
**Source:** `.ai/audit/02-config/findings.md`
**Status:** complete
**Validated:** yes
**Mode:** problems-only
**Validation scope:** Each finding verified against current source in `src/mko_telepost/`, `docs/SPEC.md`, and cross-phase findings (`01-cli`).

---

## Validation Process

For every finding the validator:

1. Read the affected source file(s) and confirmed the cited code is present verbatim.
2. Checked `docs/SPEC.md` §4.2 (configuration invariants) and `AGENTS.md` rules.
3. Cross-referenced findings in `.ai/audit/01-cli/findings.md` for shared root causes or conflicts.
4. Assessed architectural fit and operational value at project scale (CLI tool, single user).

### Verified facts

- `core/paths.py`: `PathResolver.resolve()` joins relative paths onto `self.base_dir`; `TelepostConfigReader.__init__` constructs `PathResolver(APP_PATHS.user_dir)`. Confirmed.
- `app.py` `run()`: `--config` uses Typer `exists=True` (CWD-relative check), then passes the raw `Path` (possibly relative) to `TelepostConfigReader(config_path=...)`. Confirmed.
- `core/config_reader.py` `_validate_settings`: `use_full_validation=False` branch calls `TelepostSettings.model_validate(config_data)`, which in Pydantic v2 runs `@model_validator(mode="after")`. The docstring claim ("skips after validators") is false. Confirmed.
- `core/chat_models.py` `HumanizationConfig`: `validate_delay_bounds` only checks `max >= min`; no `base_delay_seconds` cross-check. Field bounds are asymmetric as described. Confirmed.
- `core/telegram_poster.py` `TelegramPoster.__init__`: `self.client_config = settings.client.model_dump()` stored as instance state, mutated later in `create_client()`. `docs/SPEC.md` line 134: "No raw dicts are used in business logic." Confirmed deviation.
- `settings/app_config.yaml`: `api_id: 12345` with no placeholder guard; `telethon_models.py` `ClientConfig.api_id` only enforces `gt=0`. Confirmed.
- `settings/log_config.yaml`: defines logger `"teleposter"`; all 11 modules use `logging.getLogger(__name__)` → `mko_telepost.*`. No `getLogger("teleposter")` exists. Confirmed dead logger block.
- Cross-phase: `01-cli/CLI-001` reports logging is never loaded at startup. This masks CFG-006's operational impact today but does not invalidate the template correctness issue.

---

## Findings
### CFG-001: Relative `--config` path resolves against wrong directory (runtime failure)

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Decision:** APPROVED — `SPEC-DEVIATION` (operational correctness bug). Severity HIGH, classification mandatory.
> - **Verified:** `app.py` `run()` applies Typer `exists=True` (CWD-relative `os.path.exists`) then forwards the raw `Path` to `TelepostConfigReader(config_path=...)`. `config_reader.__init__` builds `PathResolver(APP_PATHS.user_dir)` and `_load_yaml` calls `self._resolve_path(path)` → relative paths join `user_dir`, not CWD. The CLI accepts the file but the reader then raises `ConfigError("Configuration file not found: ...")`. The documented `--config` flag is unusable with any relative path.
> - **Architectural fit:** Fix aligns with `APP_PATHS` being the single source of truth for *user-dir-relative* values, while the user-supplied `--config` argument is a caller-relative path and must be resolved against CWD. The two concerns are correctly separable.
> - **See also:** none.

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION (operational correctness) |
| **Affected Modules** | `src/mko_telepost/core/config_reader.py`, `src/mko_telepost/app.py` |
| **Classification** | mandatory |
| **Validation** | APPROVED — fix required. |

**Description:** When a user invokes `mko-telepost run --config my_config.yaml` with a
relative path, Typer's `exists=True` flag validates the file against the **current
working directory** (click uses `os.path.exists`, which is CWD-relative). The file is
accepted by the CLI. But `TelepostConfigReader._load_yaml()` then calls
`self._resolve_path(path)`, which routes through `PathResolver.resolve()`, whose
`base_dir` is hardcoded to `APP_PATHS.user_dir`. A relative path is therefore
resolved against `~/.config/mko_telepost/`, not against CWD, and the reader raises
`ConfigError("Configuration file not found: ...")`.

The user sees "Configuration not found" for a file that the CLI just accepted as
existing. This is a correctness/operational bug: the documented `--config` flag is
unusable with any relative path.

**Evidence (verified):**

`app.py` — `run()` option and `_load_and_validate_config()`:
```python
config_path: Path | None = typer.Option(
    None, "--config", "-c", exists=True, file_okay=True, dir_okay=False, ...
)
...
if custom_config_path is None:
    reader = TelepostConfigReader.from_user_dir()
else:
    reader = TelepostConfigReader(config_path=config_path)   # relative Path forwarded as-is
```

`config_reader.py`:
```python
self.resolver = PathResolver(APP_PATHS.user_dir)          # always user_dir
...
def _resolve_path(self, path: Path) -> Path:
    return self.resolver.resolve(path)                      # relative -> user_dir/...
```

`paths.py` `PathResolver.resolve()`:
```python
path = Path(path).expanduser()
if not path.is_absolute():
    path = self.base_dir / path
return path.resolve()
```

**Recommendation (validated):** Fix in `app.py` — resolve `config_path` against the
caller's CWD _before_ constructing the reader. Change one line in
`_load_and_validate_config()`:

```python
# Before:
reader = TelepostConfigReader(config_path=config_path)

# After:
reader = TelepostConfigReader(config_path=config_path.resolve())
```

Rationale: `--config` is a CLI argument and CWD is exclusively a CLI-layer concern.
`TelepostConfigReader` and its `PathResolver` are service-layer components designed
to resolve *internal* config values (credentials_file, token_file, log filenames)
against `APP_PATHS.user_dir` — not to resolve the CLI-provided config file path.
Fixing in `app.py` respects the layer separation rule (`AGENTS.md`: app.py → service
layer, no cross-layer imports) and keeps `PathResolver` scoped to its intended
purpose. If the path is already absolute, `Path.resolve()` is a no-op (normalizes
but preserves the path), so the change is always safe.


### CFG-003: `HumanizationConfig` allows `base_delay_seconds > max_delay_seconds`

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Decision:** APPROVED — `SPEC-DEVIATION`. The class docstring describes `base_delay_seconds` as the seed for humanization jitter and `max_delay_seconds` as the "Maximum delay bound"; allowing the seed to exceed the declared upper bound is a logical correctness gap, not merely a style issue.
> - **Verified:** `chat_models.py` `validate_delay_bounds` only checks `max_delay_seconds >= min_delay_seconds`. No validator references `base_delay_seconds`. `base_delay_seconds` is bounded `ge=1.0, le=3600` and `max_delay_seconds` is bounded `le=3600`, so `base=500, max=100` passes both field constraints and the cross-field validator.
> - **Architectural fit:** Adding a `model_validator(mode="after")` for `base <= max` is consistent with the existing `resolve_chat_defaults` after-validator pattern in `models.py`. Low effort.
> - **See also:** CFG-007 (same model, related bounds gap — but distinct: CFG-003 is a cross-field *semantic* invariant, CFG-007 is per-field *symmetry* of constraints. Not merged; both stand.)

| Field | Value |
|-------|-------|
| **ID** | CFG-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/chat_models.py` |
| **Classification** | advisory |
| **Validation** | APPROVED. |

**Description:** `HumanizationConfig.validate_delay_bounds` only enforces
`max_delay_seconds >= min_delay_seconds`. There is no cross-check against
`base_delay_seconds`, which is the seed for the actual humanization delay (per the
class docstring: "Base delay for human-like jitter"). A user can configure
`base_delay_seconds=500` with `max_delay_seconds=100`, and the model accepts it —
but the delay engine would then be allowed to produce delays above its own
`max_delay_seconds` bound, defeating the purpose of the cap.

**Evidence (verified):** `chat_models.py`:
```python
@field_validator("max_delay_seconds")
@classmethod
def validate_delay_bounds(cls, v: float, info: ValidationInfo) -> float:
    """Ensure max_delay_seconds >= min_delay_seconds."""
    if "min_delay_seconds" in info.data and info.data["min_delay_seconds"] > v:
        raise ValueError(...)
    return v            # no check vs base_delay_seconds
```

**Recommendation:** Add a `model_validator(mode="after")` asserting
`base_delay_seconds <= max_delay_seconds`, so the delay seed cannot exceed the
declared upper bound.


### CFG-004: Raw dict persisted as instance state in `TelegramPoster` (spec deviation)

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Decision:** APPROVED — `SPEC-DEVIATION`. `docs/SPEC.md` line 134 explicitly states "All settings are validated through Pydantic v2 models. No raw dicts are used in business logic." `AGENTS.md` repeats the rule. `TelegramPoster.__init__` converts the validated `ClientConfig` model to a plain dict via `model_dump()` and stores it as mutable instance state `self.client_config`, which is then mutated in `create_client()` (`config["session"] = ...`) and unpacked into `TelegramClient(**config)`. The `SecretStr` for `api_hash` is manually unwrapped via `get_secret_value()` precisely because the model was flattened to a dict — a direct symptom of the deviation.
> - **Architectural fit:** Recommendation keeps the `TelethonConfig`/`ClientConfig` model as the typed source of truth on the instance and builds kwargs locally inside `create_client()`. Aligns with the SPEC invariant and removes the manual `SecretStr` unwrapping. Minimal, low-risk refactor.
> - **See also:** none.

| Field | Value |
|-------|-------|
| **ID** | CFG-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/telegram_poster.py` |
| **Classification** | advisory |
| **Validation** | APPROVED. |

**Description:** `TelegramPoster.__init__` violates the SPEC invariant by
immediately converting the validated `ClientConfig` Pydantic model into a plain
dict via `model_dump()` and storing it as mutable instance state
(`self.client_config`). The dict is then mutated in `create_client()`
(`config["session"] = ...`) before being unpacked into `TelegramClient(**config)`.
The `SecretStr` for `api_hash` has to be manually unwrapped via
`get_secret_value()` precisely because the model was flattened to a dict.

**Evidence (verified):** `telegram_poster.py`:
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

`docs/SPEC.md` (line 134):
> All settings are validated through Pydantic v2 models. No raw dicts are used in
> business logic.

**Recommendation:** Keep the `TelethonConfig`/`ClientConfig` model as the source
of truth on the instance, and build the kwargs dict locally inside
`create_client()` at the call site (resolving the session path and revealing
`api_hash` there). This removes the persistent raw dict, the manual `SecretStr`
unwrapping, and keeps the model as the authoritative, typed representation.


### CFG-005: Template ships `api_id: 12345` with no placeholder guard

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Decision:** APPROVED — `SPEC-DEVIATION`. The template uses the `YOUR_` prefix convention for every sibling credential-like field and `telethon_models.py` rejects `YOUR_`-prefixed values via `field_validator`s. `api_id` is the exception: template ships `12345` and `ClientConfig.api_id` only enforces `gt=0`. A user who forgets to replace `12345` passes validation and only discovers the problem at Telegram runtime. Inconsistent with the established placeholder-guard pattern.
> - **Architectural fit:** `api_id` is typed `int`, so the `YOUR_` string convention cannot apply directly. The recommendation uses a sentinel-based `field_validator` on `api_id` that rejects the template's `12345`, extending the established guard pattern (already present for `api_hash`, `phone_or_token`, etc.) to integer fields. Low effort, consistent config-time UX.
> - **See also:** none.

| Field | Value |
|-------|-------|
| **ID** | CFG-005 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/settings/app_config.yaml`, `src/mko_telepost/core/telethon_models.py` |
| **Classification** | advisory |
| **Validation** | APPROVED. |

**Description:** The template `app_config.yaml` uses the `YOUR_` prefix convention
for every credential-like field, and the Pydantic models reject any value starting
with `YOUR_` via `field_validator`s. `api_id` is the exception: the template ships
`api_id: 12345` (a real-looking integer), and `ClientConfig` only enforces
`gt=0`. There is no placeholder check, so a user who forgets to replace `12345`
passes validation cleanly and only discovers the problem at runtime when Telegram
rejects the credentials.

**Evidence (verified):** `app_config.yaml`:
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

**Recommendation (single):** Add a `@field_validator("api_id")` to `ClientConfig` in
`src/mko_telepost/core/telethon_models.py` that rejects the template sentinel value
`12345`. This extends the existing placeholder-guard pattern (already established for
`api_hash`, `phone_or_token`, and other `YOUR_`-prefixed fields) to integer-typed
credential fields. A user who runs `mko run` without editing the template gets a clear
config-time error instead of a Telegram runtime error.

**Exact change to `src/mko_telepost/core/telethon_models.py`:**

Add the following `field_validator` inside `ClientConfig`, after the existing
`@field_validator("api_hash")` block:

```python
@field_validator("api_id")
@classmethod
def validate_api_id(cls, v: int) -> int:
    """Reject the template placeholder value for api_id."""
    if v == 12345:
        raise ValueError(
            "api_id value 12345 is a template placeholder. "
            "Replace with your actual API ID from https://my.telegram.org/apps."
        )
    return v
```

**Template change (optional but recommended):** Update the inline comment in
`src/mko_telepost/settings/app_config.yaml` from `# Replace with your API ID (must be > 0)`
to `# Replace with your API ID (must be > 0; 12345 is a sentinel and will be rejected)`.


### CFG-006: `log_config.yaml` template targets a non-existent logger name

> **Validation Note:**
> - **Action:** validated (unchanged) with evidence correction + cross-phase dependency note.
> - **Decision:** APPROVED — `SPEC-DEVIATION`. The template defines a named logger `"teleposter"` with `propagate: false` and attaches `console` + `rotating_file` handlers to it. Every module in `src/` obtains its logger via `logging.getLogger(__name__)`, producing loggers rooted at `mko_telepost.*`. No `getLogger("teleposter")` exists anywhere in the package (verified via grep across `src/`), so the `"teleposter"` block is dead configuration.
> - **Evidence correction:** The source findings.md evidence block quoted the logger name as `"teleporter"` (with an extra `e`). The actual `log_config.yaml` ships `"teleposter"`. This is a transcription typo in the audit evidence, not a code difference — the substance of the finding (logger name does not match the package root `mko_telepost`) is correct either way.
> - **Cross-phase dependency:** `01-cli/CLI-001` reports that logging is never loaded at CLI startup (`load_logging_config()` is referenced only in tests). This means CFG-006 has **no operational impact today** — the dead `"teleposter"` block is never read at runtime. The template correctness fix is still valid and should be applied **together with** CLI-001's fix so that once logging is wired in, handler attachment is deterministic.
> - **See also:** `01-cli/CLI-001` (hidden dependency: CFG-006 fix only has operational effect once logging is loaded at startup).

| Field | Value |
|-------|-------|
| **ID** | CFG-006 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/settings/log_config.yaml` |
| **Classification** | advisory |
| **Validation** | APPROVED (with evidence correction and cross-phase dependency on `01-cli/CLI-001`). |

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

**Evidence (verified, corrected):** `log_config.yaml`:
```json
"loggers": {
    "teleposter": {"level": "INFO", "propagate": false, "handlers": ["console", "rotating_file"]}
}
```
Grep across `src/`: all 11 `logging.getLogger(__name__)` calls yield
`mko_telepost.*`; there is no `getLogger("teleposter")` anywhere.

**Recommendation:** Rename the template logger to `mko_telepost` (matching the
package root) so the named-logger configuration actually applies, or remove the
`loggers` block and rely on `root`. This makes handler attachment deterministic
and avoids the silent fallthrough to root. Apply alongside the `01-cli/CLI-001`
fix so the configuration is actually loaded.


### CFG-007: `HumanizationConfig` bounds are asymmetric and incomplete

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Decision:** APPROVED — `BEST-PRACTICE`. Low effort, high ROI: adding the missing `ge`/`le` bounds makes every delay field symmetric and self-documenting, and catches typo'd values at config time. This is consistent with the project rule favoring small, focused, maintainable models; it does not introduce abstraction or indirection.
> - **Verified:** `chat_models.py` field declarations match the finding exactly: `min_delay_seconds` has `ge=0.5` (no `le`); `max_delay_seconds` has `le=3600` (no `ge`); `micro_break_seconds` has `ge=30.0` (no `le`); `base_delay_seconds` (`ge=1.0, le=3600`), `jitter_spread` (`ge=0.1, le=2.0`), and `micro_break_every` (`ge=1, le=100`) are symmetric.
> - **Architectural fit:** Pure additive constraint change; no behavioral regression for valid configs. Note interaction with CFG-003: adding `ge` to `max_delay_seconds` does not relieve the need for the cross-field `base <= max` invariant — both fixes are independent and complementary.
> - **See also:** CFG-003 (related model, distinct concern).

| Field | Value |
|-------|-------|
| **ID** | CFG-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/chat_models.py` |
| **Classification** | advisory |
| **Validation** | APPROVED. |

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

**Evidence (verified):** `chat_models.py`:
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

## Cross-Finding Analysis

### Merge candidates

No findings within Phase 02 share a single root cause:

- **CFG-003 vs CFG-007** — both touch `HumanizationConfig` bounds but address distinct concerns: CFG-003 is a missing *cross-field semantic* invariant (`base_delay_seconds <= max_delay_seconds`); CFG-007 is per-field *symmetry* of `ge`/`le` constraints. They are complementary, not duplicates. **Not merged.** Both stand; CFG-007 even notes that adding `ge` to `max_delay_seconds` does not satisfy CFG-003's requirement.

### Cross-phase conflicts

None. The Phase 02 findings are consistent with `01-cli` findings:

- `01-cli/CLI-001` (logging never loaded at startup) and `02-config/CFG-006` (template logger name `"teleposter"` does not match package root) are **complementary, not conflicting**. CLI-001 explains why CFG-006 currently has zero operational impact; fixing CFG-006 without CLI-001 would leave the dead block unloaded, and fixing CLI-001 without CFG-006 would load a misconfigured logger. They should be fixed together.
- `01-cli/CLI-002` (config-not-found message wording) and `02-config/CFG-001` (relative `--config` resolves against wrong dir) are distinct: CLI-002 is about message text, CFG-001 is about path resolution. No conflict.

### Dependency chains within the phase

- CFG-003 and CFG-007 both edit `chat_models.py` `HumanizationConfig`. They touch different constructs (a validator vs field constraints) and can be applied in either order. No sequencing constraint.
- CFG-002 (config_reader docstring/flag) and CFG-001 (config_reader path resolution) both edit `config_reader.py` but in different methods. No ordering dependency.
- CFG-004 (`telegram_poster.py`), CFG-005 (`telethon_models.py` + template), CFG-006 (`log_config.yaml`) are in separate files. Independent.


---

## Rollout Safety

- **No circular dependencies** detected. All fixes are local to individual modules or templates.
- **No unsafe ordering** within Phase 02. Fixes are independent or complementary (CFG-003 + CFG-007 in the same model class; either order is safe).
- **One hidden cross-phase dependency:** CFG-006 (template logger rename) has operational value only once `01-cli/CLI-001` (load logging at startup) is also fixed. Applying CFG-006 alone is safe but has no visible effect until logging is wired in. Recommended sequencing: fix CLI-001 first or together with CFG-006.
- **Backward compatibility:** All fixes are additive (new validators, new bounds, docstring correction, model-as-source-of-truth refactor, template rename). No existing valid configuration is rejected by any fix:
  - CFG-003: only rejects `base > max`, which is logically invalid.
  - CFG-005: only rejects the template sentinel `12345`; real `api_id` values are unaffected.
  - CFG-007: only adds bounds that already match documented intent; existing defaults remain valid.
  - CFG-004: internal refactor; `TelegramClient` call signature unchanged.
- **Fragile insertion points:** none. All recommendations target named methods/validators/classes, not line numbers.

---

## Warnings

- **Documentation inconsistency (CFG-002):** The `load()` and `_validate_settings` docstrings describe behavior that contradicts Pydantic v2 semantics. Any maintainer relying on `validate=False` to obtain a partially-validated `TelepostSettings` (e.g. during `init`) will silently get full validation. This is a correctness risk for future code even though production never passes `False` today.
- **Cross-phase masking (CFG-006 / CLI-001):** The dead `"teleposter"` logger block is currently invisible at runtime because logging is never loaded. Do not treat "no user has reported this" as evidence the template is correct.
- **Architectural risk (CFG-004):** The persistent raw dict in `TelegramPoster` is the kind of state that tends to accumulate further direct mutations over time (each new `TelegramClient` kwarg would be another `config["..."] = ...` line). Fixing it now is cheaper than after more mutations accrete.

---

## Required Fixes (mandatory)

- **CFG-001** — Resolve a relative `--config` path against CWD before handing it to `TelepostConfigReader`. The documented `--config` flag is otherwise unusable with any relative path.

## Advisory Recommendations

- **CFG-002** — Correct the `load()` and `_validate_settings` docstrings (or remove the no-op `validate` parameter) so documented behavior matches Pydantic v2 semantics. No production behavior change required.
- **CFG-003** — Add a `model_validator(mode="after")` asserting `base_delay_seconds <= max_delay_seconds` on `HumanizationConfig`.
- **CFG-004** — Keep `ClientConfig` as the typed source of truth on `TelegramPoster`; build `TelegramClient` kwargs locally inside `create_client()` instead of persisting a `model_dump()` dict as instance state.
- **CFG-005** — Add a sentinel-based `@field_validator("api_id")` to `ClientConfig` that rejects `12345`, so an unedited template fails at config time, not at Telegram runtime.
- **CFG-006** — Rename the `log_config.yaml` logger from `"teleposter"` to `mko_telepost` (or drop the `loggers` block). Apply together with `01-cli/CLI-001`.
- **CFG-007** — Add the missing `ge`/`le` bounds to `min_delay_seconds`, `max_delay_seconds`, and `micro_break_seconds` for symmetry.

## Doc Updates Needed

- **CFG-002** — The `_validate_settings` and `load()` docstring claims that `model_validate()` skips after-validators are false; correct them (or remove the flag) so the documented behavior matches Pydantic v2 semantics.


---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 6 | CFG-001, CFG-003, CFG-004, CFG-005, CFG-006, CFG-007 |
| Reclassified | 1 | CFG-002 (SPEC-DEVIATION → DOC-UPDATE) |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None.

### Merged Findings

None.

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| CFG-002 | SPEC-DEVIATION | DOC-UPDATE | The code behavior (`model_validate()` running the full validation pipeline including `mode="after"` validators) is the correct, safer Pydantic v2 behavior. The defect is purely in the `load()` and `_validate_settings` docstrings, which falsely claim after-validators are skipped. Per validation rule "If code is better than docs → reclassify as `[DOC-UPDATE]`". Production never passes `validate=False`; the flag is only used by tests. Fix the docstrings (or remove the no-op flag) — no production behavior change required. |

### Severity totals (validated)

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 (CFG-001, mandatory) |
| MEDIUM | 3 (CFG-002, CFG-003, CFG-004) |
| LOW | 3 (CFG-005, CFG-006, CFG-007) |

### Type totals (validated)

| Type | Count |
|------|-------|
| SPEC-DEVIATION | 5 (CFG-001, CFG-003, CFG-004, CFG-005, CFG-006) |
| DOC-UPDATE | 1 (CFG-002) |
| BEST-PRACTICE | 1 (CFG-007) |

---

## Runtime Verification Summary (carried over from source findings, validator-confirmed)

- **R1 (Model instantiation):** `extra="forbid"`, `chat_id=0` placeholder rejection, and `max < min` rejection all work as documented. CFG-003 (`base_delay > max_delay` accepted) and CFG-005 (`api_id` placeholder gap) confirmed during instantiation.
- **R2 (Config loading):** CFG-001 confirmed via runtime reproduction — relative `--config` path resolves against `user_dir`, not CWD.
- **R3 (Linter/Type checker):** `uv run ruff check` and `uv run mypy` on the seven config-related modules — both clean.
- **R4 (Tests):** `uv run pytest -k "config or model or init or path or reader"` — 132 passed, 92 deselected. No failures.

---

*Validation complete. All seven findings approved (six unchanged, one reclassified to DOC-UPDATE). No rejections, no merges. One cross-phase dependency noted (CFG-006 ↔ `01-cli/CLI-001`).*
