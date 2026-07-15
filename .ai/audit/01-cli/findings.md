# Phase 01 Audit Findings — CLI Entry Point & Command Layer

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/01-audit-cli.md
**Status:** complete
**Validated:** no

---

## Runtime Verification Summary

| Step | Result |
|------|--------|
| R1 — Import (`mko_telebot.cli`, `main`, `core`) | PASS — `IMPORT OK` |
| R2 — `--help` for all 5 commands (init/validate/run/config/version) | PASS — all render without error |
| R3 — `ruff check` | PASS — 0 issues on CLI-layer files |
| R3 — `basedpyright` | WARN — 0 errors, 15 warnings on CLI-layer files |
| R4 — `pytest` | PASS — 353 passed |

> `problems-only: true` — only problems are documented below.

---

## Findings

### CLI-001: `run` reports silent success when Telegram auth fails

| Field | Value |
|-------|-------|
| **ID** | CLI-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/cli.py` (run), `src/mko_telebot/monitor.py` (run_monitor), `src/mko_telebot/monitor_client.py` (start_client) |
| **Classification** | mandatory |

**Description:** When Telethon authentication fails, `start_client()` returns `False` and `run_monitor()` returns `None` implicitly without raising. The CLI `run()` handler does `asyncio.run(run_monitor(settings, client))` and never inspects the result, so it prints nothing and exits with code `0`. The user receives a misleading "success" while the monitor never started.

**Evidence:**
`src/mko_telebot/monitor_client.py:89-92`:
```python
except (TelegramAuthError, TelegramServiceError) as e:
    logger.error(f"Failed to start Telethon client: {e}")
    return False
```
`src/mko_telebot/monitor.py:139-146` — `if await start_client(...):` has no `else` branch; on `False` the function falls through and returns `None`.
`src/mko_telebot/cli.py:97-105`:
```python
client = create_client(settings)
try:
    asyncio.run(run_monitor(settings, client))
except KeyboardInterrupt:
    ...
except MkoTelebotError as e:
    ...
```
The error is only emitted via `logger.error` (into the log file after `setup_logging()`), so a console-only user sees no failure and a `0` exit code.

**Recommendation:** Make authentication failure a first-class error: have `run_monitor` raise a `MkoTelebotError` (or return a status the CLI checks) when `start_client` returns `False`, and have `run()` print an actionable message (e.g., "Telegram authentication failed — check telethon_config.yaml") and exit non-zero. This restores meaningful exit codes (Audit Dimension 4).

---

### CLI-002: Overly narrow exception handling lets raw tracebacks escape `run`

| Field | Value |
|-------|-------|
| **ID** | CLI-002 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/cli.py` (run), `src/mko_telebot/monitor_client.py` (start_client) |
| **Classification** | mandatory |

**Description:** The CLI rule states "No raw tracebacks leak to the user" and "Custom exceptions from core/errors.py." `run()` only catches `MkoTelebotError` and `KeyboardInterrupt`. `start_client()` only wraps `TelegramAuthError`/`TelegramServiceError`. Telethon can raise other exceptions during `client.start()` (e.g., `ConnectionError`, `OSError`, `asyncio.TimeoutError`, `telethon.errors.*`) that are neither wrapped nor caught, so they propagate out of `asyncio.run()` as a raw Python traceback.

**Evidence:**
`src/mko_telebot/cli.py:97-105` — `except MkoTelebotError` is the only error branch; any non-`MkoTelebotError` raised inside the monitor (network, disk, Telethon) is unhandled.
`src/mko_telebot/monitor_client.py:75-92` — `client.start(...)` is wrapped only in `except (TelegramAuthError, TelegramServiceError)`.

**Recommendation:** Wrap the `asyncio.run(...)` body (or `start_client` call) in a broad `except Exception` that maps to a user-friendly `MkoTelebotError` message plus non-zero exit, while still logging the original traceback via `logger.exception`. This satisfies the "never leak raw tracebacks" rule without silently swallowing errors.

---

### CLI-003: `init` and `version` can leak raw tracebacks on edge-case errors

