# Phase 08 Audit Findings — Code Quality, Security & Maintainability

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Runtime Verification Summary

- **Ruff** (`uv run ruff check src`): All checks passed — no unused imports, no unused variables, no print statements in production code.
- **basedpyright** (`uv run basedpyright src`): **0 errors, 78 warnings** (0 notes). The warnings are concentrated in the Telethon-dependent layer and in the parser.
- **Pytest** (`uv run pytest`): **353 passed, 0 failed** in 11.83s.
- **Security scan:** No hardcoded secrets (API keys/tokens/passwords) found in source. No `print()` in production code (all Rich `console.print()` are confined to `cli.py`, as permitted). No bare `except:`. No credential values logged.

> Note: per `problems-only` mode, only the findings below are documented. Passing checks (ruff clean, tests green, no secrets, no bare except, `logger` pattern present in every module) are intentionally omitted.

---

## Findings

### QLT-001: `matcher.search_match` swallows all exceptions and returns `False`

| Field | Value |
|-------|-------|
| **ID** | QLT-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/matcher.py` |
| **Classification** | mandatory |

**Description:** `search_match()` wraps the entire parse+evaluate call in a broad `except Exception as e:` that logs and then returns `False` unconditionally (`matcher.py:172-183`). This masks genuine errors as "no match". In particular, `parse_query()` deliberately raises `ValueError` for an empty or invalid keyword (`parser.py:198-202`), and `evaluate_query`/`patterns_for_node` can raise on malformed patterns. A broken keyword in the user's config therefore silently never matches — the operator sees no match and no actionable error, only a traceback buried in debug logs.

**Evidence:**
```python
# matcher.py:172-183
try:
    inclusions, exclusions = parse_query(query)
    return evaluate_query(text, inclusions, exclusions)
except Exception as e:
    logger.exception(f"Error while evaluating search_match for query '{query}': {e}")
    return False
```
This directly violates the project rule: *"Never silently swallow errors."* `search_match` is the hot path invoked per message per keyword (`monitor_forward.py:184`), so a single misconfigured keyword degrades matching cluster-wide without surfacing.

**Recommendation:** Stop treating parse/validation failures as "no match". Distinguish:
- Recoverable runtime errors (e.g. transient) → keep `logger.exception` but consider re-raising or returning a typed `MatchResult` rather than a bare `bool`.
- Configuration errors from `parse_query` (`ValueError`) → surface as a `ConfigError`/validation failure at load time (validate each keyword when the channel config is built), not per-message.

**Effort:** small. **Priority:** recommended (mandatory per project error-handling rule).

---

### QLT-002: Parser uses raw string token types instead of `StrEnum`

| Field | Value |
|-------|-------|
| **ID** | QLT-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | advisory |

**Description:** The `PatternParser` tokenizer emits and the parser compares raw string literals for token types: `"GROUP_START"`, `"GROUP_END"`, `"OR"`, `"EXCLUDE"`, `"TERM"` (e.g. `parser.py:57-77`, `80-96`, `112`, `146`, `165`, `172`). The project's stated convention (AGENTS.md, `project.md` rule 10) is *"Fixed values: `StrEnum` only — never plain strings, dicts, or lists for constants."* The codebase already follows this elsewhere (`telethon.ProxyType(StrEnum)`), so this is an internal inconsistency / spec deviation.

**Evidence:**
```python
# parser.py:57-58
if ch == "(":
    tokens.append(("GROUP_START", "("))
# parser.py:165
if tok[0] == "TERM":
```

**Impact:** Stringly-typed tokens are easy to typo (a misspelled `"TERM"` fails silently as a non-matching branch), give no IDE autocomplete, and defeat type checking — exactly the class of bug the project's `StrEnum` rule exists to prevent.

**Recommendation:** Introduce `class TokenType(StrEnum): TERM="TERM"; OR="OR"; EXCLUDE="EXCLUDE"; GROUP_START="("; GROUP_END=")"` and use it for both token emission and comparison. (Per the deviation policy: the code choice is *not* better than the rule — fix the code to comply.)

**Effort:** small. **Priority:** recommended.

---

### QLT-003: Statically unreachable defensive `None` guard in `parse_query`

| Field | Value |
|-------|-------|
| **ID** | QLT-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | advisory |

**Description:** `parse_query(query: str)` declares `query` as `str`, yet guards `if query is None:` (`parser.py:198-199`). basedpyright correctly reports *"Condition will always evaluate to False since the types 'str' and 'None' have no overlap"* and *"Code is unreachable"* (`parser.py:198:8`, `199:9`). The runtime contract (callers may pass `None`) and the static type (`str`) disagree.

**Evidence:** basedpyright output:
```
parser.py:198:8 - warning: Condition will always evaluate to False since the types "str" and "None" have no overlap
parser.py:199:9 - warning: Code is unreachable (reportUnreachable)
```

**Impact:** A latent contract ambiguity. If `None` can truly arrive (defensive coding is reasonable for a public entry point fed by user config), the annotation is wrong and hides a real guard; if `None` can never arrive, the dead branch is misleading. Either widen the annotation to `str | None` or drop the guard.

**Recommendation:** Decide the contract: if `None` is a valid input, change the signature to `query: str | None` (keeping the guard, which then becomes reachable); otherwise remove the guard. Bonus: raise a `ConfigError` instead of a generic `ValueError` so the failure is consistent with the rest of the config layer.

**Effort:** trivial. **Priority:** recommended.

---

### QLT-004: Untyped `telethon` dependency causes pervasive `Any`/`Unknown` leakage

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/task.py`, `src/mko_telebot/monitor.py`, `src/mko_telebot/monitor_client.py`, `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** `telethon` ships no type stubs (`py.typed` absent). basedpyright therefore treats every symbol imported from it as `Unknown` (implicit `Any`), which propagates into the project's own code. This produces the bulk of the 78 warnings and, more importantly, defeats the project's strict type-safety goal in the entire Telegram layer. Confirmed via websearch: pyright treats untyped third-party modules as `Unknown`, and the recommended fix is either custom type stubs for the used subset or a typed boundary — *not* scattered `# pyright: ignore` pragmas (pyright discussion #6243).

