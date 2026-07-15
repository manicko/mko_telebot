# mko_telebot — Consolidated Audit Findings Report

**Pipeline:** Multi-agent audit (executor → validator per phase)
**Date:** 2026-07-15
**Phases executed:** 9 (01–09) + validation phase 99
**Auditor/Validator model:** `poolside/laguna-m.1:free`
**Scope:** `src/mko_telebot/` (CLI, core/, settings/) + docs/

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Phases completed | 9 / 9 |
| Raw validated findings | 35 |
| Distinct findings (after consolidation) | 31 |
| Rejected findings | 8 |
| Merged (retired into another) | 2 (DF-004, QLT-007) |

### Severity breakdown (distinct)

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 5 |
| MEDIUM | 14 |
| LOW | 12 |

> Note: Two HIGH raw entries (SRV-001, DF-001) share one root cause (channel dropped on untracked exception); counted once in "distinct". 5 mandatory fixes are required before production deployment.

### Phase completion

| # | Phase | Findings (validated) | Rejected | Status |
|---|-------|----------------------|----------|--------|
| 01 | CLI | 6 | 1 (CLI-007) | ✅ |
| 02 | Config | 2 | 1 (CFG-002) | ✅ |
| 03 | Services | 6 | 0 | ✅ |
| 04 | Security | 3 | 0 | ✅ |
| 05 | Integrations | 5 | 1 (INT-006) | ✅ (re-run) |
| 06 | Data Flow | 3 | 2 (DF-005, DF-006) | ✅ |
| 07 | Tests | 3 | 1 (TST-004) | ✅ (re-run) |
| 08 | Quality | 7 | 0 | ✅ |
| 09 | Structural Quality | 0 | 2 (STR-001, STR-002) | ✅ (no defects) |

---

## Mandatory Fixes (HIGH — required before deployment)

- **M1 — Silent monitoring failure (SRV-001 / DF-001).** A transient `RPCError`/`TelegramServiceError` in `process_task` (launched via untracked `asyncio.create_task`) makes the channel exit before `reschedule_task`, so it is **permanently dropped** and silently stops being monitored. `monitor_forward.py:235` raises `TelegramServiceError`; `monitor.py:57-68,126` never catches it.
- **M2 — Forwarding silently disabled (CFG-001).** `ChannelsConfig.apply_defaults_to_channels` (`core/channels.py:124-128`) unconditionally overwrites per-channel `keywords`/`forward_to` with the `defaults` list. With the shipped template's empty `forward_to: []`/`keywords: []`, **every channel loses its forwarding targets on load**.
- **M3 — Auth failure crashes process / not caught (INT-001).** `start_client()` catches `TelegramAuthError`/`TelegramServiceError`, but Telethon's `client.start()` raises only Telethon exception types. Real failures (bad credentials, unreachable API, 2FA) crash the whole process. Tests inject the wrong exception types, masking the bug.
- **M4 — Silent success on auth failure (CLI-001).** `start_client()` returns `False`, `run_monitor()` returns `None`, and `cli.py` never inspects the result → exit code 0 despite monitor never starting.
- **M5 — Permanent message loss (DF-002).** Messages that fail to forward are still marked processed: `process_task` advances `last_msg_id` and state is saved regardless of delivery success; `forward_to_users` only logs failure. The next cycle skips `id ≤ last_msg_id`, **permanently losing the post and all higher-id posts** in that batch.

---

## Detailed Findings — HIGH

### H1 — Channel permanently dropped on exception in `process_task`  `SRV-001`, `DF-001`
- **Severity:** HIGH · **Type:** RUNTIME-ERROR · **Status:** VALIDATED (mandatory)
- **Modules:** `src/mko_telebot/monitor.py:57-68,126`; `monitor_forward.py:230-237`
- **Evidence:** `process_task` runs inside an untracked `asyncio.create_task`; on `TelegramServiceError` (raised at `monitor_forward.py:235` for non-flood RPC errors) the coroutine exits before `reschedule_task`, removing the channel from the queue. Only a "Task exception never retrieved" warning is logged.
- **Fix:** Wrap `process_task` in `try/except` and reschedule in `finally`. Track spawned tasks.

### H2 — Per-channel defaults overwrite explicit `keywords`/`forward_to`  `CFG-001`
- **Severity:** HIGH · **Type:** SPEC-DEVIATION · **Status:** VALIDATED (mandatory)
- **Modules:** `src/mko_telebot/core/channels.py:113-136` (`apply_defaults_to_channels`)
- **Evidence:** Validator unconditionally applies `default_factory` list values; `merged_data.update(...)` overwrites explicit channel values. Shipped `config.yaml` `defaults: keywords: [], forward_to: []` zeroes every channel → forwarding disabled. Test `test_explicit_overrides_preserved` only covers scalar fields.
- **Fix:** Distinguish "not specified" from "explicitly empty"; preserve non-empty per-channel list values. Add list-override tests.

