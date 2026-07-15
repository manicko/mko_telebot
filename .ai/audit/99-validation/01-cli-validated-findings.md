# Phase 01 Validated Audit Report — CLI Entry Point & Command Layer

**Source Findings:** `.ai/audit/01-cli/findings.md`
**Validation Date:** 2026-07-15
**Validator:** validator agent

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 5 | CLI-001, CLI-002, CLI-003, CLI-004, CLI-005 |
| Reclassified | 1 | CLI-006: BEST-PRACTICE → SPEC-DEVIATION |
| Rejected | 1 | CLI-007 |
| Merged | 0 | — |

---

## Approved Findings

### CLI-001: `run` reports silent success when Telegram auth fails

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `src/mko_telebot/monitor_client.py:89-92` — Confirmed: `start_client()` returns `False` on auth failure
- `src/mko_telebot/monitor.py:139-146` — Confirmed: `if await start_client(...)` has no `else` branch; function falls through returning `None`
- `src/mko_telebot/cli.py:97-99` — Confirmed: `asyncio.run(run_monitor(...))` result is never inspected

**Architectural Impact:** HIGH — Silent failure violates the "meaningful exit codes" requirement in the project rules. Users cannot distinguish between successful startup and authentication failure without checking log files.

**Recommendation stands:** `run_monitor()` should raise `MkoTelebotError` when `start_client` returns `False`, and CLI should surface this to the user with non-zero exit.

---

### CLI-002: Overly narrow exception handling lets raw tracebacks escape `run`

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `src/mko_telebot/cli.py:97-105` — Confirmed: Only catches `MkoTelebotError` and `KeyboardInterrupt`
- `src/mko_telebot/monitor_client.py:75-92` — Confirmed: Only wraps `TelegramAuthError`/`TelegramServiceError`

**Project Rule Violation:** Conflicts with "never leak raw tracebacks to the user" requirement in agent guidelines. Telethon can raise `ConnectionError`, `OSError`, `asyncio.TimeoutError`, and various `telethon.errors.*` that propagate as unhandled exceptions.

**Recommendation stands:** Wrap `asyncio.run()` body in broad exception handler that maps to user-friendly messages.

---

### CLI-003: `init` and `version` can leak raw tracebacks on edge-case errors

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `src/mko_telebot/cli.py:52-64` (`init`) — Confirmed: No `try/except` around `dst.mkdir()` or `shutil.copy2()`
- `src/mko_telebot/cli.py:130-131` (`version`) — Confirmed: No `try/except` around `pkg_version("mko-telebot")`

**Project Rule Violation:** Inconsistent with `validate` command which catches `ConfigError`, and violates "no raw tracebacks leak" rule.

**Recommendation stands:** Add defensive error handling to both commands.

---

### CLI-004: Fire-and-forget tasks swallow `process_task` exceptions; channels die silently

| Field | Value |
|-------|-------|
| **ID** | CLI-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `src/mko_telebot/monitor.py:68` — Confirmed: `asyncio.create_task(reschedule_task(task, queue))` result unused
- `src/mko_telebot/monitor.py:126` — Confirmed: `asyncio.create_task(process_and_reschedule(...))` fire-and-forget pattern
- `src/mko_telebot/monitor_forward.py:235-237` — Confirmed: `TelegramServiceError` raised from `_fetch_messages()` on RPCError

**Architectural Impact:** HIGH — Silent channel monitoring failures compromise operational reliability. Process supervisors cannot detect partial failures.

**Recommendation stands:** Tasks should have exception handling or tracking to surface failures.

---

### CLI-005: `run` exits 0 on KeyboardInterrupt

| Field | Value |
|-------|-------|
| **ID** | CLI-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Status** | **VALIDATED** |

**Evidence Verified:**
- `src/mko_telebot/cli.py:100-102` — Confirmed: `raise typer.Exit(code=0)` on `KeyboardInterrupt`

**Analysis:** While exit code 0 is conventional for successful runs, Unix convention uses 128+signal (130 for SIGINT) to distinguish intentional interruption. This aids process supervisors in detecting incomplete runs.

**Recommendation stands:** Minimal change with clear operational value.

---

### CLI-006: Type-checker warnings on the CLI layer

| Field | Value |
|-------|-------|
| **ID** | CLI-006 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Status** | **RECLASSIFIED** (was BEST-PRACTICE) |

> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** Type-check warnings indicate untyped code flowing into typed boundaries, violating the project's `Type Safety Everywhere` rule. The `Any` in `logging.py:39` and lack of type stubs for `telethon` propagate `Any` into call sites, reducing type safety guarantees.
> - **See also:** Project rules: "Type Safety Everywhere" and python-code-standards.md

**Evidence Verified:** Confirmed 15 warnings from `uv run basedpyright`:
- `reportCallInDefaultInitializer` — Typer pattern (benign)
- `reportExplicitAny` — `dict[str, Any]` in logging.py
- `reportMissingTypeStubs` — telethon package
- `reportUnusedCallResult` — fire-and-forget tasks (also CLI-004)
- `reportAny` / `reportUnknownVariableType` — dynamic `getattr` on telethon objects

**Architectural Impact:** MEDIUM — Type safety erosion undermines maintainability guarantees.

---

### CLI-007: `init` silently skips subdirectories in the template settings dir

| Field | Value |
|-------|-------|
| **ID** | CLI-007 |
| **Severity** | LOW |
| **Type** | ~~SPEC-DEVIATION~~ [REJECTED] |
| **Status** | **REJECTED** |

> **Rejection reason:** Investigation of `src/mko_telebot/settings/` shows the template directory contains only flat YAML files (`config.yaml`, `telethon_config.yaml`, `log_config.yaml`, `keyw_config_example_keep.yaml`). There are no subdirectories in the current template structure. The silent `continue` on `not item.is_file()` is intentional design for flat config files. Adding recursive copy logic or warnings would introduce overengineering without current ROI. No spec requires subdirectory support.

---

## Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| CLI-007 | `init` silently skips subdirectories | Template settings are flat; subdirectory support not required; would add unnecessary complexity |

## Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| CLI-006 | BEST-PRACTICE | SPEC-DEVIATION | Type-safety warnings violate explicit project rule; not optional best-practice |

## Rollout Safety

No cross-phase conflicts detected. The four mandatory fixes (CLI-001 through CLI-004) are independent and can be implemented in any order. CLI-005 and CLI-006 are advisory/low-severity.

## Required Fixes

- **CLI-001** (HIGH): `run` must report and exit non-zero when Telegram auth fails
- **CLI-002** (MEDIUM): Broaden exception handling in `run`/`start_client`
- **CLI-003** (MEDIUM): Add error handling to `init` and `version` commands
- **CLI-004** (MEDIUM): Add exception handling/tracking for fire-and-forget tasks