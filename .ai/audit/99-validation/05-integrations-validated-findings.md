# Phase 05 Validation â€” External Integrations

**Validator:** validator
**Source findings:** `.ai/audit/05-integrations/findings.md`
**Status:** validated
**problems_only:** true

## Runtime Re-Verification

| Step | Result |
|------|--------|
| Code inspection `telegram_service.py:289-323` | Confirmed `async with client:` â†’ `client.start(**self._make_start_kwargs())` block at lines 305-311 |
| Code inspection `gsheets_reader.py:215-244` | Confirmed `get_sheet_data(spreadsheet_id: str, range_name: str)` required params + dead `or` fallback at lines 243-244 |
| Telethon `__aenter__` source (runtime `inspect.getsource`) | Confirmed: `async def __aenter__(self): return await self.start()` â€” calls `start()` with **no arguments** |
| Cross-phase reference check | SEC-003 (Phase 04) and SRV-005 (Phase 03) target the **same** `async with client:` block at `telegram_service.py:305-315` â€” confirmed sequencing dependency |

---

## Findings

### INT-001: Credentials bypassed by async with client [CODE-FIX-NEEDED] Telegram credentials are bypassed on the auth path â€” `async with client:` calls `start()` with no credentials before `client.start(**creds)` runs

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | mandatory |

**Description:** `TelegramService.run()` authenticates the Telethon client with this block:

```python
async with client:
    await client.start(**self._make_start_kwargs())
```

`TelegramClient.__aenter__` is defined in Telethon as:

```python
async def __aenter__(self):
    return await self.start()
```

It calls `self.start()` with **no arguments** â€” i.e. with the default `phone=lambda: input('Please enter your phone (or bot token): ')` and `bot_token=None`. The configured credentials built by `_make_start_kwargs()` (which selects `phone` vs `bot_token` based on `TelethonConfig.is_user` and reads `phone_or_token.get_secret_value()`) are only passed to the **second** `start()` call, which runs after `__aenter__` has already attempted authentication.

Trace of `_start()` (Telethon) confirms the consequence:

1. **Session already valid** â€” `__aenter__` â†’ `start()` â†’ `me = await self.get_me()` returns the authorized user â†’ returns `self` immediately. The subsequent `client.start(phone=token)` then sees `me is not None`, emits a Telethon warning ("the session already had an authorized user so it did not login to the user account using the provided phone"), and returns. The configured `phone_or_token`/`bot_token` is **never used for login** â€” auth succeeds only because of the pre-existing session file. `_make_start_kwargs()` is effectively dead on this path.

2. **Fresh / expired / corrupted session** (the documented re-auth path) â€” `__aenter__` â†’ `start()` â†’ `get_me()` returns `None` â†’ `bot_token` is `None` â†’ enters `while callable(phone): value = phone()` â†’ invokes the default `input('Please enter your phone (or bot token): ')` lambda. The configured `phone_or_token`/`bot_token` is **never reached**. In the intended non-interactive CLI context, `input()` blocks on stdin or raises `EOFError`, crashing the run. The explicit `client.start(**self._make_start_kwargs())` line is unreachable because `__aenter__` already failed.

This breaks the documented auth contract on both user and bot paths. The CLI is designed to run unattended from config (`TelethonConfig.phone_or_token` is a `SecretStr` precisely so it can be injected non-interactively), and the spec (`docs/SPEC.md:184`) states: *"Access the plaintext value via `.get_secret_value()` when passing to `client.start()`."* That pass is defeated by `__aenter__` running `start()` first.

**Evidence:**

- `src/mko_telepost/core/telegram_service.py:306-315`:
  ```python
  async with client:
      await client.start(**self._make_start_kwargs())
      await self._coordinate_posting(
          client, granges_data, used_cache_files
      )
      self._cleanup_session(session_path)
  ```
- Telethon `TelegramClient.__aenter__` (verified at runtime via `inspect.getsource`):
  ```python
  async def __aenter__(self):
      return await self.start()
  ```