| Field | Value |
|-------|-------|
| **ID** | CLI-003 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/cli.py` (init, version) |
| **Classification** | mandatory |

**Description:** The `init` and `version` commands have no error handling around operations that can raise non-`MkoTelebotError` exceptions, violating the "no raw tracebacks leak to the user" rule and the inconsistent-error-handling checklist item.

- `init` calls `dst.mkdir(parents=True, exist_ok=True)` and `shutil.copy2(item, target)` with no `try/except`. A permission error, read-only filesystem, or disk-full condition raises `OSError`/`PermissionError` that propagates as a raw traceback.
- `version` calls `pkg_version("mko-telebot")` (`importlib.metadata.version`). If the CLI is executed other than through the installed console script (e.g., `python src/mko_telebot/main.py` from a source checkout without an editable install), `importlib.metadata.PackageNotFoundError` is raised and leaks a raw traceback.

**Evidence:**
`src/mko_telebot/cli.py:52-64` (`init`):
```python
dst.mkdir(parents=True, exist_ok=True)
...
_ = shutil.copy2(item, target)
```
`src/mko_telebot/cli.py:130-131` (`version`):
```python
ver: str = pkg_version("mko-telebot")
console.print(f"mko-telebot version [bold]{ver}[/bold]")
```
Contrast with `validate`/`run`, which do catch `ConfigError`/`MkoTelebotError` — the handling is inconsistent across commands.

**Recommendation:** Wrap `init`'s filesystem operations in `try/except OSError` that prints a friendly message and exits non-zero. For `version`, guard `pkg_version` with `try/except importlib.metadata.PackageNotFoundError` (or read `version` from package metadata defensively) so the command degrades gracefully. This makes error presentation uniform across all commands (Audit Dimension 1 & 4).

---

### CLI-004: Fire-and-forget tasks swallow `process_task` exceptions; channels die silently

| Field | Value |
|-------|-------|
| **ID** | CLI-004 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telebot/monitor.py` (main_loop, process_and_reschedule), `src/mko_telebot/monitor_forward.py` (process_task) |
| **Classification** | mandatory |

