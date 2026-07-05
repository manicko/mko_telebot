# SEC-001 Research Findings — Credential Leak via ValidationError Cause Chain

**Task:** TASK_016_research_SEC001_credential_leak  
**Date:** 2026-07-03  
**Author:** Research agent  
**Status:** Complete (go recommendation)

---

## 1. All `raise ... from` Sites in `config_reader.py`

| # | Line | Site | Chains What | Credential Risk |
|---|------|------|-------------|-----------------|
| 1 | 109 | `raise ConfigError(f"Failed to load configuration: {e}") from e` in `load()` | Any non-`ConfigError` exception (`OSError`, `yaml.YAMLError`, etc.) | **Low indirect risk.** `e` interpolated into message via f-string (a copy lands in `ConfigError.args[0]`). The `__cause__` chain carries the original exception `str()`. On its own, no Pydantic `input_value` exposure. However, if Pydantic 3 changes `ValidationError` to not subclass `Exception` (i.e. lands in this `except` branch), the raw `ValidationError` with `input_value` would be chained here instead of line 153. |
| 2 | 153 | `raise ConfigError(sanitized_msg) from e` in `_validate_settings()` | `pydantic.ValidationError` | **CRITICAL.** `e` is the raw `ValidationError` which Pydantic v2 renders with `input_value='...'` for each error. For `SecretStr` fields (`api_hash`, `phone_or_token`), the plaintext value is exposed. |

## 2. How Credentials Leak Through the Cause Chain

### Leak Path (app.py → config_reader.py):

```
app.py:63  _load_and_validate_config()
  config_path exists check (OK)
  → app.py:90-93  reader = TelepostConfigReader() / reader.load()
    → config_reader.py:83-109  TelepostConfigReader.load()
      → config_reader.py:100  self._settings = self._validate_settings(config_data)
        → config_reader.py:144-153  _validate_settings()
          TelepostSettings.model_validate(config_data)
          → raises pydantic.ValidationError if invalid
          → catch: builds sanitized_msg (loc + error_type only)
          → **raise ConfigError(sanitized_msg) from e**  ← LINE 153
      → ConfigError propagates up
      (if non-ConfigError: **raise ConfigError(...) from e** at LINE 109)
  → app.py:115-116  **except Exception: logger.exception("Configuration load failed")**
    → logger.exception formats full exception chain:
      - ConfigError message (sanitized ✅)
      - __cause__: ValidationError (UNSANITIZED ❌)
        - input_value='BBBBB...' (plaintext api_hash or phone_or_token)
    → goes to Python's lastResort stderr handler
```

### Root cause:

`raise ConfigError(sanitized_msg) from e` on line 153. The `from e` syntax sets `ConfigError.__cause__` to the original `ValidationError`. When `logger.exception()` (equivalent to `logger.error(..., exc_info=True)`) formats the traceback, Python's logging formatter calls `traceback.print_exception()` which walks the entire `__cause__` / `__context__` chain and renders each exception's `__str__()`.

Pydantic v2's `ValidationError.__str__()` includes `input_value=<repr(value)>` for every error, and for `SecretStr` fields this renders the **plaintext secret** — not `'******'`. This is by design in Pydantic v2 (the `input_value` is the pre-validation input, not the validated model field).

### Test gap:

`tests/test_validation_sanitization.py` only asserts `secret_value not in str(exc_info.value)` — i.e. the `ConfigError` message. It never captures `logging` output or checks whether the `ValidationError.__cause__` text appears in the formatted traceback. The existing tests pass with the leak present.

## 3. Stderr vs Disk Persistence Paths Assessment

### Current state (before CLI-001 fix):

| Path | Active? | Leak Destination |
|------|---------|------------------|
| `logger.exception()` → Python `lastResort` handler | **Yes** | `stderr` (terminal / shell capture / CI logs) |
| `log_config.yaml` `RotatingFileHandler` | **No** | Not loaded at runtime → handler never installed |
| `console.print()` in `app.py` | **No** | Exception caught before Rich output — only generic "Check logs" message printed |

**Confirmed (by SEC-001 Validation Note + SEC-X01):** `TelepostConfigReader.load_logging_config()` is defined at `config_reader.py:155` but called **only** from `tests/test_config_reader.py:113`. There is zero `dictConfig` / `fileConfig` / `basicConfig` call in `src/`. The root logger has zero handlers; Python's `lastResort` (`<_StderrHandler <stderr> (WARNING)>`) handles all `WARNING+` records including the SEC-001 leak.