### H3 — `start_client()` catches wrong exception types; real failures crash process  `INT-001`
- **Severity:** HIGH · **Type:** RUNTIME-ERROR · **Status:** VALIDATED (mandatory)
- **Modules:** `src/mko_telebot/monitor_client.py:75-92`
- **Evidence:** `except (TelegramAuthError, TelegramServiceError)` never triggers because Telethon raises its own hierarchy (`RPCError`, `ValueError`, `OSError`). Real auth failures propagate as raw tracebacks. `tests/test_monitor.py:273-287` feed wrong exception types, masking the bug.
- **Fix:** Map real Telethon exceptions to project errors (or catch the Telethon hierarchy) so auth failures return `False`. Fix the tests to assert real behavior.

### H4 — `run` reports silent success on Telegram auth failure  `CLI-001`
- **Severity:** HIGH · **Type:** SPEC-DEVIATION · **Status:** VALIDATED (mandatory)
- **Modules:** `src/mko_telebot/cli.py:97-99`; `monitor.py:139-146`
- **Evidence:** `start_client()` returns `False`; `run_monitor()` has no `else` and returns `None`; `asyncio.run(...)` result is never inspected → process exits 0.
- **Fix:** `run_monitor()` raises `MkoTelebotError` when `start_client` returns `False`; CLI surfaces a non-zero exit.

### H5 — Failed forwards still marked processed → permanent message loss  `DF-002`
- **Severity:** HIGH · **Type:** RUNTIME-ERROR · **Status:** VALIDATED (flagged by Phase 06; distinct data-loss)
- **Modules:** `src/mko_telebot/monitor.py` (`process_task`); `monitor_forward.py` (`forward_to_users`)
- **Evidence:** `last_msg_id` is advanced and state saved even when all forwards fail; `forward_to_users` only logs the failure. Next cycle skips `id ≤ last_msg_id`, losing the post and all higher-id posts in the batch. Reproduced: `last_msg_id = 500` despite all forwards failing.
- **Fix:** Advance `last_msg_id` / save state only after confirmed successful delivery; on failure, keep state and retry.

---

## Detailed Findings — MEDIUM

### M-A — Untracked fire-and-forget `asyncio.create_task` (consolidated)  `SRV-002`, `CLI-004`, `INT-004`, `QLT-007`, `DF-004`
- **Severity:** MEDIUM · **Type:** BEST-PRACTICE · **Status:** VALIDATED (merged)
- **Modules:** `monitor.py:68,126,144-145`
- **Evidence:** Tasks spawned via `asyncio.create_task` are not referenced, have no done-callback, and are not awaited on shutdown. Exceptions surface only as "Task exception was never retrieved".
- **Fix:** Maintain a set of spawned tasks; attach exception handlers; await with timeout on shutdown.

### M-B — Captionless media-only posts silently dropped  `SRV-003`, `DF-003`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED (mandatory)
- **Modules:** `monitor_forward.py:181-184` (`process_messages`)
- **Evidence:** `if msg_text and (...)` skips when `msg_text == ""`. Contradicts `docs/00-overview/overview.md:81,88` ("media forwarded intact", "even when the body text is empty"). No test covers media-only with empty keywords.
- **Fix:** Forward captionless media when `keywords` is empty: `(msg_text and keyword_match) or (content["media"] and not task.keywords)`.

### M-C — `search_match` swallows all errors, silently disables bad keywords  `SRV-004`, `QLT-001`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED (mandatory)
- **Modules:** `matcher.py:172-183`; `monitor_forward.py:184`
- **Evidence:** Broad `except Exception` returns `False` after logging. Violates "never silently swallow errors". Misconfigured keywords silently fail to match.
- **Fix:** Validate keyword syntax at config load (`ConfigError`); remove the broad `except` or re-raise.

### M-D — Overly narrow exception handling leaks raw tracebacks  `CLI-002`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED
- **Modules:** `cli.py:97-105`; `monitor_client.py:75-92`
- **Evidence:** `run` catches only `MkoTelebotError`/`KeyboardInterrupt`; Telethon/OS exceptions escape as raw tracebacks, violating the no-raw-tracebacks rule.
- **Fix:** Wrap `asyncio.run()` body in a broad handler mapping to user-friendly messages.

### M-E — `init` / `version` can leak raw tracebacks  `CLI-003`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED
- **Modules:** `cli.py:52-64` (`init`), `cli.py:130-131` (`version`)
- **Evidence:** No `try/except` around `dst.mkdir()`/`shutil.copy2()`/`pkg_version()`. Inconsistent with `validate` which catches `ConfigError`.
- **Fix:** Add defensive error handling to both commands.