**Description:** In the async bridge, tasks are spawned with `asyncio.create_task(...)` and their results are never awaited or referenced. `process_task` is not wrapped in any `try/except`, so any exception it raises (e.g., `TelegramServiceError` from `_fetch_messages`' RPCError branch, or any error from `forward_to_users`) propagates out of `process_and_reschedule` into an unreferenced task. The exception is never retrieved, so Python logs a "Task exception was never retrieved" warning and the failure is swallowed. The CLI `run()` cannot surface it (its `except` only covers the top-level coroutine), so a single failing channel silently stops being monitored while the process keeps running and reports health.

**Evidence:**
`src/mko_telebot/monitor.py:57-68`:
```python
async with lock:
    await process_task(task, client, settings)
    try:
        await task.save_state()
    except StateError as e:
        logger.error("...")
asyncio.create_task(reschedule_task(task, queue))  # result never awaited
```
`src/mko_telebot/monitor.py:126`: `asyncio.create_task(process_and_reschedule(...))` — fire-and-forget, no tracking.
`src/mko_telebot/monitor_forward.py:254-257` — `process_task` calls `await _fetch_messages(...)` which can raise `TelegramServiceError` (line 235) and is not caught here.

**Recommendation:** Either (a) wrap `process_task` work in `process_and_reschedule` with `try/except Exception` that logs and re-arms the task, or (b) keep references to created tasks and await/join them so exceptions are surfaced to the CLI. At minimum, attach a done-callback that logs unhandled exceptions. This prevents silent loss of monitoring for a channel (correctness/operational reliability).

---

### CLI-005: `run` exits 0 on KeyboardInterrupt, masking interruption from automation

| Field | Value |
|-------|-------|
| **ID** | CLI-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/cli.py` (run) |
| **Classification** | advisory |

**Description:** A user-initiated Ctrl+C is handled and exits with code `0` ("Shutdown requested"). For an unattended/monitored deployment, a process that was interrupted (rather than completing successfully) returning `0` can mislead supervisors (systemd, Docker restart policies, cron) into treating the run as successful. Exit codes should distinguish intentional interruption from success.

**Evidence:**
`src/mko_telebot/cli.py:100-102`:
```python
except KeyboardInterrupt:
    console.print("[yellow]Shutdown requested[/yellow]")
    raise typer.Exit(code=0) from None
```

**Recommendation:** Return a non-zero exit code (e.g., `130`, the conventional SIGINT code) on `KeyboardInterrupt` so process supervisors can tell an interrupted run from a clean one. Effort: trivial.

---

### CLI-006: Type-checker warnings on the CLI layer (basedpyright)

| Field | Value |
|-------|-------|
| **ID** | CLI-006 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/cli.py`, `src/mko_telebot/logging.py`, `src/mko_telebot/monitor.py`, `src/mko_telebot/monitor_client.py` |
| **Classification** | advisory |

**Description:** `basedpyright` reports 0 errors but 15 warnings across the CLI/service layer. Notable categories:
- `cli.py:37` — `reportCallInDefaultInitializer`: `typer.Option(False, ...)` is a function call in a default-value expression (inherent to the Typer pattern; benign but flagged).
- `logging.py:39` — `reportExplicitAny` on `dict[str, Any]`.
- `monitor_client.py` / `monitor.py` — `reportMissingTypeStubs` for `telethon` and `reportAny`/`reportUnknownVariableType` from dynamic `getattr`/`sender` access.

The phase defines linter/type-checker warnings as direct evidence. While none are correctness bugs, they reduce type-safety guarantees and signal that `telethon`'s untyped surface is flowing `Any` into the call sites.

**Evidence:** `uv run basedpyright src/mko_telebot/cli.py src/mko_telebot/monitor.py src/mko_telebot/monitor_client.py src/mko_telebot/logging.py` → `0 errors, 15 warnings`.

**Recommendation:** Add a `pyright`/basedpyright config (or pyproject overrides) to (a) acknowledge the Typer default-initializer pattern, and (b) add `telethon` type stubs or `# pyright: ignore` annotations at the `getattr`/`sender` boundaries with explicit `Any`→typed narrowing. This tightens type safety without overengineering. Effort: small.

---

### CLI-007: `init` silently skips subdirectories in the template settings dir

| Field | Value |
|-------|-------|
| **ID** | CLI-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/cli.py` (init) |
| **Classification** | advisory |

**Description:** `init` iterates `src.iterdir()` and copies only entries where `item.is_file()` is true, skipping any subdirectory. If the bundled template settings ever include nested directories (e.g., per-channel defaults), they would be silently omitted. The user then believes `init` succeeded (console shows "Copied N file(s)") while the configuration is incomplete, and only discovers the gap later via a `validate`/`run` failure.

**Evidence:**
`src/mko_telebot/cli.py:57-65`:
```python
for item in src.iterdir():
    if not item.is_file():
        continue
    target: Path = dst / item.name
    ...
    _ = shutil.copy2(item, target)
```

**Recommendation:** Either `shutil.copytree` recursively, or explicitly assert the template dir is flat and log a warning when a subdirectory is skipped, so the omission is visible. Effort: trivial. Dead-code policy note: if subdirectories are intentionally unsupported, document that constraint in `init`'s docstring rather than leaving the silent `continue`.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 3 |

## Mandatory Fixes

- **CLI-001** (HIGH): `run` must report and exit non-zero when Telegram auth fails instead of silent success.
- **CLI-002** (MEDIUM): Broaden exception handling in `run`/`start_client` so non-`MkoTelebotError` Telethon/OS errors don't leak raw tracebacks.
- **CLI-003** (MEDIUM): Wrap `init` filesystem ops and `version` package-metadata lookup to avoid raw tracebacks.
- **CLI-004** (MEDIUM): Stop swallowing `process_task` exceptions in fire-and-forget tasks; surface channel failures.

## Advisory Recommendations

- **CLI-005** (LOW): Use a non-zero exit code (130) on KeyboardInterrupt.
- **CLI-006** (LOW): Reduce basedpyright warnings via config + telethon stubs/annotations.
- **CLI-007** (LOW): Make `init` handle/announce nested template directories.

## Doc Updates Needed

None required for this phase. (No spec-vs-code documentation divergence was identified in the CLI layer; the SPEC's described command set matches the implemented `init/validate/run/config/version` commands.)

---
