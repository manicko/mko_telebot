# Phase 03 Audit Findings — Service Layer & Business Logic

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/03-audit-services.md
**Status:** complete
**Validated:** no
**Mode:** problems-only

## Runtime Verification Summary

| Step | Result |
|------|--------|
| R1 — Import verification | OK — all service modules import cleanly |
| R2 — `ruff check` (6 service files) | All checks passed |
| R2 — `mypy` (6 service files) | Success: no issues found in 6 source files |
| R3 — `pytest tests/` | 224 passed in 1.21s |
| R4 — Dead code search | 1 instance found — see SRV-002 |

---

## Findings

### SRV-001: `max_photos` config allows up to 20 but Telegram album hard limit is 10

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
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
`failed_count`), and the run continues. The root cause — an invalid configuration value — is
never surfaced at validation time, so the operator only sees per-post "unexpected error" logs
with no link back to the `max_photos` setting.

**Evidence:**
- `chat_models.py:82` — `max_photos: int = Field(default=5, ge=1, le=20, ...)`
- `chat_models.py:176-183` — per-chat validator allows `1..20`
- `telegram_service.py:101` — `raw_photos = post[1][: chat.max_photos]`
- `telegram_service.py:206-211` — `await client.send_file(post.chat_id, files, caption=post.txt, ...)`
- `telegram_service.py:264-267` — catch-all `except Exception` returns `False`
- `docs/SPEC.md:249`, `docs/99-reference/config-reference.md:188,206` — document `le=20`
- Telegram API docs (`/api/files`, "Albums, grouped media"): "maximum 10 per media group"

**Recommendation:** Tighten the `max_photos` upper bound to `le=10` in both
`ChatDefaults` and the `ChatConfig.max_photos` validator (and update the spec/config docs to
match). This rejects invalid configurations at load time with a clear Pydantic validation
error instead of letting them through to a per-post API failure. If a future Telegram limit
change raises the cap, bump the validator in one place.

---

### SRV-002: `ImageCache.get_cache_path` is dead code and returns a path inconsistent with `resize_image`

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/image_cache.py` |
| **Classification** | advisory |

**Description:** `ImageCache.get_cache_path` (lines 39-51) is never called from production
code. A repository-wide search returns exactly one production definition site
(`image_cache.py:39`) and zero non-test call sites; the only callers are
`tests/test_image_cache.py` (`test_get_cache_path`, `test_get_cache_path_consistency`).
The spec documents `resize_image` and `cleanup_unused` as the public image-cache API
(`docs/SPEC.md` §4.9) but does **not** document `get_cache_path`, so per the project's dead-code
policy this is undocumented dead code rather than future-proofing.

More importantly, `get_cache_path` is **wrong** if anyone were to call it. It computes the
cache filename as `{digest}{ext}` where `ext = original_path.suffix or ".jpg"` — i.e. it
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
- `image_cache.py:39-51` — `get_cache_path` uses `original_path.suffix or ".jpg"`
- `image_cache.py:70-79` — `resize_image` recomputes digest and uses `out_ext` from alpha mode
- Grep `get_cache_path` across `src/`: 1 match (the definition only)
- Grep `get_cache_path` across `tests/`: 7 matches (test-only callers)
- `docs/SPEC.md` §4.9 lists only `resize_image` and `cleanup_unused` as image-cache guarantees

**Recommendation:** Investigate the intended purpose of `get_cache_path`. If it was meant as a
public lookup helper, fix it to match `resize_image`'s alpha-aware extension logic (or have
`resize_image` call it) and document it in SPEC §4.9. If it has no external caller, remove it
and let the tests exercise the real `resize_image` cache-hit path instead. Either way, the
extension inconsistency should be eliminated so the two code paths cannot diverge further.

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

- `PostProcessor._extract_text_value` returns `Any` — the raw `row[txt_col]` cell value
  (`post_processor.py:144-159`). Google Sheets returns typed cell values, so a cell containing
  a number (`42`), a boolean (`TRUE`/`FALSE` → Python `bool`), or a date serial may flow
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

This violates the project rule "Type Safety Everywhere" (`.kilo/rules/project.md` §9) and the
AGENTS.md "Pydantic v2 / type hints" guidance.

**Evidence:**
- `task.py:20` — `txt: str`
- `post_processor.py:159` — `return row[txt_col]` (return type `Any`)
- `post_processor.py:218` — `posts.append([txt_value, valid_photos])` (`txt_value: Any`)
- `telegram_service.py:110` — `txt=post[0]` (no `str(...)` coercion)
- `telegram_service.py:105` — `# type: ignore[arg-type]` masking the `Any` leak
- `telegram_service.py:209,214` — `caption=post.txt` / `send_message(..., post.txt, ...)`

