# Phase 04 Audit Findings — Security & Secret Management

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/04-audit-security.md
**Status:** complete
**Validated:** no

---

## Findings

### SEC-001: `logger.exception` in `app.py` leaks `api_hash` / `phone_or_token` into logs via the chained Pydantic `ValidationError` traceback

| Field | Value |
|-------|-------|
| **ID** | SEC-001 |
| **Severity** | CRITICAL |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | `src/mko_telepost/app.py`, `src/mko_telepost/core/config_reader.py` |
| **Classification** | mandatory |

**Description:** `_load_and_validate_config` catches any exception from `reader.load()` and calls `logger.exception("Configuration load failed")` (`app.py:116`). When configuration validation fails, `TelepostConfigReader._validate_settings` raises `ConfigError(sanitized_msg) from e` where `e` is the original `pydantic.ValidationError` (`config_reader.py:152-159`). The `ConfigError` *message* is correctly sanitized (it contains only `loc` and `error_type`, no input values). However, `raise ... from e` links the `ValidationError` as `__cause__`, and `logger.exception` formats the **full cause-chain traceback**. Pydantic v2's `ValidationError.__str__()` embeds `input_value=...` for each error, which for `SecretStr` fields (`api_hash`, `phone_or_token`) is the **plaintext secret value**.

The sanitization in `config_reader._validate_settings` therefore protects only the `ConfigError` message string, not the chained traceback that `logger.exception` actually emits. The existing test `tests/test_validation_sanitization.py::test_sanitized_error_no_input_value` only asserts `secret_value not in str(exc_info.value)` — i.e. the `ConfigError` message — and does not exercise the `logger.exception` path, so the leak is undetected by the suite.

**Evidence (runtime, reproduced against current code):**

1. `app.py:116` — `except Exception: logger.exception("Configuration load failed")`.
2. `config_reader.py:159` — `raise ConfigError(sanitized_msg) from e` (chains the unsanitized `ValidationError`).
3. `log_config.yaml:17-25` — root logger has a `RotatingFileHandler` writing to `logs/log.log` (resolved to `~/.config/mko_telepost/logs/log.log`), so the leaked secret **persists to disk** across two 5 MB rotations.
4. Reproduction (config with `api_hash` exceeding `max_length=64`, all other fields valid):
   ```
   === captured log (relevant lines) ===
   Configuration load failed
     Value should have at most 64 items after validation, not 70 [type=too_long,
     input_value='BBBBBBBBBBBBBBBBBBBBBBBB...BBBBBBBBBBBBBBBBBBBBBBB', input_type=str]
   === LEAK CHECK ===
   api_hash BBBBB leaked into log: True
   ```
   The `input_value` is the real `api_hash` value from the user's config. A `phone_or_token` value that fails a non-placeholder constraint (e.g. `min_length=5`) is leaked through the same mechanism.

**Recommendation:** Break the cause chain when re-raising so the `ValidationError` is not serialized into the traceback. Concretely, in `_validate_settings` raise the `ConfigError` **without** `from e` (or attach only a redacted `__cause__`), e.g. `raise ConfigError(sanitized_msg) from None`. Verify by extending the sanitization test to capture `logging` output and assert the secret does not appear in the formatted traceback (not just in `str(exc_info.value)`). Additionally consider calling `ValidationError.errors(include_input=False)` (Pydantic v2) when building the sanitized message so future code paths that do log error details stay safe.

---

### SEC-002: Leftover live Telethon session file at the project root with world-readable/writable permissions

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | repo root (`test.session`), `src/mko_telepost/core/telegram_poster.py` |
| **Classification** | advisory |

**Description:** A real Telethon session file `test.session` (28 672 bytes — an authenticated session containing the Telegram auth key) exists directly in the repository root. The file's filesystem permissions are `666` (owner/group/world read+write). Production code correctly resolves session paths into `APP_PATHS.user_settings_dir` (`telegram_poster.py:47-48`), so this file is a manual testing artifact, but it violates the credential-at-rest hygiene this phase checks.

**Evidence:**
- `filesystem_get_file_info` on `C:\py_dev\mko_telepost\test.session` → `size: 28672`, `permissions: 666`, modified 2026-06-29.
- `git check-ignore -v test.session` → `.gitignore:220:*.session  test.session` — the file is gitignored and untracked (`git ls-files --error-unmatch` reports "did not match any file(s) known to git"), so it is **not** a repository leak. The risk is local: world-readable credential file sitting outside `USER_DIR` in a directory that is routinely opened in editors, zipped for backups, or synced via cloud drives.
- No production code or test creates `test.session` (grep for `test.session` / `TelegramClient(` in `tests/` returns no matches), confirming it is an orphaned manual artifact.

**Recommendation:** Delete `test.session` from the working tree. Add a defensive check (or pre-commit hook) that no `*.session` / `*.session-journal` files exist under the project root, since the codebase already mandates `USER_DIR` for session storage.

---

### SEC-003: Session `.session` file restrictive permissions applied only after successful `client.start()` — auth-failure path leaves the auth key world-readable

