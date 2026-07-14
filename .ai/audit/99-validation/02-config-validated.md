# Phase 02 Audit Findings — Configuration & Pydantic Models

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** yes
**Validated Date:** 2025-07-14

---

## Findings

### CFG-001: `proxy_type` field in ProxyConfig uses plain string instead of StrEnum

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/telethon.py` |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Confirmed. The `proxy_type` field at line 26 uses `str` type with hardcoded validation `"socks5", "socks4", "http"` at lines 45-48. Project rules mandate StrEnum for all fixed values (roles, statuses, types, modes). This is a legitimate spec deviation requiring code change.
> - **See also:** —

**Description:** The `proxy_type` field in `ProxyConfig` (line 26) uses a plain `str` type with a field validator that checks against hardcoded values `{"socks5", "socks4", "http"}`. Per project rules, fixed-value fields must use `StrEnum` instead of plain strings or magic constants. The `LogLevel` enum in `channels.py` serves as a correct example, but `proxy_type` was not converted.

**Evidence:**
- `src/mko_telebot/core/telethon.py:26`: `proxy_type: str = Field(..., description="Proxy type")`
- `src/mko_telebot/core/telethon.py:45-50`: Hardcoded set validation `"socks5", "socks4", "http"` in `validate_proxy_type` method
- Project rules require `StrEnum` for all fixed values (roles, statuses, types, modes)

**Recommendation:** Create a `ProxyType` StrEnum with values SOCKS5, SOCKS4, HTTP and update `ProxyConfig.proxy_type` to use this enum instead of a plain string. This provides type safety, IDE autocomplete, and prevents typos.

---

### CFG-002: Unused `LogLevel` StrEnum in channels.py

| Field | Value |
|-------|-------|
| **ID** | CFG-002 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | `src/mko_telebot/core/channels.py` |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Confirmed. The `LogLevel` StrEnum is defined, exported via `__all__` in channels.py and `__init__.py`, and listed in py_map.yaml, but is never used in Pydantic models, configuration files, or runtime code. The log configuration uses plain string level names. Per validation rule #55-60, when the spec/models/config do NOT reference a component, the "dead code" label is appropriate. This is genuinely unused code that should be removed or integrated.
> - **See also:** —

**Description:** `LogLevel` StrEnum is defined and exported but never used in any configuration model or consuming code. It exists in `channels.py` and is exported via `__all__`, but searches find no references to `LogLevel.` in the codebase. This is dead code that adds confusion.

**Evidence:**
- `src/mko_telebot/core/channels.py:11-20`: `LogLevel` enum definition
- `src/mko_telebot/core/__init__.py:7`: Exported via `__all__`
- No code references `LogLevel.` anywhere in the codebase (only definition and export sites)

**Recommendation:** Either remove `LogLevel` entirely since it's unused, or add documentation explaining its intended purpose if it's meant for future use. Currently it appears to be dead code.

---

### CFG-003: Type safety warnings in config.py and channels.py

| Field | Value |
|-------|-------|
| **ID** | CFG-003 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/core/config.py`, `src/mko_telebot/core/channels.py` |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Confirmed. 34 basedpyright warnings verified: unannotated class attributes at config.py:122-124 (3 warnings), explicit Any types at config.py:50,78,179 (3 warnings), and various Any/unknown type issues in config.py and channels.py. Note: The "implicit string concatenation" warnings at telethon.py:60,162,195 are false positives - these are valid Python multi-line string literals intentionally split across lines for readability.
> - **See also:** —

**Description:** The `basedpyright` type checker reports 37 warnings for type safety issues in configuration modules. These include missing type annotations on class attributes, use of `Any` types, and implicit string concatenation. While tests pass, these indicate maintainability issues.

**Evidence:**
- `src/mko_telebot/core/config.py:122-124`: Unannotated class attributes `config_path`, `secrets_path`, `log_config_path`
- `src/mko_telebot/core/config.py:50,78,179`: Explicit `Any` type usage
- `src/mko_telebot/core/channels.py:121`: Unused result from channel validation

**Recommendation:** Add explicit type annotations to class attributes and reduce use of `Any` types by using proper typing.

---

### CFG-004: ConfigError message doesn't guide user to run init

