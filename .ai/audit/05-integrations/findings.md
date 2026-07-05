# Phase 05 Audit Findings — External Integrations

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/05-audit-integrations.md
**Status:** complete
**Validated:** no

## Runtime Verification

| Step | Result |
|------|--------|
| R1 — Import verification | OK — `IMPORTS_OK` for all integration modules |
| R2 — `ruff check` (3 modules) | OK — exit 0, "All checks passed!" |
| R2 — `mypy` (3 modules) | OK — exit 0, "Success: no issues found in 3 source files" |
| R3 — `pytest` (gsheets/telegram_service/telegram_poster) | OK — 42 passed, exit 0 |

---

## Findings

### INT-001: Telegram credentials are bypassed on the auth path — `async with client:` calls `start()` with no credentials before `client.start(**creds)` runs

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

It calls `self.start()` with **no arguments** — i.e. with the default `phone=lambda: input('Please enter your phone (or bot token): ')` and `bot_token=None`. The configured credentials built by `_make_start_kwargs()` (which selects `phone` vs `bot_token` based on `TelethonConfig.is_user` and reads `phone_or_token.get_secret_value()`) are only passed to the **second** `start()` call, which runs after `__aenter__` has already attempted authentication.

Trace of `_start()` (Telethon) confirms the consequence:

1. **Session already valid** — `__aenter__` → `start()` → `me = await self.get_me()` returns the authorized user → returns `self` immediately. The subsequent `client.start(phone=token)` then sees `me is not None`, emits a Telethon warning ("the session already had an authorized user so it did not login to the user account using the provided phone"), and returns. The configured `phone_or_token`/`bot_token` is **never used for login** — auth succeeds only because of the pre-existing session file. `_make_start_kwargs()` is effectively dead on this path.

2. **Fresh / expired / corrupted session** (the documented re-auth path) — `__aenter__` → `start()` → `get_me()` returns `None` → `bot_token` is `None` → enters `while callable(phone): value = phone()` → invokes the default `input('Please enter your phone (or bot token): ')` lambda. The configured `phone_or_token`/`bot_token` is **never reached**. In the intended non-interactive CLI context, `input()` blocks on stdin or raises `EOFError`, crashing the run. The explicit `client.start(**self._make_start_kwargs())` line is unreachable because `__aenter__` already failed.

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
- Telethon `_start()`: when `get_me()` returns `None` and `bot_token` is falsy, it loops `while callable(phone): value = phone()` — invoking interactive `input()` before the configured credential is consulted.
- `docs/SPEC.md:184` and `docs/00-overview/overview.md:61` document that `phone_or_token` is passed to `client.start()` — the code path that would do so is unreachable on a fresh session.
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

This guarantees `phone`/`bot_token` from `TelethonConfig` reach `_start()` on every run, including fresh sessions, and removes the redundant double-`start()`. Coordinate with prior findings SEC-003 / SRV-005 (which already restructure this same `try` block for session-file hardening and the "Telegram authentication failed" log message) — implement together to avoid repeated rewrites of lines 305-315. Add an integration test that asserts `_make_start_kwargs()` values are forwarded to a stubbed `start()` on the unauthorized-session path (the current mocks bypass `start()` entirely, so they cannot catch this regression).

---

### INT-002: Dead credential-fallback logic in `GSheetsReader.get_sheet_data` — `or` fallbacks never trigger because both parameters are required

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

- `src/mko_telepost/core/gsheets_reader.py` — `get_sheet_data` signature (required `spreadsheet_id: str`, `range_name: str`) and the `or` fallback lines.
- `src/mko_telepost/core/google_sheets_models.py` — `GoogleSheetsConfig.spreadsheet_id` has `min_length=10`, so it is always a non-empty string when valid; no `range_name` default exists in the model.
- `src/mko_telepost/core/telegram_service.py:332-335` — sole call site passes both `self.settings.google_sheets.spreadsheet_id` and `range_name` positionally.
- The docstring example (`reader.get_sheet_data("abc123", "Sheet1!A1:Z100")`) also shows both args as required.

**Recommendation:** Pick one contract and make the code match it. Either (a) drop the dead `or` fallback lines and the `# Use config values if not provided` comment — the method requires both args and that is fine; or (b) if a "default to config" mode is genuinely wanted, make the parameters optional (`spreadsheet_id: str | None = None`, `range_name: str | None = None`) and resolve them from `self.config` inside. Option (a) is simpler and matches the only existing caller. Remove the invented `"Sheet1!A1:Z100"` default regardless — it has no source of truth in the config models or spec. Effort: trivial. Priority: recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 0 |
| LOW | 1 |

## Mandatory Fixes

- **INT-001** — `async with client:` invokes `TelegramClient.start()` with no credentials before `client.start(**self._make_start_kwargs())`, so configured `phone_or_token`/`bot_token` are bypassed on fresh-session auth (interactive `input()` / `EOFError`). Replace with an explicit `await client.start(**creds)` followed by `disconnect()` in `finally`. Coordinate with SEC-003 / SRV-005.

## Advisory Recommendations

- **INT-002** — Remove the dead `or self.config.spreadsheet_id` / `or "Sheet1!A1:Z100"` fallback in `GSheetsReader.get_sheet_data` (both parameters are required), or make the parameters optional and resolve from config. The invented default range has no spec source.

## Doc Updates Needed

None.