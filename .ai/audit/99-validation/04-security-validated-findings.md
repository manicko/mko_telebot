# Phase 04 Audit Findings — Security & Secret Management

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/04-audit-security.md
**Status:** complete
**Validated:** yes (by validator agent)

> **Validation note (header):** All four findings were verified against the current
> codebase. SEC-001 is **VALIDATED with an evidence correction** and a **CRITICAL
> cross-phase rollout dependency** on CLI-001 (Phase 01). SEC-002, SEC-003, SEC-004
> are **VALIDATED as-is** (SEC-003 and SEC-004 carry minor evidence corrections that
> do not change their conclusions). Details are inline under each finding and in
> the new `SEC-X01` cross-phase conflict entry at the end of the Findings section.

---

## Findings

### SEC-001: `logger.exception` in `app.py` leaks `api_hash` / `phone_or_token` into logs via the chained Pydantic `ValidationError` traceback

> **Validation Note:**
> - **Action:** validated (with evidence correction + cross-phase dependency)
> - **Detail:** Reproduced under real runtime conditions (zero root handlers, Python `lastResort` stderr handler active). The chained `ValidationError` traceback **is** rendered and the `input_value='BBBBB...'` fragment (real `api_hash`) **is** leaked — confirmed via `stderr` capture. The leak mechanism (`raise ConfigError(sanitized_msg) from e` + `logger.exception`) is exactly as described. **However, evidence point #3 is factually incorrect today:** `log_config.yaml` is **never loaded in production** — `TelepostConfigReader.load_logging_config()` is defined at `config_reader.py:161` but called only from `tests/test_config_reader.py:113`; there is no `dictConfig`/`fileConfig`/`basicConfig` call anywhere in `src/`. Therefore the `RotatingFileHandler` is **not installed at runtime**, the secret is **not** written to `~/.config/mko_telepost/logs/log.log`, and the "persists to disk across two 5 MB rotations" claim is false. The leak currently goes to **stderr** (terminal / captured shell output / CI logs), not to a log file. The CRITICAL severity is nonetheless justified: `api_hash` is a Telegram API credential and the plaintext `input_value` is emitted on every config-validation failure. **Critical rollout dependency on CLI-001 (Phase 01):** CLI-001 (validated, SPEC-DEVIATION) mandates loading `log_config.yaml` at startup. If CLI-001 is fixed **before** SEC-001, the `RotatingFileHandler` becomes active and the same leak is then **persisted to disk** across two 5 MB rotations — i.e. fixing CLI-001 alone **escalates** SEC-001 from a transient stderr leak to persistent credential-at-rest exposure. SEC-001 MUST be fixed before or together with CLI-001.
> - **See also:** CLI-001 (Phase 01, `.ai/audit/99-validation/01-cli-validated-findings.md`); cross-phase finding `SEC-X01` at the end of this section.

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
   - **Validator correction:** this point describes the *configured* handler, but `log_config.yaml` is not loaded at runtime (see SEC-001 Validation Note and SEC-X01). The handler is therefore **not installed today**; the leak currently reaches `stderr` via `lastResort`, not the rotating log file. The disk-persistence path only activates after CLI-001 is fixed.
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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Confirmed independently. `filesystem_get_file_info` on `C:\py_dev\mko_telepost\test.session` returns `size: 28672`, `permissions: 666`, modified `2026-06-29`. `.gitignore:220` matches `*.session`; `git ls-files --error-unmatch test.session` reports "did not match any file(s) known to git" — gitignored and untracked, so this is a local artifact, not a repository leak. The risk is local credential-at-rest hygiene (repo root, outside `APP_PATHS.user_settings_dir`). Note: on Windows, `permissions: 666` is the `stat`-mask interpretation of the NTFS ACL rather than true POSIX mode bits, but the conclusion (file is readable/writable beyond the owner) holds. Recommendation (delete + add guard) is sound and low-effort.

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

### SEC-003: Session permissions timing [CODE-FIX-NEEDED] Session `.session` file restrictive permissions applied only after successful `client.start()` — auth-failure path leaves the auth key world-readable