- Telethon `start()` signature: `phone` defaults to `lambda: input('Please enter your phone (or bot token): ')`, `bot_token=None`.
- Telethon `_start()`: when `get_me()` returns `None` and `bot_token` is falsy, it loops `while callable(phone): value = phone()` â€” invoking interactive `input()` before the configured credential is consulted.
- `docs/SPEC.md:184` and `docs/00-overview/overview.md:61` document that `phone_or_token` is passed to `client.start()` â€” the code path that would do so is unreachable on a fresh session.
- Tests mask the bug: `tests/test_telegram_service.py:88-92`, `:159-161`, `:256-258` set `mock_client.__aenter__ = AsyncMock(return_value=mock_client)` and `mock_client.start = AsyncMock()`, so `__aenter__` returns immediately without invoking Telethon's real `start()`. The real credential-flow behavior is never exercised. All 42 tests pass while the production auth path is broken on first run.

**Recommendation:** Do not rely on `async with client:` for the start phase. Replace the block with an explicit start-then-disconnect sequence so the configured credentials are passed to the **first** and only `start()` call:

```python
client = self.poster.create_client()
try:
    await client.start(**self._make_start_kwargs())
    await self._coordinate_posting(client, granges_data, used_cache_files)
finally:
    await client.disconnect()
    self._cleanup_session(session_path)
```

This guarantees `phone`/`bot_token` from `TelethonConfig` reach `_start()` on every run, including fresh sessions, and removes the redundant double-`start()`. Coordinate with prior findings SEC-003 / SRV-005 (which already restructure this same `try` block for session-file hardening and the "Telegram authentication failed" log message) â€” implement together to avoid repeated rewrites of lines 305-315. Add an integration test that asserts `_make_start_kwargs()` values are forwarded to a stubbed `start()` on the unauthorized-session path (the current mocks bypass `start()` entirely, so they cannot catch this regression).

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified against live code and Telethon runtime source. `__aenter__` confirmed to call `self.start()` with no args (runtime `inspect.getsource` returns `return await self.start()`). Production block at `telegram_service.py:305-311` matches the finding verbatim. Test mocks at `tests/test_telegram_service.py:88-92` replace `__aenter__` with an `AsyncMock(return_value=mock_client)` that bypasses real `start()` â€” confirming the regression is masked, not absent. SPEC-DEVIATION classification upheld: spec (`docs/SPEC.md:184`) mandates credential pass to `client.start()`; implementation defeats it via `async with`.
> - **See also:** SEC-003 (Phase 04), SRV-005 (Phase 03), SRV-004 (Phase 03) â€” all four target the identical `async with client:` block at `telegram_service.py:305-315`. See Rollout Analysis.

---
### INT-002: Dead or fallbacks in get_sheet_data ~~DONE — DOC-UPDATE resolved~~ Dead credential-fallback logic in `GSheetsReader.get_sheet_data` — `or` fallbacks never trigger because both parameters are required

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/gsheets_reader.py` |
| **Classification** | advisory |

**Description:** `get_sheet_data` declares both `spreadsheet_id: str` and `range_name: str` as required positional parameters (no defaults), then immediately shadows them with fallback expressions that can never be reached:

```python
def get_sheet_data(
    self,
    spreadsheet_id: str,
    range_name: str,
) -> list[list[Any]]:
    ...
    # Use config values if not provided
    spreadsheet_id = spreadsheet_id or self.config.spreadsheet_id
    range_name = range_name or "Sheet1!A1:Z100"
```

Because `spreadsheet_id` and `range_name` are always supplied by the caller (a non-empty string is truthy, and the model's `spreadsheet_id` field has `min_length=10`), the `or self.config.spreadsheet_id` and `or "Sheet1!A1:Z100"` branches are dead code. The comment `# Use config values if not provided` describes behavior that the signature makes impossible. The sole caller, `TelegramService._fetch_sheet_data`, always passes both arguments explicitly (`telegram_service.py:332-335`), confirming the fallback is unreachable.

This is not a runtime bug, but it is misleading: a reader infers the method supports a "use config defaults" mode that does not exist, and the hardcoded `"Sheet1!A1:Z100"` fallback invents a default range that is not defined anywhere in the config models or spec.

**Evidence:**