**Evidence (selected basedpyright warnings):**
```
task.py:16:6   - Stub file not found for "telethon" (reportMissingTypeStubs)
task.py:165:17 - Type of "state" is partially unknown (Any | dict[Unknown, Unknown])
monitor_forward.py:34:16 - Return type is Any (reportAny)
monitor_forward.py:62:13  - Type of "append" is Any (reportAny)
monitor_client.py:107:25 - Argument type is Any (getattr)
```
Only `core/config.py` applies targeted `# pyright: ignore` pragmas, so typing discipline is inconsistent across the codebase.

**Impact:** `Task`, `forward_to_users`, message/group handling, and entity resolution are effectively untyped. Real signature mistakes (wrong arg, missing attribute) pass the type checker silently. This is the single largest source of the 78 warnings and the weakest link in the "Type safety everywhere" rule.

**Recommendation:** Introduce a thin **typed boundary** module that wraps the Telethon calls actually used (client construction, `get_entity`, `iter_messages`, `send_message`/`send_file`, `get_sender`) and exposes narrow, fully-annotated domain types (e.g. a `ResolvedEntity`/`ForwardTarget` protocol). Keep `Any` contained at that boundary instead of letting it flood the domain layer. Alternatively, author a small `.pyi` stub (pyright can draft it) for the used subset. Configure `reportMissingTypeStubs` consistently rather than per-file.

**Effort:** medium. **Priority:** recommended.

---

### QLT-005: Implicit string concatenation flagged by basedpyright

| Field | Value |
|-------|-------|
| **ID** | QLT-005 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/telethon.py`, `src/mko_telebot/monitor_forward.py` |
| **Classification** | advisory |

**Description:** Several multi-line f-strings rely on implicit adjacent-literal concatenation, which basedpyright flags as `reportImplicitStringConcatenation`. While intentional here, the construct is a known footgun (a missing comma in a list of strings silently merges entries).

**Evidence (basedpyright):**
```
telethon.py:60:21  - Implicit string concatenation not allowed
telethon.py:162:17 - Implicit string concatenation not allowed
telethon.py:195:17 - Implicit string concatenation not allowed
monitor_forward.py:107:17, 115:17, 143:17, 260:13 - Implicit string concatenation not allowed
```
Example (`monitor_forward.py:107-108`):
```python
f"Flood wait {e.seconds}s, retry {attempt + 1}/{max_tries} "
f"for {getattr(target, 'id', target)}"
```

**Impact:** Inconsistent with a clean type-checker run; the pattern obscures a class of real bugs and is the most frequent style warning in the two files.

**Recommendation:** Wrap the multi-line f-string in parentheses (implicit concatenation within a single parenthesized string is allowed) or use explicit `\n` / `str.join`. This also removes the warning noise so genuine issues stand out.

**Effort:** trivial. **Priority:** recommended.

---

### QLT-006: `Task.set_offset_date` silently ignores invalid `history_days`

| Field | Value |
|-------|-------|
| **ID** | QLT-006 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/task.py` |
| **Classification** | advisory |

**Description:** `set_offset_date()` catches `(TypeError, ValueError)` from `int(self.history_days)` and simply `return`s, leaving `self.offset_date = None` (`task.py:146-152`). No log, no error. The result is silent degradation: an invalid `history_days` value causes the scan to run with **no date-window filter** (the `offset_date` guard in `monitor_forward._fetch_messages` becomes `None`), fetching far more history than intended.

