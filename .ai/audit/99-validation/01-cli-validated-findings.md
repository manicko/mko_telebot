# Phase 01 Validation Report — CLI Entry Point & Command Layer

**Source:** `.ai/audit/01-cli/findings.md`
**Validator:** validator
**Mode:** `problems_only = TRUE` — only findings with validation problems (reclassification, scope gaps, rejections, merges, new issues) are reported. Findings that validate cleanly with no issues are omitted.

---

## Validation Method

Each finding was verified against the current implementation in `src/mko_telepost/`:

1. **CLI-001** — grep across `src/` for `basicConfig|dictConfig|fileConfig|load_logging_config` callers; runtime check of root logger handlers; review of `app.py` error paths.
2. **CLI-002** — grep across `src/` for `mko init` and `mko-telepost init`; full read of `__init__.py`, `paths.py`, `config_reader.py`, `init_service.py`.
3. **CLI-003** — review of `app.py` `config` command (lines 228-265) and `core/paths.py` `user_settings_dir` property.

---

## Cross-Finding Analysis

- **Same root cause:** none. The three findings are independent.
- **Conflicting evidence:** none. The Runtime Verification Record is internally consistent.
- **Dependency chains:** none. Each finding can be fixed independently. CLI-001 (logging) does not depend on CLI-002 (command name) or CLI-003 (table width), and vice versa.
- **No cross-phase conflicts** detected against the evidence presented.

---

## Findings With Validation Problems

### CLI-002: User-facing code references wrong command name (mko init vs mko-telepost init) [CODE-FIX-NEEDED]

> **Code fix required.** The following 5 source locations in `.py` files reference the non-existent `mko` command:

1. `src/mko_telepost/__init__.py:5-8` — module docstring Usage block (4 references)
2. `src/mko_telepost/core/config_reader.py:74` — `ConfigError` message
3. `src/mko_telepost/core/init_service.py:5` — module docstring
4. `src/mko_telepost/core/paths.py:61` — `PathResolver.ensure_dir` docstring

**Verdict:** Code lags behind documentation. The CLI entry point (`app.py`) correctly registers `mko-telepost`. Documentation references in `.py` files must be updated to match. All documentation-only findings have been removed from this audit report.

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| CLI-002 | SPEC-DEVIATION | SPEC-DEVIATION (scope expanded) | Type unchanged; finding kept but `Affected Modules` and `Recommendation` must be extended to cover `__init__.py:5-8` (4 wrong refs) and `paths.py:61` (1 wrong ref) in addition to the original 2 locations. |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| — | — | None rejected. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | None merged. |

---

## Required Fixes

1. **CLI-001** — Configure logging at CLI startup (load `log_config.yaml` via `TelepostConfigReader.load_logging_config()`, fall back to `logging.basicConfig()`) so `logger.exception()` does not leak tracebacks to stderr and the "Check logs for details." message points at a real log file. *(Unchanged from source finding.)*
2. **CLI-002 [CODE-FIX-NEEDED]** — Replace `mko ` → `mko-telepost ` in **all 5 locations**: `__init__.py:5-8`, `core/config_reader.py:74`, `core/init_service.py:5`, `core/paths.py:61`. Do not execute the fix limited to the 2 originally listed files — that would leave the package entry-point docstring and `paths.py` still incorrect.

## Advisory Recommendations

1. **CLI-003** — Set `overflow="fold"` (or widen/weight the Path column) on the `config` command's `Table` so `USER_DIR` and `user_settings_dir` remain visually distinct on narrow terminals. *(Unchanged from source finding.)*
2. **Audit-process** — Auditor should run repo-wide greps for command-name tokens; the CLI-002 scope gap indicates the search was file-targeted rather than token-targeted.