| Field | Value |
|-------|-------|
| **ID** | SEC-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py`, `src/mko_telepost/core/telegram_poster.py` |
| **Classification** | advisory |

**Description:** `TelegramPoster.create_client` sets owner-only permissions on the session **directory** (`telegram_poster.py:53`, `set_restrictive_permissions(session_path.parent, is_dir=True)`), but the actual `.session` file is created later by Telethon inside `client.start()` with the process default permissions (typically `0644` on Unix / default NTFS ACL on Windows). The owner-only ACL on the file is only applied by `TelegramService._cleanup_session` (`telegram_service.py:404-414`), which runs **only on the success path** after `_coordinate_posting` completes:

```python
async with client:
    await client.start(**self._make_start_kwargs())   # session file created here (default perms)
    await self._coordinate_posting(client, granges_data, used_cache_files)
    self._cleanup_session(session_path)               # perms tightened only here
```

If `client.start()` raises (bad credentials, phone-code error, network failure, Ctrl-C), execution jumps to `except Exception: logger.error("Telegram authentication failed"); raise` (`telegram_service.py:313-315`) and `_cleanup_session` is never reached. The `.session` file — which now contains a live Telethon auth key — is left on disk with default (group/world-readable) permissions. The same gap applies to the `.session-journal` file, which `_cleanup_session` does not touch at all.

**Evidence:**
- `telegram_service.py:306-315` — `client.start()` and `_coordinate_posting` are inside the `async with client:` block; `_cleanup_session` is called only after `_coordinate_posting` returns successfully, on the non-exception path.
- `telegram_service.py:313-315` — the `except Exception` branch logs and re-raises without calling `_cleanup_session`.
- `telegram_service.py:411` — `_cleanup_session` only chmods `Path(str(session_path) + ".session")`; the `.session-journal` sibling file Telethon creates during writes is never hardened.
- `file_permissions.py:10-21` — `set_restrictive_permissions` is the project's own hardening helper; it is simply invoked too late for the failure path.

**Recommendation:** Harden the session file immediately after it is created rather than only on success. Either (a) call `set_restrictive_permissions` on both `*.session` and `*.session-journal` inside a `finally` after `client.start()` completes (covering both success and auth-failure), or (b) set a restrictive umask (`os.umask(0o077)`) around the `client.start()` call so the file is created owner-only from the start. Extend `_cleanup_session` to also harden the `-journal` file.

---

### SEC-004: Photo-path filesystem probing (`get_dir_content`) runs before containment validation, contradicting the "prevent probing" ordering invariant

| Field | Value |
|-------|-------|
| **ID** | SEC-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py` |
| **Classification** | advisory |

**Description:** The phase checklist requires "File paths from Google Sheets (photo paths) are validated before use. No user-supplied path can escape the intended directory." `_validate_photo_path` correctly checks `resolved.is_relative_to(allowed_resolved)` **before** `resolved.exists()` and explicitly comments "security: prevent probing" (`post_processor.py:94-102`). However, that validator is called by `_validate_photo_paths`, which runs **after** `_extract_photo_paths` has already invoked `get_dir_content(raw_entry_resolved)` (`post_processor.py:140-142`). `get_dir_content` performs `Path(path).glob("**/*.jpg")` against the user-supplied path, so the filesystem is probed (directory listing / existence / permission errors) before the containment check runs.

When a sheet editor supplies an absolute path (e.g. `/home/secret/Pics/` or `C:\Users\admin\`), `base_dir / raw_entry` collapses to the absolute path (pathlib semantics), and `get_dir_content` enumerates `.jpg`/`.jpeg` entries in that directory. The resulting paths are later rejected by `_validate_photo_path` (so nothing is exfiltrated to Telegram), but the directory has already been listed, and the difference between "empty", "PermissionError", and "non-empty" is observable through timing and through `logger.exception` output in `utils.get_dir_content` (`utils.py:43`).

**Evidence:**
- `post_processor.py:136-142` — `_should_skip_photo_entry` only filters glob metacharacters and empty strings; a plain absolute path passes, then `get_dir_content(raw_entry_resolved)` is called.
- `post_processor.py:161-179` — `_validate_photo_paths` (which calls `_validate_photo_path` with the containment check) runs only after `_extract_photo_paths` has already globbed.
- `utils.py:38-43` — `get_dir_content` catches `OSError, PermissionError` and logs `logger.exception(f"Error reading directory {path}: {err}")`, so both probing and error logging happen pre-validation.
- `post_processor.py:94` — the code's own comment states the intended invariant: "Check path containment before existence (security: prevent probing)". The current call order violates it for the glob step.

**Recommendation:** Move the containment check into `_extract_photo_paths` before any filesystem access. Resolve `raw_entry` against `base_dir`, verify `resolved.is_relative_to(allowed_base.resolve())` (honoring `allow_absolute_paths`), and only then call `get_dir_content`. This makes the "prevent probing" comment true end-to-end.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 1 |

## Mandatory Fixes

- **SEC-001** — Stop the `ValidationError` cause chain from reaching `logger.exception` (e.g. `raise ConfigError(sanitized_msg) from None`), and extend the sanitization test to assert against captured log output, not just `str(exc_info.value)`. `api_hash` / `phone_or_token` plaintext is currently written to `~/.config/mko_telepost/logs/log.log`.

## Advisory Recommendations

- **SEC-002** — Delete the orphaned `test.session` (perms `666`) from the repo root and add a guard preventing session files outside `USER_DIR`.
- **SEC-003** — Harden the `.session` (and `.session-journal`) file in a `finally` after `client.start()`, or set `os.umask(0o077)` around `client.start()`, so an auth failure does not leave the auth key world-readable.
- **SEC-004** — Validate photo-path containment in `_extract_photo_paths` before calling `get_dir_content`, to honor the "prevent probing" invariant stated in the code.

## Doc Updates Needed

None.