### M-F — `init --force` overwrites user Telegram credentials  `SEC-001`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED
- **Modules:** `cli.py:57-65` (iterates all `settings/` files and copies to user dir)
- **Evidence:** `telethon_config.yaml` (with real credentials) is copied over, destroying the user's secrets and invalidating the session. Docs do not warn of irreversible loss.
- **Fix:** Exclude `telethon_config.yaml` from `--force` overwrite, or document the credential-loss risk explicitly.

### M-G — `build_sender_tag()` fallback unreachable (wrong exception type)  `INT-002`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED
- **Modules:** `monitor_forward.py` (`build_sender_tag`)
- **Evidence:** `except TelegramServiceError` never catches real `get_sender()` errors → empty-sender fallback is dead.
- **Fix:** Catch real Telethon exception types so the fallback executes.

### M-H — `_send_with_retry()` retries permanent `RPCError` subclasses  `INT-003`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED
- **Modules:** `monitor_forward.py` (`_send_with_retry`)
- **Evidence:** All `RPCError` subclasses retried, including permanent ones (banned, peer-invalid, dead session) → wasted backoff, dead sessions never surfaced.
- **Fix:** Classify `RPCError` subclasses; retry only transient ones.

### M-I — Unreachable `except TelegramServiceError` in `_fetch_messages()`  `INT-005`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED (reclassified)
- **Modules:** `monitor_forward.py:230-241`
- **Evidence:** `except RPCError` immediately re-raises `TelegramServiceError`; the following `except TelegramServiceError` is unreachable dead code.
- **Fix:** Remove the unreachable branch; let `monitor.py:117` handle uniformly.