**Recommendation:** Coerce text at the boundary in `PostProcessor._extract_text_value` —
return `str(row[txt_col])` when the cell is non-None and `""` when it is None/empty. This keeps
`Task.txt`'s `str` contract honest, removes the `Any`-leak, and lets the `# type: ignore` be
dropped. Effort: trivial. Priority: recommended.

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

The spec (`docs/SPEC.md` §4.6 security table) lists credential-isolation and CLI error
sanitization as controls but does not mandate this particular log message, so the message can
be corrected without a spec change.

**Evidence:**
- `telegram_service.py:305-315` —
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

**Recommendation:** Narrow the message to reflect the actual failing stage, or split the
`try`. Minimal fix: change the log to `logger.error("Telegram run failed", exc_info=True)`
(or `logger.exception(...)`) so the real exception type and traceback are captured instead of
being hidden behind a generic "authentication failed" label. If the intent was specifically to
mask credential details, keep the message generic but drop the word "authentication".
Effort: trivial. Priority: recommended.

---

### SRV-005: Session file permissions hardened only on the success path

| Field | Value |
|-------|-------|
| **ID** | SRV-005 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** The spec security table (`docs/SPEC.md` §4.6) lists "Set restrictive
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
"after successful connection" wording — `client.start()` succeeding is the "successful
connection" point, yet the file perms are applied much later.

**Evidence:**
- `telegram_service.py:306-315` — `_cleanup_session` called only on the success path; on
  exception it is skipped
- `telegram_service.py:404-414` — `_cleanup_session` applies `set_restrictive_permissions`
  to the `.session` file
- `telegram_poster.py:50-53` — parent directory perms hardened in `create_client`
- `docs/SPEC.md` §4.6 — control described as "after successful connection"

**Recommendation:** Harden the session file immediately after `client.start()` succeeds
(move the `set_restrictive_permissions(session_file)` call to right after `await
client.start(...)`), so the control matches the spec and applies on every run that authenticates
— including runs that subsequently fail during posting. Effort: trivial. Priority: recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 3 |
| LOW | 1 |

## Mandatory Fixes

- **SRV-001** — `max_photos` upper bound of 20 exceeds Telegram's 10-photo album limit;
  invalid configs pass validation and then fail per-post at runtime. Tighten to `le=10`.

## Advisory Recommendations

- **SRV-002** — `ImageCache.get_cache_path` is undocumented dead code whose extension logic
  diverges from `resize_image`. Investigate purpose; either fix+document or remove.
- **SRV-003** — `Task.txt` (`str`) is populated from `Any` sheet cells without coercion,
  breaking the type contract. Coerce to `str` at the `PostProcessor` boundary.
- **SRV-004** — `run()` mislabels every failure as "Telegram authentication failed". Use
  `logger.exception(...)` with a stage-accurate message.
- **SRV-005** — Session file permissions are only hardened on the success path. Harden right
  after `client.start()` succeeds.

## Doc Updates Needed

- None beyond the `max_photos` range change in SRV-001 (spec + `config-reference.md`).