> **Validation Note:**
> - **Action:** code-fix-needed — SPEC requires hardening after `client.start()`; code applies on success path only.
> - **Detail:** Confirmed in `telegram_service.py:306-315`: `client.start()` and `_coordinate_posting(...)` run inside `async with client:`, and `_cleanup_session(session_path)` (line 311) runs **only on the success path**. The `except Exception` branch (lines 313-315) logs `"Telegram authentication failed"` and re-raises **without** calling `_cleanup_session`. `_cleanup_session` (lines 404-414) only hardens `Path(str(session_path) + ".session")` and never touches the `.session-journal` sibling. `set_restrictive_permissions` (`file_permissions.py:10-21`) is cross-platform (Unix `chmod 0o600` / Windows owner-only DACL). **Minor correction:** on Windows (the project's primary platform), the `.session` file inherits NTFS ACLs from its parent directory, which `telegram_poster.py:53` already hardens via `set_restrictive_permissions(session_path.parent, is_dir=True)` — so on Windows the exposure is partially mitigated by inheritance. The gap is fully real on Unix and on Windows if the parent ACL is later relaxed. Recommendation (`finally` block) is architecturally sound.
> - **See also:** SRV-005 (Phase 03, `.ai/audit/99-validation/03-services-validated-findings.md`) — SRV-005 restructures the **same** `try/except` block in `telegram_service.run()` to fix the stage-inaccurate `"Telegram authentication failed"` message. SEC-003 and SRV-005 must be coordinated: both edit lines 305-315. Implementing SEC-003's `finally`-based hardening inside SRV-005's restructured block is the clean sequence; doing them independently risks merge conflicts and a transient window where one fix is present and the other is not.

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

**Recommendation:** Use a `finally` block. `os.umask` is process-global and thread-unsafe — it affects all concurrent file creation (image cache, temp files), not just Telethon's, and is a no-op on Windows. The `finally` approach is scoped, idempotent, cross-platform, and follows the project's existing hardening pattern via `set_restrictive_permissions`.

**Single approach: `finally` block hardening.**

1. **Extend `_cleanup_session`** (`telegram_service.py:404-414`) to also harden `.session-journal`:

   ```python
   def _cleanup_session(self, session_path: Path) -> None:
       for suffix in (".session", ".session-journal"):
           f = Path(str(session_path) + suffix)
           if f.exists():
               set_restrictive_permissions(f)
   ```

2. **Move hardening into a `finally` block** after `client.start()`. Restructure lines 305-315 so `_cleanup_session` runs regardless of success or failure:

   ```python
   try:
       async with client:
           await client.start(**self._make_start_kwargs())
           await self._coordinate_posting(client, granges_data, used_cache_files)
   except Exception:
       logger.error("Telegram authentication failed")
       raise
   finally:
       self._cleanup_session(session_path)
   ```

   The `finally` block runs after both the success path (posting complete) and the auth-failure path (`client.start()` raises). The `except Exception` re-raises, but `finally` executes before the exception reaches the outer `try/finally`.

3. **Coordinate with SRV-005 (Phase 03):** SRV-005 replaces the inaccurate `"Telegram authentication failed"` error message in the same `except` block. Implement SEC-003's `finally` restructure as the base; SRV-005 then adjusts the error message text within the new structure.

---

### SEC-004: Photo-path filesystem probing (`get_dir_content`) runs before containment validation, contradicting the "prevent probing" ordering invariant

> **Validation Note:**
> - **Action:** validated (with minor evidence correction)
> - **Detail:** Confirmed in `post_processor.py`. `get_posts` (line 210) calls `_extract_photo_paths(...)` **before** `_validate_photo_paths(...)` (line 212). `_extract_photo_paths` (lines 140-142) resolves `raw_entry_resolved = base_dir / raw_entry` and immediately calls `get_dir_content(raw_entry_resolved)`, which globs the directory (`utils.py:31-44`) and catches `OSError`/`PermissionError` via `logger.exception`. `_validate_photo_path` (lines 94-102) does perform the containment check (`resolved.is_relative_to(allowed_resolved)`) **before** `resolved.exists()`, with the comment `"security: prevent probing"` — but that check runs only in the second step, after the FS has already been probed. The ordering invariant is therefore violated end-to-end, exactly as described. **Minor evidence correction:** the finding states `get_dir_content` performs `Path(path).glob("**/*.jpg")`; the actual default call is non-recursive — `get_dir_content` uses `pattern = ""` when `subfolders=False` (its default), so the glob is `*.jpg` / `*.jpeg`, not `**/*.jpg`. This does not weaken the finding: a non-recursive `*.jpg` glob still enumerates the target directory and still distinguishes empty / `PermissionError` / non-empty via timing and via `logger.exception`. Recommendation (move the containment check into `_extract_photo_paths` before any FS access) is correct and aligns with the code's own stated invariant.

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

### SEC-X01: [CROSS-PHASE CONFLICT] SEC-001 disk-persistence evidence contradicts CLI-001 (Phase 01) — logging is not configured at runtime

> **Validation Note:**
> - **Action:** new cross-phase finding (added by validator)
> - **Detail:** Cross-phase conflict surfaced during validation, not an original auditor finding. SEC-001 (this phase) evidence point #3 claims the leaked `api_hash` is "written to `~/.config/mko_telepost/logs/log.log`" and "persists to disk across two 5 MB rotations" because `log_config.yaml:17-25` configures a `RotatingFileHandler`. CLI-001 (Phase 01, validated as SPEC-DEVIATION) establishes — and this validator independently confirmed — that `log_config.yaml` is **never loaded in production**: `TelepostConfigReader.load_logging_config()` is defined at `config_reader.py:161` but invoked only from `tests/test_config_reader.py:113`; there is no `dictConfig` / `fileConfig` / `basicConfig` call anywhere in `src/`. At runtime the root logger has zero handlers and Python's `lastResort` (`<_StderrHandler <stderr> (WARNING)>`) handles records. The two findings therefore **contradict each other on the leak destination**: SEC-001 says "log file on disk"; CLI-001 says "no log file is ever written, only stderr". CLI-001 is correct about the current state. The contradiction is **not a reason to reject either finding** — both describe real defects — but it has a **critical rollout ordering implication** captured in SEC-001's Validation Note: resolving CLI-001 first (installing the `RotatingFileHandler`) without first resolving SEC-001 (breaking the cause chain) **escalates** the leak from a transient stderr emission to persistent credential-at-rest exposure on disk. **Required ordering: SEC-001 must land before or atomically with CLI-001.** A regression test that captures both `stderr` and the configured file-handler output and asserts the secret is absent from both is the only way to keep this invariant durable as logging configuration evolves.
> - **See also:** SEC-001 (this file); CLI-001 (`.ai/audit/99-validation/01-cli-validated-findings.md`).

| Field | Value |
|-------|-------|
| **ID** | SEC-X01 |
| **Severity** | HIGH |
| **Type** | CROSS-PHASE-CONFLICT |
| **Affected Modules** | `src/mko_telepost/app.py`, `src/mko_telepost/core/config_reader.py`, cross-phase: CLI-001 (Phase 01) |
| **Classification** | mandatory (rollout ordering) |

**Description:** SEC-001 and CLI-001 make contradictory claims about where the leaked `api_hash` traceback lands. This entry records the conflict and the rollout ordering it forces. See the Validation Notes on SEC-001 and this entry for the full rationale.

**Recommendation:** Enforce rollout ordering — SEC-001 (`raise ConfigError(sanitized_msg) from None` + log-capture regression test) must be merged **before or in the same change** as CLI-001 (load `log_config.yaml` at startup). Do not merge CLI-001 alone. The SEC-001 regression test must assert the secret is absent from **both** the current `stderr`/`lastResort` path **and** the future `RotatingFileHandler` path (configure a capturing handler in the test).

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 1 (SEC-X01, cross-phase ordering) |
| MEDIUM | 2 |
| LOW | 1 |

## Mandatory Fixes

- **SEC-001** — Stop the `ValidationError` cause chain from reaching `logger.exception` (e.g. `raise ConfigError(sanitized_msg) from None`), and extend the sanitization test to assert against captured log output, not just `str(exc_info.value)`. **(Evidence correction: today the plaintext `api_hash` / `phone_or_token` `input_value` is leaked to `stderr` via `lastResort`, NOT to `~/.config/mko_telepost/logs/log.log` — `log_config.yaml` is not loaded at runtime. The disk-persistence path only activates after CLI-001 is fixed; see SEC-X01. The fix and its regression test must cover BOTH the current stderr path and the future file-handler path.)**
- **SEC-X01** — Enforce rollout ordering: SEC-001 must land before or atomically with CLI-001 (Phase 01). Do not merge CLI-001 alone, or the leak escalates from stderr to a persistent on-disk log file.

## Advisory Recommendations

- **SEC-002** — Delete the orphaned `test.session` (perms `666`) from the repo root and add a guard preventing session files outside `USER_DIR`.
- **SEC-003** — Harden `.session` + `.session-journal` in a `finally` after `client.start()` (reject `os.umask`: process-global, thread-unsafe, Unix-only). Implement the `finally` restructure first, then SRV-005 adjusts the error message text within the new structure.
- **SEC-004** — Validate photo-path containment in `_extract_photo_paths` before calling `get_dir_content`, to honor the "prevent probing" invariant stated in the code.

## Doc Updates Needed

None.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | SEC-002 |
| Validated (with evidence correction) | 3 | SEC-001 (leak destination: stderr not log file), SEC-003 (Windows ACL inheritance mitigates), SEC-004 (glob is non-recursive `*.jpg`, not `**/*.jpg`) |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |
| New cross-phase findings | 1 | SEC-X01 (SEC-001 ↔ CLI-001 conflict + rollout ordering) |

### Rejected Findings

None.

### Merged Findings

None.

### Reclassified Findings

None.

### Cross-Phase Dependencies

| This Finding | Depends On / Conflicts With | Phase | Nature |
|--------------|------------------------------|-------|--------|
| SEC-001 | CLI-001 | 01-cli | **Critical ordering:** SEC-001 must land before or with CLI-001. CLI-001 installs the `RotatingFileHandler`; without SEC-001's cause-chain break, the handler persists the leaked `api_hash` to disk. |
| SEC-003 | SRV-005 | 03-services | **Coordination:** both restructure `telegram_service.py:305-315`. Implement SEC-003's `finally`-hardening inside SRV-005's restructured block to avoid merge conflicts. |
| SEC-001 | CFG-002 | 02-config | **Weak link:** CFG-002 corrects the `_validate_settings` / `load()` docstrings (and possibly removes the `validate` flag). SEC-001 edits the same `_validate_settings` method (`config_reader.py:148-159`). Sequence independently but review together. |

### Rollout Safety

- **Unsafe sequence (MUST avoid):** merging CLI-001 before SEC-001. This moves the `api_hash` leak from transient `stderr` to a persistent rotating log file on disk (`~/.config/mko_telepost/logs/log.log` + 2 backups) — a severity escalation. See SEC-X01.
- **Safe sequence:** SEC-001 first (break cause chain + log-capture regression test covering both stderr and file-handler paths), then CLI-001.
- **Coordination required:** SEC-003 and SRV-005 edit the same `try/except` block; land them together or in a documented order.
- **No circular dependencies detected.** SEC-002 and SEC-004 are fully independent and can land in any order.

### Warnings

- **Architectural risk (SEC-001):** the `raise ... from e` pattern is used in two places in `config_reader.py` (line 112 `raise ConfigError(...) from e` for the generic `except Exception` in `load()`, and line 159 in `_validate_settings`). Only line 159 chains a `ValidationError` containing `SecretStr` `input_value`s, but line 112 can also chain arbitrary exceptions whose `str()` may include user input. The fix should audit both `raise ... from` sites in this module.
- **Documentation inconsistency:** `log_config.yaml` is shipped and documented as the logging configuration, but is never loaded in production (CLI-001). Any maintainer reading the config or docs will assume the `RotatingFileHandler` is active. SEC-X01 makes this gap security-relevant.
- **Test gap:** `tests/test_validation_sanitization.py` asserts only against `str(exc_info.value)`, never against captured log output. Until a log-capture assertion exists, the SEC-001 regression is not enforceable.

### Required Fixes

1. **SEC-001** — break the `ValidationError` cause chain in `config_reader._validate_settings` (`raise ConfigError(sanitized_msg) from None`); audit the sibling `raise ... from e` at `config_reader.py:112`.
2. **SEC-001 regression test** — extend `tests/test_validation_sanitization.py` to capture `logging` output (both `stderr`/`lastResort` and a configured file handler) and assert the secret is absent from the formatted traceback.
3. **SEC-X01 ordering** — enforce SEC-001-before-or-with-CLI-001 in the rollout plan; do not merge CLI-001 alone.

### Advisory Recommendations

- **SEC-002** — delete `test.session`; add a pre-commit guard against `*.session` / `*.session-journal` outside `USER_DIR`.
- **SEC-003** — harden `.session` + `.session-journal` in a `finally` after `client.start()` (reject `os.umask`); coordinate with SRV-005.
- **SEC-004** — move the photo-path containment check into `_extract_photo_paths` ahead of `get_dir_content`.