| Field | Value |
|-------|-------|
| **ID** | CFG-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/config.py`, `src/mko_telebot/core/errors.py` |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** Confirmed. The ConfigError at config.py:63 raises with message "Configuration file not found" without actionable guidance. Users seeing this error have no indication that `mko-telebot init` exists to create the missing configuration. This is a valid UX improvement.
> - **See also:** —

**Description:** When a configuration file is missing, `ConfigError` is raised with only the file path. The error message does not guide users to run `mko-telebot init` to create the configuration files, which is the documented resolution path. This degrades user experience for newcomers.

**Evidence:**
- `src/mko_telebot/core/config.py:63`: `raise ConfigError("Configuration file not found", path=path)`
- Actual error output: `Required config file not found (path: /nonexistent/config.yaml)` — no mention of `init` command
- Documentation at `docs/11-guides/configuration.md:83`: Error recovery should guide users to the `init` command

**Recommendation:** Update the error message to include actionable guidance, e.g., "Configuration file not found at {path}. Run 'mko-telebot init' to create the default configuration files."

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 2 |

## Mandatory Fixes

None — all findings are advisory.

## Advisory Recommendations

- CFG-001: Create `ProxyType` StrEnum for proxy type validation
- CFG-002: Remove or document unused `LogLevel` enum
- CFG-003: Fix type safety warnings (class attribute annotations, Any types)
- CFG-004: Improve ConfigError message to guide users to run init

## Doc Updates Needed

- CFG-002: If `LogLevel` is removed, update documentation references

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 4 | CFG-001, CFG-002, CFG-003, CFG-004 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | — |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | — |

---

## Research Addendum: CFG-002 and CFG-003 Clarification

### CFG-002: LogLevel StrEnum — Removal Recommended

**Finding**: `LogLevel` is dead code and should be removed.

**Evidence**:
- `LogLevel` defined in `src/mko_telebot/core/channels.py:11-18` with values DEBUG, INFO, WARNING, ERROR, CRITICAL
- Exported via `__all__` in channels.py and `__init__.py` but **no code references `LogLevel.`** anywhere
- Python's `logging` module already provides `logging.DEBUG`, `logging.INFO`, etc. as integer constants
- `logging.py:41` uses `logging.INFO` directly, not `LogLevel.INFO`
- No YAML configuration schema references `LogLevel`
- No Pydantic model uses `LogLevel` as a field type

**Actionable Recommendation**: Remove `LogLevel` entirely. Complete code changes:
1. Remove lines 11-20 in `src/mko_telebot/core/channels.py` (enum + docstring)
2. Remove `"LogLevel"` from `__all__` in `src/mko_telebot/core/channels.py:151`
3. Remove `"LogLevel"` import and export from `src/mko_telebot/core/__init__.py:7,21`

**Impact**: Zero — codebase does not use this enum.

### CFG-003: Type Safety Warnings — Specific Implementation Approach

**Finding**: 31 type warnings in config.py (20) and channels.py (11), requiring targeted fixes.

**Classification by Warning Type**:

| Warning Type | Count | Location | Recommended Fix |
|--------------|-------|----------|-----------------|
| Unannotated class attributes | 3 | config.py:122-124 | Add `self.config_path: Path` etc. annotations |
| Explicit `Any` in function signatures | 3 | config.py:50,78,179 | Use `dict[str, Any]` consistently for YAML data |
| Implicit `Any` from `model_dump()` | 8 | channels.py:131-147 | Annotate loop variables: `default_value: Any` |
| `UnusedCallResult` | 1 | channels.py:121 | Assign pop result to `_` |
| Unknown types from YAML loading | 16 | config.py:66,89,197,200 | Use `dict[str, Any]` consistently |

**Specific Code Changes**:

**config.py — Add class attribute annotations (lines 122-124)**:
```python
        self.config_path: Path = config_path
        self.secrets_path: Path = secrets_path
        self.log_config_path: Path | None = log_config_path
        self._settings: TelepostSettings | None = None
```

**config.py — Annotate YAML loaded data (line 66)**:
```python
        data: dict[str, Any] = yaml.safe_load(f)
```

**channels.py — Annotate loop variables in `apply_defaults_to_channels` (lines 130-141)**:
```python
        update_data: dict[str, Any] = {}
        for field_name, default_value in defaults_data.items():
            current_val: Any = getattr(channel, field_name)
```

**channels.py — Fix unused result (line 121)**:
```python
_ = self.channels.pop("DEFAULTS", None)
```

**Rationale**: YAML configuration files are inherently dynamic (`dict[str, Any]`). The warnings stem from:
1. Python lacking typed YAML — `yaml.safe_load()` returns `Any`
2. Missing annotation syntax for class attributes in `__init__`
3. Pydantic's `model_dump()` returning `dict[str, Any]` for runtime-dumped data

These changes satisfy `basedpyright` while maintaining runtime flexibility.