### M-J — `ChannelConfig.name` path-traversal validator untested  `TST-001`
- **Severity:** MEDIUM · **Type:** BEST-PRACTICE · **Status:** VALIDATED
- **Modules:** `core/channels.py:43-51`; `tests/test_config_reader.py`
- **Evidence:** Validator rejects `/`, `\`, `..` (name feeds filesystem paths via `task.py:127`), but no regression test exists (only `ClientConfig.session` is tested).
- **Fix:** Add parametrized cases for traversal characters; assert `"@chan"` accepted.

### M-K — `extra="forbid"` schema strictness untested  `TST-002`
- **Severity:** MEDIUM · **Type:** BEST-PRACTICE · **Status:** VALIDATED
- **Modules:** `core/models.py`, `core/channels.py`, `core/telethon.py`
- **Evidence:** Every config model sets `extra="forbid"` but no test asserts unknown keys are rejected.
- **Fix:** Add tests asserting `ValidationError` on unexpected top-level keys.

### M-L — Property-based matcher tests assert only "no crash"  `TST-003`
- **Severity:** MEDIUM · **Type:** BEST-PRACTICE · **Status:** VALIDATED
- **Modules:** `tests/test_parser.py:565-582`
- **Evidence:** `try/except Exception: pytest.fail` + `isinstance(result, bool)` cannot detect incorrect matching; broad `except` hides minimal counterexamples.
- **Fix:** Add meaningful invariants; remove broad `except`.

### M-M — Parser uses raw string token types instead of `StrEnum`  `QLT-002`
- **Severity:** MEDIUM · **Type:** SPEC-DEVIATION · **Status:** VALIDATED
- **Modules:** `parser.py:57-58,67,112,165`
- **Evidence:** String-literal token types (`"TERM"`, `"OR"`, `"EXCLUDE"`, `"GROUP_START"`) violate the project's "StrEnum only" rule.
- **Fix:** Introduce `TokenType(StrEnum)` and use consistently.

### M-N — Untyped Telethon dependency causes `Any`/`Unknown` leakage  `QLT-004`
- **Severity:** MEDIUM · **Type:** BEST-PRACTICE · **Status:** VALIDATED
- **Modules:** `task.py`, `monitor_forward.py`, `monitor_client.py`, `telethon.py`
- **Evidence:** Telethon ships no `py.typed` marker; 78 basedpyright warnings stem from missing stubs and explicit `Any`.
- **Fix:** Introduce a typed boundary module wrapping Telethon calls.

---

## Detailed Findings — LOW

| ID | Title | Module | Note |
|----|-------|--------|------|
| CLI-005 | `run` exits 0 on `KeyboardInterrupt` | `cli.py:100-102` | Use 130 for SIGINT per Unix convention. |
| CLI-006 | Type-checker warnings on CLI layer | `logging.py`, telethon stubs | 15 warnings; reclassified SPEC-DEVIATION (Type Safety Everywhere). |
| SEC-002 | Stray `test.session` in repo root | repo root | 28 KB auth DB artifact; remove (already gitignored). Reclassified SPEC-DEVIATION. |
| SEC-003 | No file-permission hardening on credentials | `cli.py`, `config.py` | Add `0600`/`0700` for POSIX multi-user safety. |
| CFG-003 | Logger names in docs mismatch real hierarchy | `docs/11-guides/configuration.md` | `__main__`/`telebot` vs `mko_telebot.*`; code works via `root`. DOC-UPDATE. |
| SRV-005 | Type-safety degradation in service layer | `monitor_forward.py` | Explicit `Any` in message pipeline. |
| SRV-006 | Unused `Task.__init__(last_msg_id=...)` seed | `task.py:48,63` | Parameter always overwritten by `load_state()`. |
| QLT-003 | Unreachable `None` guard in `parse_query` | `parser.py:184-202` | Signature already enforces `str`; remove guard or widen to `str \| None`. Reclassified SPEC-DEVIATION. |
| QLT-005 | Implicit string concatenation (basedpyright) | `telethon.py`, `monitor_forward.py` | Wrap multi-line f-strings in parentheses. |
| QLT-006 | `Task.set_offset_date` silently ignores invalid `history_days` | `task.py:146-153` | Silent `offset_date=None` disables date filter; raise `ConfigError`. Reclassified SPEC-DEVIATION. |
| QLT-008 | `PathResolver` unused (dead) and duplicates `config.resolve_path` | `paths.py:27-76` | Remove or wire in. |
| TST-005 | Audit phase spec references non-existent components | `.kilo/commands/audit/phases/07-audit-tests.md` | `PostProcessor`/`ImageCache`/`TelegramPoster`/`GSheetsReader` are stale; update table. DOC-UPDATE. |

---

## Rejected Findings (excluded from merge)

| ID | Phase | Reason |
|----|-------|--------|
| CLI-007 | 01 | Settings template is flat; subdirectory copy not required (overengineering). |
| CFG-002 | 02 | `keyw_config_example_keep.yaml` is an intentional documented example. |
| INT-006 | 05 | 2FA requirement inherent to Telethon; README documents limitation; depends on INT-001. |
| TST-004 | 07 | Test file organization is an architectural preference, not a defect (negative ROI). |
| STR-001 | 09 | `msg_text` carries pre-aggregated album text; deriving would break album handling. |
| STR-002 | 09 | `channel_name` provides essential log context; low-complexity function. |
| DF-005 | 06 | Skipping ambiguous forward targets is deliberate safety design; no proven harm. |
| DF-006 | 06 | Global-lock parallelism is speculative; Avoid Overengineering. |

## Merged (retired into another finding)

| Retired ID | Consolidated Into | Rationale |
|------------|-------------------|-----------|
| DF-004 | SRV-002 (M-A) | Same fire-and-forget root cause. |
| QLT-007 | SRV-002 (M-A) | Same fire-and-forget root cause. |

---

## Validation Notes & Data-Integrity

- **Phase 05 re-run:** The Phase 05 executor produced an incomplete findings file on the first two attempts (only INT-005/INT-006 detailed blocks persisted while the summary referenced INT-001..006, including a HIGH mandatory fix). The orchestrator reconstructed the complete findings file from the executor's verified result text and re-validated it; all six findings are now validated (INT-006 rejected).
- **Phase 07 re-run:** The first Phase 07 executor returned an empty result with no file. Re-run succeeded (TST-001..003 validated; TST-004 rejected; TST-005 reclassified).
- **Phase 09:** No defects found — both findings (STR-001, STR-002) rejected by validator; structural quality confirmed excellent (all functions rank A/B on CC, all files rank A on MI, max function 47 lines, max nesting 3, no god modules).
- All 9 validation reports are present in `.ai/audit/99-validation/`.

---

## Recommended Remediation Order

1. **M2 (CFG-001)** — unblocks core forwarding feature immediately.
2. **M1 (SRV-001/DF-001) + M-A (SRV-002)** — supervised task lifecycle; stops silent channel loss.
3. **M5 (DF-002)** — prevent permanent message loss on forward failure.
4. **M3 (INT-001) + M4 (CLI-001) + M-D/M-E (CLI-002/003)** — correct, user-visible error handling.
5. **M-B (SRV-003) + M-C (SRV-004/QLT-001)** — align forwarding behavior with docs; fail-fast on bad keywords.
6. **Security (M-F SEC-001, SEC-002, SEC-003)** — protect credentials.
7. **Integrations (M-G/M-H/M-I: INT-002/003/005)** — correct Telethon exception mapping.
8. **Tests (M-J/M-K/M-L: TST-001/002/003)** + **Quality (M-M/M-N: QLT-002/004)** + LOW items.