- `src/mko_telepost/core/gsheets_reader.py:215-244` — `get_sheet_data` signature (required `spreadsheet_id: str`, `range_name: str`) and the `or` fallback lines at 243-244. Re-verified: signature unchanged, fallbacks present.
- `src/mko_telepost/core/google_sheets_models.py` — `GoogleSheetsConfig.spreadsheet_id` has `min_length=10`, so it is always a non-empty string when valid; no `range_name` default exists in the model.
- `src/mko_telepost/core/telegram_service.py:332-335` — sole call site passes both `self.settings.google_sheets.spreadsheet_id` and `range_name` positionally.
- The docstring example (`reader.get_sheet_data("abc123", "Sheet1!A1:Z100")`) also shows both args as required.

**Recommendation:** Pick one contract and make the code match it. Either (a) drop the dead `or` fallback lines and the `# Use config values if not provided` comment — the method requires both args and that is fine; or (b) if a "default to config" mode is genuinely wanted, make the parameters optional (`spreadsheet_id: str | None = None`, `range_name: str | None = None`) and resolve them from `self.config` inside. Option (a) is simpler and matches the only existing caller. Remove the invented `"Sheet1!A1:Z100"` default regardless — it has no source of truth in the config models or spec. Effort: trivial. Priority: recommended.

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified against live code. Signature at `gsheets_reader.py:215-219` declares both params as required `str` (no defaults). Dead `or` fallbacks confirmed at lines 243-244. Sole caller `_fetch_sheet_data` (`telegram_service.py:337-339`) passes both args positionally. The "dead code" classification is consistent with spec — `docs/SPEC.md` and `GoogleSheetsConfig` define no `range_name` default, so the invented `"Sheet1!A1:Z100"` literal has no source of truth. BEST-PRACTICE / advisory upheld: low-severity, trivial fix, no behavior change.
> - **See also:** none.

---
## Cross-Phase Analysis

### Same-root-cause clustering (CRITICAL — sequencing dependency)

Four findings across three phases target the **identical** `async with client:` block at `src/mko_telepost/core/telegram_service.py:305-315`:

| Finding | Phase | Concern | Proposed edit to same lines |
|---------|-------|---------|------------------------------|
| INT-001 | 05 | Credentials bypassed by `__aenter__` -> `start()` with no args | Replace `async with client:` with explicit `try: await client.start(**creds)` + `finally: disconnect` |
| SEC-003 | 04 | Session file perms hardened only on success path | Move `set_restrictive_permissions` into `finally` after `client.start()`; also harden `.session-journal` |
| SRV-005 | 03 | Session perms hardened only on success path (duplicate root of SEC-003) | Same as SEC-003 |
| SRV-004 | 03 | Over-broad `except Exception` logs "authentication failed" for any error | Narrow log to actual failing stage / use `logger.exception` |

**Merge candidate:** SEC-003 and SRV-005 share an identical root cause (session-hardening on success path only) and identical fix location. They should be merged into a single finding before execution to avoid duplicate edits.

**Execution ordering (REQUIRED):**

INT-001, SEC-003, SRV-005, and SRV-004 must be implemented **in a single coordinated rewrite** of `telegram_service.py:305-315`, not as four sequential edits. Each finding proposes a different modification to the same ~10-line block; applying them independently risks:

1. **Stale anchors** — INT-001 rewrites the `try` structure, invalidating line anchors SEC-003 / SRV-005 / SRV-004 reference.
2. **Edit conflicts** — INT-001 removes `async with client:`; SEC-003/SRV-005 reference the inner block of that construct; SRV-004 references the `except` clause that wraps it.

**Recommended unified target block** (combines INT-001 + SEC-003/SRV-005 + SRV-004):

```python
client = self.poster.create_client()
try:
    await client.start(**self._make_start_kwargs())
    self._harden_session_files(session_path)  # SEC-003 / SRV-005
    await self._coordinate_posting(client, granges_data, used_cache_files)
except Exception:
    logger.exception("Telegram run failed")   # SRV-004
    raise
finally:
    await client.disconnect()
    self._cleanup_session(session_path)
```

This single edit satisfies all four findings without repeated rewrites. Implement INT-001 as the structural anchor; layer SEC-003/SRV-005 (session hardening) and SRV-004 (log message) onto it.

### Conflicting evidence

None detected. R1–R3 runtime results (imports OK, ruff/mypy clean, 42 tests pass) are consistent with INT-001's claim that tests mask the bug rather than refute it — the production auth path is untested against a real (or stubbed-with-default-args) Telethon `start()`.

