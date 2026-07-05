# Phase 03 Audit Findings â€” Service Layer & Business Logic

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/03-audit-services.md
**Status:** complete
**Validated:** yes
**Mode:** problems-only
**Validator:** validator
**Validation date:** 2026-07-03

## Runtime Verification Summary

| Step | Result |
|------|--------|
| R1 â€” Import verification | OK â€” all service modules import cleanly |
| R2 â€” `ruff check` (6 service files) | All checks passed |
| R2 â€” `mypy` (6 service files) | Success: no issues found in 6 source files |
| R3 â€” `pytest tests/` | 224 passed in 1.21s |
| R4 â€” Dead code search | 1 instance found â€” see SRV-002 |

---

## Findings

### SRV-001: `max_photos` config allows up to 20 but Telegram album hard limit is 10

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION (code lags behind docs — SPEC says "after client.start()")
| **Affected Modules** | `src/mko_telepost/core/chat_models.py`, `src/mko_telepost/core/telegram_service.py` |
| **Classification** | mandatory |

**Description:** `ChatDefaults.max_photos` and `ChatConfig.max_photos` are validated with
`ge=1, le=20` (see `chat_models.py` lines 82 and the per-chat validator at lines 176-183).
The posting path in `TelegramService._push_posts_to_queue` slices photos to `chat.max_photos`
(`telegram_service.py` line 101) and sends them as a single album via
`client.send_file(post.chat_id, files, ...)` (line 206). Telethon dispatches a multi-file
`send_file` call to Telegram's `messages.sendMultiMedia`, whose hard limit is **10 items per
media group** (confirmed in the official Telegram API docs: *"wrapping each InputMedia ...
maximum 10 per media group"*). Any chat configured with `max_photos` between 11 and 20 will
therefore produce albums that Telegram rejects with a 400 `MEDIA_INVALID`/`MULTI_TOO_LONG`
error on every post that has more than 10 photos.

The error is not in the retry whitelist in `_try_send_message` (lines 227-263), so it falls
through to the catch-all `except Exception` at line 264, which logs `"Unexpected error sending
to '<chat_name>'"` and returns `False`. The post is then silently dropped (counted as
`failed_count`), and the run continues. The root cause â€” an invalid configuration value â€” is
never surfaced at validation time, so the operator only sees per-post "unexpected error" logs
with no link back to the `max_photos` setting.

**Evidence:**
- `chat_models.py:82` â€” `max_photos: int = Field(default=5, ge=1, le=20, ...)`
- `chat_models.py:176-183` â€” per-chat validator allows `1..20`
- `telegram_service.py:101` â€” `raw_photos = post[1][: chat.max_photos]`
- `telegram_service.py:206-211` â€” `await client.send_file(post.chat_id, files, caption=post.txt, ...)`
- `telegram_service.py:264-267` â€” catch-all `except Exception` returns `False`
- `docs/SPEC.md:249`, `docs/99-reference/config-reference.md:188,206` â€” document `le=20`
- Telegram API docs (`/api/files`, "Albums, grouped media"): "maximum 10 per media group"

**Recommendation:** Tighten the `max_photos` upper bound to `le=10` in both
`ChatDefaults` and the `ChatConfig.max_photos` validator (and update the spec/config docs to
match). This rejects invalid configurations at load time with a clear Pydantic validation
error instead of letting them through to a per-post API failure. If a future Telegram limit
change raises the cap, bump the validator in one place.

> **Validation Note:**
> - **Action:** code-fix-needed — SPEC describes hardening after `client.start()` succeeds; code applies after posting.
> - **Detail:** Verified against current code. `chat_models.py` confirms `Field(default=5, ge=1, le=20)` on `ChatDefaults.max_photos` and the per-chat `validate_max_photos` rejects only `v < 1 or v > 20`. `telegram_service._push_posts_to_queue` slices `post[1][: chat.max_photos]` and `_try_send_message` dispatches a single `client.send_file(post.chat_id, files, ...)` with no album-batching. The 10-item Telegram media-group limit is a real upstream contract, so values 11â€“20 are unreachable at runtime and fail silently via the catch-all `except Exception` returning `False`. SPEC.md:249 and config-reference.md:188,206 both document `le=20`, so spec and code are mutually consistent but both wrong relative to the Telegram contract â€” this is a genuine spec deviation (the spec value itself is incorrect), not a doc-only update.
> - **Rollout note:** Tightening to `le=10` is a backward-incompatible config change. Existing configs with `max_photos` in 11â€“20 were already failing per-post at runtime, so this converts silent runtime failures into loud load-time Pydantic errors (desired fail-fast). The change must be applied atomically to: (a) `ChatDefaults.max_photos` Field, (b) `ChatConfig.validate_max_photos` upper bound, (c) `docs/SPEC.md:249`, (d) `docs/99-reference/config-reference.md:188,206`, (e) `docs/99-reference/error-reference.md:233`, and (f) the `test_max_photos_constraints` docstring at `tests/test_models.py:428` (currently reads "le=20"). No existing test asserts acceptance of `max_photos` in 11â€“20, so only the docstring needs updating.
> - **See also:** none

---

### SRV-002: `ImageCache.get_cache_path` is dead code and returns a path inconsistent with `resize_image`

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION (code lags behind docs — SPEC says "after client.start()")
| **Affected Modules** | `src/mko_telepost/core/image_cache.py` |
| **Classification** | advisory |

**Description:** `ImageCache.get_cache_path` (lines 39-51) is never called from production
code. A repository-wide search returns exactly one production definition site
(`image_cache.py:39`) and zero non-test call sites; the only callers are
`tests/test_image_cache.py` (`test_get_cache_path`, `test_get_cache_path_consistency`).
The spec documents `resize_image` and `cleanup_unused` as the public image-cache API
(`docs/SPEC.md` Â§4.9) but does **not** document `get_cache_path`, so per the project's dead-code
policy this is undocumented dead code rather than future-proofing.

More importantly, `get_cache_path` is **wrong** if anyone were to call it. It computes the
cache filename as `{digest}{ext}` where `ext = original_path.suffix or ".jpg"` â€” i.e. it
preserves the source file's extension (lines 48-51). `resize_image`, by contrast, normalizes
the output extension based on the image's alpha channel: `.png` for `RGBA`/`LA`/`P` modes
and `.jpg` otherwise (lines 76-79). So for a `.png` source that turns out to be opaque,
`get_cache_path` returns `...abc.png` while `resize_image` actually writes `...abc.jpg`. A
caller using `get_cache_path` to look up an already-cached file would look for a path that
never exists, defeating the cache.

The cache-key logic is also duplicated: `resize_image` re-implements the digest inline
(lines 70-79) instead of delegating to `get_cache_path`, so the two implementations can drift
(as they already have).

**Evidence:**
- `image_cache.py:39-51` â€” `get_cache_path` uses `original_path.suffix or ".jpg"`
- `image_cache.py:70-79` â€” `resize_image` recomputes digest and uses `out_ext` from alpha mode
- Grep `get_cache_path` across `src/`: 1 match (the definition only)
- Grep `get_cache_path` across `tests/`: 7 matches (test-only callers)
- `docs/SPEC.md` Â§4.9 lists only `resize_image` and `cleanup_unused` as image-cache guarantees

**Recommendation:** Remove `get_cache_path` and replace it with a private `_get_cache_path`
helper used only by `resize_image`. This eliminates dead code (zero production callers), removes
the extension-divergence risk, and keeps the alpha-aware normalization logic in one place.

**Rationale:** `get_cache_path` was never called from production code â€” a repository-wide search
finds exactly 1 definition and 0 production call sites. Its interface (pure path computation
given only the source path) is fundamentally incompatible with alpha-aware extension selection,
which requires opening the image to check `img.mode`. Fixing it would require I/O in a
path-only method, making the interface misleading. Removal is strictly better.

**Implementation plan:**

1. Remove the `get_cache_path` method (lines 39-51) from
   `src/mko_telepost/core/image_cache.py`.

2. Add a private `_get_cache_path` method to `ImageCache` that computes the cache path with
   the same digest and alpha-aware extension logic currently inlined in `resize_image`:
   ```python
   def _get_cache_path(self, original_path: Path, alpha: bool = False) -> Path:
       posix = original_path.as_posix()
       digest = hashlib.sha256(posix.encode("utf-8")).hexdigest()[:16]
       ext = ".png" if alpha else ".jpg"
       return self.cache_dir / f"{digest}{ext}"
   ```

3. Have `resize_image` call this helper instead of inlining the digest
   (change lines 70-79 to call `self._get_cache_path(image_path, alpha=has_alpha)`).

4. Remove the two test-only callers from `tests/test_image_cache.py`:
   `test_get_cache_path` and `test_get_cache_path_consistency`. The existing
   `test_resize_image_cache_hit` already exercises the real cache-hit path through
   `resize_image`.

**Effort:** Low (~20 lines changed). **Risk:** None â€” no production callers, existing
resize_image behavior is preserved exactly.

> **Validation Note:**
> - **Action:** code-fix-needed — SPEC describes hardening after `client.start()` succeeds; code applies after posting.
> - **Detail:** Dead-code policy cross-reference performed. SPEC Â§4.9 (`docs/SPEC.md:374-381`) lists atomic writes, cache preservation, per-chat dimensions, concurrent-run protection, output format normalization, and resize fallback logging â€” it does **not** reference `get_cache_path` as a public API. No Pydantic model or config template references it. Re-ran grep: `get_cache_path` has exactly 1 production match (the definition at `image_cache.py:39`) and 7 test matches (`tests/test_image_cache.py` lines 22, 23, 28, 33, 34, 39, 40). The extension divergence is confirmed: `get_cache_path` uses `original_path.suffix or ".jpg"` (preserves source extension) while `resize_image` derives `out_ext` from `img.mode in ("RGBA", "LA", "P")` â†’ `.png` else `.jpg`. For an opaque `.png` source the two would produce different filenames, defeating any cache lookup. The digest logic is duplicated verbatim. The recommendation (fix+document or remove) aligns with project rules (small focused modules, no dead code). Type kept as SPEC-DEVIATION: the method exists in the image-cache module whose contract is spec'd in Â§4.9, yet it is undocumented and diverges from the documented `resize_image` behavior.
> - **Rollout note:** If removed, `tests/test_image_cache.py::test_get_cache_path` and `::test_get_cache_path_consistency` must be removed in the same change. If fixed (alpha-aware), those tests must be updated to assert the normalized extension. No production callers exist, so either path is low-risk. Prefer removal unless an external caller is identified.
> - **See also:** none

---

### SRV-003: `Task.txt` typed `str` but populated with `Any` from sheet cells

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/task.py`, `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** The `Task` dataclass declares `txt: str` (`task.py:20`), implying a string
contract for downstream consumers. But the value placed into it is not guaranteed to be a
string:

- `PostProcessor._extract_text_value` returns `Any` â€” the raw `row[txt_col]` cell value
  (`post_processor.py:144-159`). Google Sheets returns typed cell values, so a cell containing
  a number (`42`), a boolean (`TRUE`/`FALSE` â†’ Python `bool`), or a date serial may flow
  through as a non-string.
- `PostProcessor.get_posts` stores posts as `list[list[Any]]` and appends
  `[txt_value, valid_photos]` where `txt_value` is `Any` (`post_processor.py:218`).
- `TelegramService._push_posts_to_queue` reads `post[0]` (typed `Any`) and assigns it directly
  to `Task(txt=post[0], ...)` (`telegram_service.py:110`). The `# type: ignore[arg-type]`
  on line 105 suppresses the mypy warning that `list[Any]` is being passed where `list[Path]`
  is expected; the same `Any`-leak affects `txt`.

Because `Task` is a plain `dataclass` (no validation), nothing coerces or rejects the value.
The non-string `txt` is then passed to `client.send_message(post.chat_id, post.txt, ...)`
(line 214) or as `caption=post.txt` to `send_file` (line 209). Telethon internally stringifies
captions, so the most common symptom is a silent type contract violation; in edge cases
(e.g. `None` text from an empty cell that slipped past the `not txt_value` filter because a
non-empty-but-falsy value like `0`/`False` was present) the message body or caption becomes
`"0"`/`"False"`/`"None"` rather than the intended human text.

This violates the project rule "Type Safety Everywhere" (`.kilo/rules/project.md` Â§9) and the
AGENTS.md "Pydantic v2 / type hints" guidance.

**Evidence:**
- `task.py:20` â€” `txt: str`
- `post_processor.py:159` â€” `return row[txt_col]` (return type `Any`)
- `post_processor.py:218` â€” `posts.append([txt_value, valid_photos])` (`txt_value: Any`)
- `telegram_service.py:110` â€” `txt=post[0]` (no `str(...)` coercion)
- `telegram_service.py:105` â€” `# type: ignore[arg-type]` masking the `Any` leak
- `telegram_service.py:209,214` â€” `caption=post.txt` / `send_message(..., post.txt, ...)`

**Recommendation:** Coerce text at the boundary in `PostProcessor._extract_text_value` â€”
return `str(row[txt_col])` when the cell is non-None and `""` when it is None/empty. This keeps
`Task.txt`'s `str` contract honest, removes the `Any`-leak, and lets the `# type: ignore` be
dropped. Effort: trivial. Priority: recommended.

> **Validation Note:**
> - **Action:** validated (unchanged, with evidence correction)
> - **Detail:** Core claim verified. `task.py` declares `txt: str` (no validation â€” plain `@dataclass`). `PostProcessor._extract_text_value` returns `row[txt_col]` with annotated return type `Any` and no coercion. `get_posts` stores `[txt_value, valid_photos]` into `list[list[Any]]`. `telegram_service._push_posts_to_queue` assigns `txt=post[0]` directly. The `not txt_value and not valid_photos` skip filter in `get_posts` indeed lets falsy non-string values (`0`, `False`) through when photos exist, which Telethon would stringify to `"0"`/`"False"` â€” a real type-contract violation against project rule Â§9. **Evidence correction:** the `# type: ignore[arg-type]` at the `_resolve_photo_paths` call suppresses the `list[Any]`â†’`list[Path]` mismatch for the *photos* argument only; it does **not** mask the `txt` leak. mypy treats `Any` as compatible with `str` by default, so `txt=post[0]` produces no error and needs no ignore â€” the leak is silent precisely because `Any` flows freely, not because an ignore hides it. The finding's conclusion (coerce at the boundary) is correct and unaffected; only the causal claim about the type-ignore is imprecise.
> - **Rollout note:** Changing `_extract_text_value` to return `str` is a boundary-localized change. The `# type: ignore[arg-type]` on the `_resolve_photo_paths` call is a separate issue (photos `Any`-leak) and should not be dropped as part of this finding. Verify no test asserts a non-string `txt` value reaching `Task`; if so, update the test to reflect the coerced contract.
> - **See also:** none

---

### SRV-004: `run()` logs every failure as "Telegram authentication failed"

| Field | Value |
|-------|-------|
| **ID** | SRV-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** In `TelegramService.run()`, the inner `try` block spans `client.start()`,
`_coordinate_posting(...)`, and `_cleanup_session(...)` (lines 306-311). Its `except Exception`
handler unconditionally logs `"Telegram authentication failed"` (line 314) and re-raises.

This is misleading: any exception raised by `_coordinate_posting` (e.g. an unhandled error in
the push/send loop, a `FloodWaitError` exhaustion path that escapes the retry loop, a network
failure during `send_file`) or by `_cleanup_session` (e.g. a permissions error on the session
file) is reported to operators as an authentication failure. During incident triage this
points the operator at credentials/auth when the actual cause is a posting or cleanup
failure, wasting investigation time.

The spec (`docs/SPEC.md` Â§4.6 security table) lists credential-isolation and CLI error
sanitization as controls but does not mandate this particular log message, so the message can
be corrected without a spec change.

**Evidence:**
- `telegram_service.py:305-315` â€”
  ```
  try:
      async with client:
          await client.start(**self._make_start_kwargs())
          await self._coordinate_posting(client, granges_data, used_cache_files)
          self._cleanup_session(session_path)
  except Exception:
      logger.error("Telegram authentication failed")
      raise
  ```
- `_coordinate_posting` raises nothing on its own, but the sending task it spawns can raise
  into `asyncio.gather` results; a `CancelledError` propagating out of `queue.join()` would
  also land here.

**Recommendation:** Replace `logger.error("Telegram authentication failed")` with
`logger.exception("Telegram client operation failed")` to make the message stage-accurate
(the same `except` handler covers auth, posting, and cleanup phases). Use `logger.exception`
instead of `logger.error` so the full exception type and traceback are captured at ERROR level,
giving operators enough detail to identify the failing stage without including the credential
value in the message text (credentials are already isolated by `_make_start_kwargs()` scope
boundary — lines 275-287). Additionally, move `self._cleanup_session(session_path)` to
immediately after `await client.start(...)` (coordinated with SRV-005) so the session file is
hardened regardless of which subsequent stage fails.

**Exact change** (file: `src/mko_telepost/core/telegram_service.py`, method `run`, lines 305-315):
```python
            try:
                async with client:
                    await client.start(**self._make_start_kwargs())
                    self._cleanup_session(session_path)          # <-- moved here (SRV-005)
                    await self._coordinate_posting(
                        client, granges_data, used_cache_files
                    )
            except Exception:
                logger.exception("Telegram client operation failed")  # <-- was logger.error("Telegram authentication failed")
                raise
```

This is a single, concrete, actionable change: 4 lines modified, no test impact (zero tests
assert the old message string). Effort: trivial. Priority: recommended. Ship combined with
SRV-005 (both touch the same region).

> **Validation Note:**
> - **Action:** code-fix-needed — SPEC describes hardening after `client.start()` succeeds; code applies after posting.
> - **Detail:** Verified in `telegram_service.run()`: the inner `try` wraps `client.start(...)`, `_coordinate_posting(...)`, and `_cleanup_session(session_path)`; the single `except Exception` logs `"Telegram authentication failed"` unconditionally and re-raises. The message is stage-inaccurate for any non-auth exception (posting errors, cleanup errors, `CancelledError` from `queue.join()`). SPEC Â§4.7 (`docs/SPEC.md:340-354`) lists "CLI error sanitization" as a control but mandates no specific log string, so correcting the message requires no spec change. No test asserts on the `"Telegram authentication failed"` string â€” grep found only `"OAuth2 authentication failed"` in `tests/test_gsheets_reader.py:212`, which is a different module/message â€” so the change has no test impact.
> - **Rollout note:** SECURITY: `_make_start_kwargs()` isolates credentials from the caller-frame traceback locals; the generic message may have been chosen to avoid surfacing credential context. The finding's fallback ("keep generic but drop 'authentication'") preserves the sanitization intent. Prefer `logger.exception("Telegram run failed")` which captures the traceback at log level without re-emitting caller locals in the message text. Coordinating with SRV-005 is recommended since both restructure the same `try` block.
> - **See also:** SRV-005

---

### SRV-005: Session file permissions timing [CODE-FIX-NEEDED] Session file permissions hardened only on the success path

| Field | Value |
|-------|-------|
| **ID** | SRV-005 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION (code lags behind docs — SPEC says "after client.start()")
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** The spec security table (`docs/SPEC.md` S4.6) lists "Set restrictive
permissions on session file after successful connection" as a control. The implementation in
`TelegramService.run()` calls `self._cleanup_session(session_path)` (which applies
`set_restrictive_permissions` to the `.session` file) **only after `_coordinate_posting` returns
successfully** (line 311). If `_coordinate_posting` raises (any posting/network error), the
`except Exception` block at line 313 re-raises and `_cleanup_session` is never reached, so the
`.session` file created by `client.start()` retains its umask-default permissions.

`create_client` does harden the **parent directory** (`telegram_poster.py:53`), which on POSIX
blocks traversal by other users and therefore limits exposure of the file regardless of its own
mode. The residual risk is narrow (multi-user hosts with shared group access, or restored
backups into a different directory) but real, and the code path does not match the spec's
"after successful connection" wording -- `client.start()` succeeding is the "successful
connection" point, yet the file perms are applied much later.

**Evidence:**
- `telegram_service.py:306-315` -- `_cleanup_session` called only on the success path; on
  exception it is skipped
- `telegram_service.py:404-414` -- `_cleanup_session` applies `set_restrictive_permissions`
  to the `.session` file
- `telegram_poster.py:50-53` -- parent directory perms hardened in `create_client`
- `docs/SPEC.md` S4.6 -- control described as "after successful connection"

**Recommendation:** Harden the session file immediately after `client.start()` succeeds
(move the `set_restrictive_permissions(session_file)` call to right after `await
client.start(...)`), so the control matches the spec and applies on every run that authenticates
-- including runs that subsequently fail during posting. Effort: trivial. Priority: recommended.

> **Validation Note:**
> - **Action:** code-fix-needed — SPEC describes hardening after `client.start()` succeeds; code applies after posting.
> - **Detail:** Verified code/spec mismatch. `telegram_service.run()` calls `self._cleanup_session(session_path)` *inside* the `async with client:` block, *after* `_coordinate_posting(...)` returns; on any exception from `_coordinate_posting` the `except Exception` re-raises and `_cleanup_session` is skipped. `_cleanup_session` computes `session_file = Path(str(session_path) + ".session")` and applies `set_restrictive_permissions(session_file)` only if it exists. By contrast, the SPEC is explicit and consistent across four locations: `docs/SPEC.md:316` ("Telethon `.session` file permissions after `client.start()`"), `docs/SPEC.md:320` ("applies `set_restrictive_permissions()` ... immediately after a successful connection"), `docs/SPEC.md:439` ("receives restrictive permissions after `client.start()` succeeds"), and `docs/00-overview/overview.md:51` ("protected after `client.start()` succeeds"). The code does not match: perms are applied after *posting* succeeds, not after *connection* succeeds. This is a genuine SPEC-DEVIATION (code should change to match the spec, not vice versa). Severity LOW is appropriate: `TelegramPoster.create_client` already hardens the parent directory (`telegram_poster.py:50-53`), which on POSIX blocks traversal by other users, narrowing residual exposure to shared-group or restored-backup scenarios.
> - **Rollout note:** Minimal change: invoke `set_restrictive_permissions` on the `.session` file immediately after `await client.start(...)` succeeds, before `_coordinate_posting`. The session file is created by Telethon during `client.start()`, so it exists at that point. The existing `_cleanup_session` can either be relocated or kept as an idempotent duplicate-hardening step (since `set_restrictive_permissions` is idempotent). No test asserts on the timing of session-file permission hardening within `run()` (grep of `tests/` for `_cleanup_session`/`set_restrictive_permissions` returns only direct `file_permissions` unit tests), so the change is test-safe. Coordinate with SRV-004 -- both restructure the same `try` block and are cleaner implemented together.
> - **See also:** SRV-004

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 1 |

## Mandatory Fixes

- **SRV-001** -- `max_photos` upper bound of 20 exceeds Telegram's 10-photo album limit;
  invalid configs pass validation and then fail per-post at runtime. Tighten to `le=10`.

## Advisory Recommendations

- **SRV-002** -- `ImageCache.get_cache_path` is undocumented dead code whose extension logic
  diverges from `resize_image`. Investigate purpose; either fix+document or remove.
- **SRV-003** -- `Task.txt` (`str`) is populated from `Any` sheet cells without coercion,
  breaking the type contract. Coerce to `str` at the `PostProcessor` boundary.
- **SRV-004** -- `run()` mislabels every failure as "Telegram authentication failed". Use
  `logger.exception(...)` with a stage-accurate message.
- **SRV-005** -- Session file permissions are only hardened on the success path. Harden right
  after `client.start()` succeeds.

## Doc Updates Needed

- None beyond the `max_photos` range change in SRV-001 (spec + `config-reference.md`).
---

## Validation Summary

| Action | Count | Details |
|--------|-------|--------|
| Validated (unchanged) | 5 | SRV-001, SRV-002, SRV-003, SRV-004, SRV-005 |
| Reclassified | 0 | -- |
| Merged | 0 | -- |
| Rejected | 0 | -- |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| -- | -- | No findings rejected. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| -- | -- | No findings merged. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| -- | -- | -- | No findings reclassified. |

### Cross-Phase Conflicts

None detected within this phase. This validation scoped to Phase 03 only; no cross-phase
findings were available for conflict analysis.

### Rollout Safety Analysis

| Finding | Dependencies | Sequencing | Risk |
|---------|--------------|-----------|------|
| SRV-001 | None. Must update spec + config-reference + error-reference + test docstring atomically with the validator change. | Independent -- can ship first. | LOW -- converts silent runtime failures to loud load-time errors; no test asserts 11-20 acceptance. |
| SRV-002 | None (no production callers). | Independent. | LOW -- removal requires deleting two test-only methods; fix requires updating those tests. |
| SRV-003 | None. Do NOT drop the photos `# type: ignore` (separate `Any`-leak). | Independent. | LOW -- boundary-localized; verify no test asserts non-string `txt`. |
| SRV-004 | Soft dependency on SRV-005 (both restructure `run()`'s `try`). | Ship together with SRV-005 for a clean single restructure. | LOW -- no test asserts the log message. |
| SRV-005 | Soft dependency on SRV-004. `set_restrictive_permissions` is idempotent, so a duplicate call is harmless. | Ship together with SRV-004. | LOW -- no test asserts permission timing; parent dir already hardened. |

No circular dependencies, no hidden dependency chains, no unsafe ordering. SRV-004 + SRV-005
share a code region and are cleaner as one combined change, but each is independently safe.

### Evidence Corrections Applied During Validation

- **SRV-003:** The finding states the `# type: ignore[arg-type]` at `telegram_service.py:105`
  "masks the `Any`-leak" for `txt`. This is imprecise: that ignore suppresses the
  `list[Any]` to `list[Path]` mismatch on the *photos* argument only. The `txt` leak is silent
  because mypy treats `Any` as compatible with `str` by default -- no ignore is needed or
  present for `txt=post[0]`. The finding's conclusion (coerce at the boundary) is unaffected.

### Warnings

- **Architectural risk (LOW):** SRV-001's `le=10` cap is a hardcoded constant matching a
  Telegram upstream limit. If Telegram raises the media-group cap, the validator must be
  bumped in one place. This is acceptable and preferable to the current silent-runtime-failure
  behavior.
- **Documentation risk (LOW):** SRV-001 touches five doc/test locations (SPEC.md,
  config-reference.md, error-reference.md, test docstring) plus two code locations -- all must
  move atomically to avoid code/doc drift.
- **Security consideration (SRV-004):** Any message rewrite must preserve the existing
  credential-sanitization posture. Do not include `phone_or_token`, `api_hash`, or session
  path in the log text. `logger.exception(...)` captures the traceback at log level without
  re-emitting caller-frame locals in the message, but ensure log handlers do not dump full
  local-variable reprs.

### Required Fixes

- **SRV-001** -- tighten `max_photos` to `le=10` (mandatory; HIGH severity).

### Advisory Recommendations

- **SRV-002, SRV-003, SRV-004, SRV-005** -- apply as time permits. All are low-risk,
  low-effort, and align with project rules. SRV-004 + SRV-005 recommended as a single change.