**Evidence:**
```python
# task.py:146-153
try:
    days = int(self.history_days)
except (TypeError, ValueError) as e:
    logger.error(f"Invalid history_days for {self.channel_name}/{self.state_file}: {e}")
    return
self.offset_date = datetime.now(UTC) - timedelta(days=days)
```
(Note: a `logger.error` line is present in the snippet but the except branch still swallows and continues — the error is logged yet execution proceeds as if nothing was wrong, which is the silent-degradation problem.)

**Impact:** A misconfigured `history_days` does not fail loudly; instead it changes runtime behaviour (broader fetch window) without operator awareness.

**Recommendation:** Raise a `ConfigError` for an invalid `history_days` (consistent with the rest of the config validation in `telethon.py`/`channels.py`), or at minimum `logger.warning` and document that the date filter is disabled.

**Effort:** trivial. **Priority:** recommended.

---

### QLT-007: Fire-and-forget `asyncio.create_task` without tracking loses failures

| Field | Value |
|-------|-------|
| **ID** | QLT-007 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | advisory |

**Description:** The monitoring loop spawns background tasks via `asyncio.create_task(...)` and discards the returned `Task` handle (`monitor.py:68`, `monitor.py:126`). basedpyright flags these as `reportUnusedCallResult`. More seriously, an unhandled exception inside a detached task is delivered only to the event-loop's exception handler; with no handler configured, the failure is effectively swallowed and the task simply stops rescheduling.

**Evidence:**
```python
# monitor.py:68 (inside process_and_reschedule)
asyncio.create_task(reschedule_task(task, queue))
# monitor.py:126 (inside main_loop)
asyncio.create_task(process_and_reschedule(task, client, queue, lock, settings))
```

**Impact:** Reliability gap — if `reschedule_task` or `process_and_reschedule` raises (e.g. state-save error, unexpected Telethon error not caught internally), the channel silently drops out of the rotation with no surfaced error and no automatic recovery. Hard to diagnose in production.

**Recommendation:** Track the task handles and attach a `add_done_callback` that logs exceptions, or `await`/gather at a supervisor level. At minimum, ensure the loop has an exception handler that logs. This converts silent drops into visible, debuggable failures.

**Effort:** small. **Priority:** recommended.

---

### QLT-008: `PathResolver` class is unused (dead) and duplicates `config.resolve_path`

| Field | Value |
|-------|-------|
| **ID** | QLT-008 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/paths.py` |
| **Classification** | advisory |

**Description:** `PathResolver` is defined (`paths.py:27-76`) and documented in the module docstring (`paths.py:6`), but is referenced nowhere else in the codebase (grep confirms the only matches are its own definition/docstring). Meanwhile `core/config.py` defines a separate `resolve_path()` function with overlapping behaviour (`config.py:27-47`), which *is* used (`config.load_logging_config`).

**Evidence:** grep for `PathResolver` across `src/` returns only:
```
paths.py:6  - PathResolver: Utility class for resolving relative paths ...
paths.py:27 - class PathResolver:
```

**Impact:** Two parallel path-resolution mechanisms exist; one is dead weight and the divergence invites future inconsistency (e.g. differing traversal handling). Per the project's Dead Code Policy this is future-proofing rather than outright dead code — but its purpose should be confirmed.

**Recommendation:** Investigate why `PathResolver` exists. If it is meant to be the canonical resolver, wire it in and remove `config.resolve_path`; if `config.resolve_path` is the chosen approach, remove `PathResolver` (and its docstring line) to avoid duplication. Do **not** delete blindly — confirm intent first.

**Effort:** trivial. **Priority:** recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 4 (QLT-001, QLT-002, QLT-004, QLT-007) |
| LOW | 4 (QLT-003, QLT-005, QLT-006, QLT-008) |

## Mandatory Fixes

- **QLT-001** — Stop masking parse/validation errors as "no match" in `search_match`; surface configuration errors at load time. Violates the project's "never silently swallow errors" rule.

## Advisory Recommendations

- **QLT-002** — Replace raw string token types in the parser with a `TokenType(StrEnum)`.
- **QLT-003** — Reconcile the `query: str` annotation with the `if query is None` guard in `parse_query`.
- **QLT-004** — Introduce a typed boundary (or `.pyi` stubs) around `telethon` to stop `Any`/`Unknown` leaking into the domain layer.
- **QLT-005** — Wrap multi-line f-strings in parentheses to satisfy `reportImplicitStringConcatenation`.
- **QLT-006** — Do not silently ignore invalid `history_days`; raise or warn explicitly.
- **QLT-007** — Track/await background `asyncio` tasks so failures are surfaced instead of dropped.
- **QLT-008** — Resolve the duplicate/unused `PathResolver` vs `config.resolve_path`.

## Doc Updates Needed

None required by this phase. (QLT-002 is a code-vs-convention deviation to be fixed in code, not docs.)