---
## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | INT-001, INT-002 |
| Reclassified | 0 | — |
| Merged | 0 | (cross-phase merge candidate SEC-003 <-> SRV-005 flagged for Phase 03/04 validators; not actionable here) |
| Rejected | 0 | — |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| — | — | No rejections. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | No in-phase merges. Cross-phase merge candidate (SEC-003 <-> SRV-005) noted in Cross-Phase Analysis for the relevant phase validators. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | No reclassifications. |

---

## Rollout Analysis

| Risk | Assessment |
|------|------------|
| **Circular dependencies** | None. INT-001 has no inbound dependency. |
| **Hidden dependency chain** | INT-001 -> must be applied alongside SEC-003, SRV-005, SRV-004 (all edit `telegram_service.py:305-315`). See Cross-Phase Analysis. |
| **Unsafe rollout ordering** | HIGH if findings are executed independently — INT-001's structural rewrite invalidates line anchors used by the other three. Coordinate as a single edit. |
| **Fragile insertion points** | Moderate. The fix replaces a 10-line `async with` block; anchors are stable only if applied atomically. |
| **Backward compatibility** | OK. Removing redundant double-`start()` does not change the success-path behavior (authenticated client posting to Telegram). Only the failure-path / fresh-session behavior changes — and that change is the intended fix. |
| **Test coverage gap** | CRITICAL. Existing tests mock `__aenter__` to bypass `start()`, so they cannot verify the fix. A new integration test asserting `_make_start_kwargs()` values reach `start()` on the unauthorized-session path is **mandatory** for INT-001 to be considered closed. |

---

## Execution Validation

| Finding | Applicable | Execution-ready | Notes |
|---------|-----------|-----------------|-------|
| INT-001 | YES | CONDITIONAL | Targets confirmed present (`telegram_service.py:305-315`, `_make_start_kwargs` at lines 285-287). Fix is architecturally aligned (explicit start/disconnect matches the non-interactive CLI contract per spec §184). **Not ready in isolation** — must be batched with SEC-003/SRV-005/SRV-004. New integration test required. |
| INT-002 | YES | YES | Targets confirmed (`gsheets_reader.py:215-244`, caller at `telegram_service.py:337-339`). Fix is trivial, self-contained, no cross-phase dependency. Option (a) recommended. |

---

## Warnings

- **Architectural risk (HIGH):** INT-001, SEC-003, SRV-005, SRV-004 all rewrite the same 10-line block. Independent execution will produce stale-anchor failures or silent re-introduction of the bug. Enforce a single coordinated commit.
- **Test coverage risk (CRITICAL):** The existing test suite (42 passing) provides **zero protection** against INT-001's regression — mocks replace `__aenter__` entirely. Without a new test asserting credential forwarding to `start()`, the fix cannot be validated as correct.
- **Documentation risk (LOW):** `docs/SPEC.md:184` and `docs/00-overview/overview.md:61` describe the intended credential-pass behavior; the code currently violates it. Fixing INT-001 reconciles code with docs — no doc change needed. If INT-001 were rejected, the docs would need to be downgraded to match the broken implementation (DOC-UPDATE). Validation chose the code-fix path per spec priority.

---

## Required Fixes

- **INT-001** — Replace `async with client:` block (`telegram_service.py:305-315`) with explicit `await client.start(**self._make_start_kwargs())` + `finally: await client.disconnect()` so configured credentials reach `_start()` on the first and only `start()` call. **Coordinate with SEC-003 / SRV-005 / SRV-004** in a single rewrite of lines 305-315. Add an integration test asserting `_make_start_kwargs()` values are forwarded to a stubbed `start()` on the unauthorized-session path.

## Advisory Recommendations

- **INT-002** — Remove the dead `or self.config.spreadsheet_id` / `or "Sheet1!A1:Z100"` fallback (and the misleading `# Use config values if not provided` comment) in `GSheetsReader.get_sheet_data` (`gsheets_reader.py:243-244`). Both parameters are required; the invented default range has no spec source. Trivial, self-contained fix.

## Doc Updates Needed

None. Fixing INT-001 reconciles the implementation with the existing spec text at `docs/SPEC.md:184`.