### Escalation path (after CLI-001 fix without SEC-001):

CLI-001 (Phase 01, validated as SPEC-DEVIATION) mandates loading `log_config.yaml` at startup. `log_config.yaml` configures:

```yaml
handlers:
  file:
    class: logging.handlers.RotatingFileHandler
    filename: logs/log.log           # resolved to ~/.config/mko_telepost/logs/log.log
    maxBytes: 5242880                # 5 MB
    backupCount: 2
root:
  level: WARNING
  handlers: [file]
```

If CLI-001 is implemented before SEC-001, every config validation failure will write the plaintext `api_hash` / `phone_or_token` to:
1. `~/.config/mko_telepost/logs/log.log` (up to 5 MB)
2. `~/.config/mko_telepost/logs/log.log.1` (previous rotation, 5 MB)
3. `~/.config/mko_telepost/logs/log.log.2` (previous rotation, 5 MB)

This **escalates from transient stderr (ephemeral) to persistent credential-at-rest on disk**.

### No other persistence paths identified:

- No syslog, no journald, no Windows Event Log integration.
- No `logging.handlers.SMTPHandler`, `HTTPHandler`, or network handlers.
- The only file handler is the `RotatingFileHandler` in the unloaded `log_config.yaml`.

### Summary:

| State | Leak destination | Persistence | Severity |
|-------|------------------|-------------|----------|
| **Current** | stderr (terminal / CI / Docker) | Ephemeral (session only) | CRITICAL (exposure in CI pipelines) |
| **After CLI-001 alone** | `logs/log.log` + 2 rotations | Disk (persistent across reboots) | CRITICAL (escalated) |
| **After SEC-001 fix** | None (neither stderr nor disk) | None | RESOLVED |

## 4. Go/No-Go Recommendation

### ✅ GO — SEC-001 can proceed

### Rationale:

1. **Preconditions satisfied:** Depends_on `TASK_015_QLT009_log_exception_resize_image` is confirmed complete (present in `.ai/tasks/done/`).
2. **Scope fully understood:** Both `raise ... from` sites identified (lines 109 and 153). The primary site (line 153) is the credential leak vector; the secondary site (line 109) is low-risk today but should be hardened for defense-in-depth.
3. **Fix is localized:** Single change in `_validate_settings` at `config_reader.py:153`: `raise ConfigError(sanitized_msg) from None`.
4. **SEC-X01 ordering confirmed:** SEC-001 must land before or atomically with CLI-001. The research confirms SEC-X01's cross-phase dependency — there is no reason to delay SEC-001.
5. **No merge conflicts anticipated:** SEC-001 edits only `config_reader.py:153` (one line). CFG-002 also edits the same method but for docstrings — trivially separable.

### Recommended fix for TASK_017_SEC001:

1. **Primary fix** (`config_reader.py:153`): Change `raise ConfigError(sanitized_msg) from e` → `raise ConfigError(sanitized_msg) from None`.
2. **Defense-in-depth** (`config_reader.py:109`): Change `raise ConfigError(f"Failed to load configuration: {e}") from e` → `raise ConfigError(f"Failed to load configuration: {e}") from None` (the message already carries the `str(e)` copy; the `__cause__` chain is redundant and risks exposing future-sensitive data).
3. **Regression test** (`tests/test_validation_sanitization.py`): Add a test that captures `logging` output (using `pytest`'s `caplog` fixture or a custom `logging.Handler`) and asserts the secret is absent from the **formatted traceback** (not just from `str(exc_info.value)`).
4. **Blocked task:** TASK_017_SEC001 can proceed immediately.

## 5. Files Read (Not Modified)

| File | Purpose |
|------|---------|
| `.ai/tasks/todo/TASK_016_research_SEC001_credential_leak.yaml` | Task definition |
| `docs/99-reference/ast-editor.md` | AST editor tool reference |
| `.ai/audit/99-validation/04-security-validated-findings.md` | SEC-001 + SEC-X01 findings |
| `src/mko_telepost/core/config_reader.py` | Primary audit target |
| `src/mko_telepost/app.py` | Caller of `reader.load()` + `logger.exception` |
| `src/mko_telepost/core/errors.py` | `ConfigError` definition |
| `tests/test_validation_sanitization.py` | Existing sanitization test |
| `tests/test_config_reader.py` | Secondary caller audit |
| `tests/test_app.py` | Mock callers of TelepostConfigReader |