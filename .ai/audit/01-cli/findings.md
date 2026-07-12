---
name: 01-cli
description: CLI Entry Point & Command Layer Audit
agent: auditor
status: complete
validated: no
---

# Phase 01 Audit Findings — CLI Entry Point & Command Layer

**Executor:** auditor  
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** complete  
**Validated:** no

---

## Findings

### CLI-001: Package discovery configuration uses wrong pattern in pyproject.toml

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | pyproject.toml, src/mko_telebot |
| **Classification** | advisory |

**Description:** The pyproject.toml uses `include = ["src/*"]` for setuptools package discovery, which is incorrect for a src-layout project. This pattern attempts to include files under `src/` rather than packages. The correct pattern should be `include = ["mko_telebot*"]` to match packages inside the src directory. This caused the module to not be importable via `uv run python -c "from mko_telebot.cli import app"` without manually setting PYTHONPATH.

**Evidence:**
- pyproject.toml line 47: `include = ["src/*"]`
- Command output shows `ModuleNotFoundError: No module named 'mko_telebot'` when importing without PYTHONPATH
- Standard src-layout requires package name in include pattern, not the directory prefix

**Recommendation:**
Change `[tool.setuptools.packages.find]` section in pyproject.toml:
```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["mko_telebot*"]
```
This follows standard src-layout conventions and ensures the package is importable after installation without requiring PYTHONPATH manipulation.

---

### CLI-002: Unused LogLevel StrEnum defined but never referenced in codebase

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | src/mko_telebot/core/channels.py, src/mko_telebot/core/__init__.py |
| **Classification** | advisory |

**Description:** The `LogLevel` StrEnum is defined in channels.py with values DEBUG, INFO, WARNING, ERROR, CRITICAL but is never used anywhere in the codebase. It is exported via `__all__` in core/__init__.py but no consumer references it. This represents either dead code or missing functionality.

**Evidence:**
- channels.py lines 10-17: LogLevel enum definition
- channels.py line 150: LogLevel in __all__
- __init__.py line 7: LogLevel imported and line 21: LogLevel in __all__
- Grep search for `LogLevel\` returns no matches - no usage found

**Recommendation:**
Investigate whether LogLevel was intended for use in logging configuration or if it should be removed. If intended for future use, document its purpose in code comments. If unused, remove to avoid confusion.

---

### CLI-003: Empty __init__.py in package root provides no value

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | src/mko_telebot/__init__.py |
| **Classification** | advisory |

**Description:** The `src/mko_telebot/__init__.py` is empty (0 lines), providing no explicit exports or package-level documentation. While Python accepts this, it's inconsistent with the project's pattern of using explicit `__all__` exports in other modules.

**Evidence:**
- __init__.py file is empty with 0 lines
- No `__all__` defined, no version info, no package metadata

**Recommendation:**
Consider adding minimal package exports (e.g., `__all__ = ["cli"]` to expose the app) or remove the file entirely if not needed.

---

### CLI-004: Redundant main.py wrapper adds unnecessary layer

| Field | Value |
|-------|-------|
| **ID** | CLI-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/main.py |
| **Classification** | advisory |

**Description:** The main.py file (12 lines) provides only a thin wrapper around `app()` with no added functionality. It imports the CLI and calls it, adding no value. The pyproject.toml already defines `mko-telebot = "mko_telebot.cli:app"` as the entry point, making main.py unnecessary.

**Evidence:**
- main.py lines 3-8: Just imports app and calls it
- pyproject.toml line 162: Entry point already points to `mko_telebot.cli:app`
- main.py is not used by any other module

**Recommendation:**
Remove main.py to simplify the codebase. The entry point is already correctly configured to point directly to the Typer app.

---

### CLI-005: setup_logging() unnecessarily instantiates full config reader

| Field | Value |
|-------|-------|
| **ID** | CLI-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/logging.py |
| **Classification** | advisory |

**Description:** The `setup_logging()` function instantiates a full `TelepostConfigReader` with config_file and telethon_config_file paths even though it only needs the log_config_path to configure logging. This triggers unnecessary validation of config.yaml and telethon_config.yaml which may not exist during initial setup.

**Evidence:**
- logging.py lines 33-37: Creates reader with config_path and secrets_path
- Only calls `load_logging_config()` which needs just the log config file
- This can cause confusion during `init` workflow when config files don't exist yet

**Recommendation:**
Refactor `setup_logging()` to directly read only the log_config.yaml file without instantiating the full config reader, or add a dedicated method to TelepostConfigReader that handles just logging config.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 3 |

## Advisory Recommendations

- CLI-001: Package discovery configuration uses wrong pattern in pyproject.toml (MEDIUM priority)
- CLI-002: Unused LogLevel StrEnum defined but never referenced (LOW priority)
- CLI-003: Empty __init__.py in package root provides no value (LOW priority)
- CLI-004: Redundant main.py wrapper adds unnecessary layer (LOW priority)
- CLI-005: setup_logging() unnecessarily instantiates full config reader (LOW priority)

## Doc Updates Needed

- CLI-001: Consider documenting the correct src-layout pattern in project setup instructions
- CLI-002: Document purpose of LogLevel or remove it
- CLI-003: Consider documenting package structure or removing empty __init__.py