# Phase 02 Audit Findings — Configuration & Pydantic Models

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

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

**Description:** The `proxy_type` field in `ProxyConfig` (line 26) uses a plain `str` type with a field validator that checks against hardcoded values `{"socks5", "socks4", "http"}`. Per project rules, fixed-value fields must use `StrEnum` instead of plain strings or magic constants. The `LogLevel` enum in `channels.py` serves as a correct example, but `proxy_type` was not converted.

**Evidence:**
- `src/mko_telebot/core/telethon.py:26`: `proxy_type: str = Field(..., description="Proxy type")`
- `src/mko_telebot/core/telethon.py:45-50`: Hardcoded set validation `"socks5", "socks4", "http"` in `validate_proxy_type` method
- Project rules require `StrEnum` for all fixed values (roles, statuses, types, modes)

**Recommendation:** Create a `ProxyType` StrEnum with values SOCKS5, SOCKS4, HTTP and update `ProxyConfig.proxy_type` to use this enum instead of a plain string. This provides type safety, IDE autocomplete, and prevents typos.

### CFG-002: Unused `LogLevel` StrEnum in channels.py

| Field | Value |
|-------|-------|
| **ID** | CFG-002 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | `src/mko_telebot/core/channels.py` |
| **Classification** | advisory |

**Description:** `LogLevel` StrEnum is defined and exported but never used in any configuration model or consuming code. It exists in `channels.py` and is exported via `__all__`, but searches find no references to `LogLevel.` in the codebase. This is dead code that adds confusion.

**Evidence:**
- `src/mko_telebot/core/channels.py:11-20`: `LogLevel` enum definition
- `src/mko_telebot/core/__init__.py:7`: Exported via `__all__`
- No code references `LogLevel.` anywhere in the codebase

**Recommendation:** Either remove `LogLevel` entirely since it's unused, or add documentation explaining its intended purpose if it's meant for future use. Currently it appears to be dead code.

### CFG-003: Type safety warnings in config.py and channels.py

| Field | Value |
|-------|-------|
| **ID** | CFG-003 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/core/config.py`, `src/mko_telebot/core/channels.py` |
| **Classification** | advisory |

**Description:** The `basedpyright` type checker reports 37 warnings for type safety issues in configuration modules. These include missing type annotations on class attributes, use of `Any` types, and implicit string concatenation. While tests pass, these indicate maintainability issues.

**Evidence:**
- `src/mko_telebot/core/config.py:122-124`: Unannotated class attributes `config_path`, `secrets_path`, `log_config_path`
- `src/mko_telebot/core/config.py:50,78,179`: Explicit `Any` type usage
- `src/mko_telebot/core/channels.py:121`: Unused result from channel validation
- `src/mko_telebot/core/telethon.py:60,162,195`: Implicit string concatenation

**Recommendation:** Add explicit type annotations to class attributes, reduce use of `Any` types by using proper typing, and fix implicit string concatenations.

### CFG-004: ConfigError message doesn't guide user to run init

| Field | Value |
|-------|-------|
| **ID** | CFG-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/config.py`, `src/mko_telebot/core/errors.py` |
| **Classification** | advisory |

**Description:** When a configuration file is missing, `ConfigError` is raised with only the file path. The error message does not guide users to run `mko-telebot init` to create the configuration files, which is the documented resolution path. This degrades user experience for newcomers.

**Evidence:**
- `src/mko_telebot/core/config.py:46`: `raise ConfigError("Configuration file not found", path=path)`
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
- CFG-003: Fix type safety warnings (class attribute annotations, Any types, implicit string concatenation)
- CFG-004: Improve ConfigError message to guide users to run init

## Doc Updates Needed

- CFG-002: If `LogLevel` is removed, update documentation references