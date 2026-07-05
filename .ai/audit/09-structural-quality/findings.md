# Phase 09 Audit Findings — Structural Code Quality

**Executor:** auditor
**Template:** `.kilo/commands/audit/phases/09-structural-quality.md`
**Status:** complete
**Validated:** no

**Audit scope:** `src/mko_telepost/**/*.py`
**Tooling:** `uv run radon cc src/mko_telepost/ -a`, `uv run radon mi src/mko_telepost/ -s`, AST-based length/nesting/control-flow scan.

**Runtime verification summary (context, not a finding):**
- Radon CC: 101 blocks analyzed, average complexity A (3.18). No function ranks C or worse.
- Radon MI: all files rank A. Lowest: `core/telegram_service.py` (52.95).
- `core/post_processor.py` could not be analyzed by radon (see STR-001).

---

## Findings

### STR-001: `post_processor.py` starts with a UTF-8 BOM, breaking static analysis tooling

| Field | Value |
|-------|-------|
| **ID** | STR-001 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py` |
| **Classification** | advisory |

**Description:** `src/mko_telepost/core/post_processor.py` begins with a UTF-8 BOM (`EF BB BF`). Radon aborts parsing the file entirely (`ERROR: invalid non-printable character U+FEFF`), so no complexity, MI, or structural metrics could be collected for this 157-line module. The project's own rules require clean, toolable Python source; a BOM on a `.py` file is non-portable and breaks linters/complexity tools (and historically some interpreters/editors).

**Evidence:**
- `uv run python -c "...read_bytes()[:3]"` → `b'\xef\xbb\xbf'`
- `radon cc` output: `core\post_processor.py` → `ERROR: invalid non-printable character U+FEFF (<unknown>, line 1)` (no functions reported).
- `radon mi` output: same `ERROR` line, no MI score emitted.

**Recommendation:** Re-save `post_processor.py` as UTF-8 *without* BOM (e.g. `uv run python -c "import pathlib; p='src/mko_telepost/core/post_processor.py'; b=pathlib.Path(p).read_bytes(); pathlib.Path(p).write_bytes(b.lstrip(b'\xef\xbb\xbf'))"`). Add a CI guard (ruff/pre-commit) that rejects BOM in `.py` files. Effort: trivial. Priority: recommended.

---

### STR-002: `_send_posts()` has nesting depth 6 (pyramid of doom)

| Field | Value |
|-------|-------|
| **ID** | STR-002 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** `TelegramService._send_posts` nests control flow six levels deep: `try` → `while` → `try`/`finally` → `if chat_config` → `if should_micro_break` → statement. The phase guide treats nesting depth > 4 as HIGH. The mixing of queue draining, per-post delay scheduling, micro-break policy, and result bookkeeping in one loop makes the control flow hard to follow and hard to unit-test (the success/micro-break branch is buried five levels in).

**Evidence:** `src/mko_telepost/core/telegram_service.py:137-175`. AST scan reports `depth=6` for `_send_posts()`. Excerpt of the deepest branch:

```python
while True:                              # depth 2 (inside try)
    post = await queue.get()
    try:                                  # depth 3
        chat_config = self._chat_configs.get(int(post.chat_id))
        if chat_config:                   # depth 4
            ...
            if self.delay_engine.should_micro_break():   # depth 5
                micro_delay = self.delay_engine.get_micro_break_delay()
                await asyncio.sleep(micro_delay)          # depth 6
    finally:
        queue.task_done()
```

**Recommendation:** Extract the per-post body into a helper such as `_process_post(post, client, max_retries, used_cache_files) -> bool`, and lift the micro-break decision into a small `_maybe_micro_break(chat_config)` method. The remaining `_send_posts` loop then reads as: dequeue → process → bookkeep, at depth ≤ 3. Effort: small. Priority: recommended.

---

### STR-003: `_try_send_message()` is 77 lines with 4 return points and 3 except branches

| Field | Value |
|-------|-------|
| **ID** | STR-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** `TelegramService._try_send_message` (lines 177-273) is 77 non-blank/comment lines, exceeding the 50-line limit. It does four things in one body: build `reply_to_kwargs`, branch on "files vs no files", log success, and handle three distinct exception classes (permanent / flood / transient). Four return points plus a trailing fall-through return make the success/failure outcome hard to trace. This is the function where future Telegram API changes (new error types, new send modes) will accumulate, so it should be split while it is still manageable.

**Evidence:** `src/mko_telepost/core/telegram_service.py:177-273` (77 lines). Returns at lines 225 (success), 236 (permanent error), 267 (unexpected error), 273 (exhausted retries). Radon ranks it B (acceptable complexity, but length-driven maintainability risk).

**Recommendation:** Extract `_build_send_call(post)` (kwargs + dispatch to `send_file`/`send_message`) and `_handle_send_exception(e, post, attempt, max_retries)` returning a `Retry|Skip|Continue` decision, leaving `_try_send_message` as a thin retry loop with a single success return and a single terminal-failure return. Effort: small. Priority: recommended.

---

### STR-004: `telegram_service.py` exceeds the 300-line file limit

| Field | Value |
|-------|-------|
| **ID** | STR-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** `core/telegram_service.py` is 433 total lines (327 non-blank/comment), the only source file exceeding the 300-line guard. It owns client lifecycle (`__init__`, `_make_start_kwargs`), queue orchestration (`_push_posts_to_queue`, `_send_posts`, `_coordinate_posting`, `run`), and the actual send/retry logic (`_try_send_message`, `_resolve_photo_paths`, `_fetch_sheet_data`, `_cleanup_session`). Per the project's "small modules and functions" rule and single-responsibility principle, the send/retry logic (which mutates independently of orchestration) is a candidate for its own module.

**Evidence:** AST line-count scan: 327 non-blank/comment lines for `core/telegram_service.py`; next-largest is `app.py` at 249. Radon MI is the lowest in the project at 52.95.

**Recommendation:** Split out the send/retry concern into `core/telegram_sender.py` (a small class taking `client` + `settings.telethon.max_retries`), keeping `TelegramService` focused on orchestration and session lifecycle. This also makes `_try_send_message` independently testable without constructing a full `TelegramService`. Effort: medium. Priority: recommended.

---

### STR-005: `ImageCache.resize_image()` has nesting depth 5 and 4 return points

| Field | Value |
|-------|-------|
| **ID** | STR-005 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/image_cache.py` |
| **Classification** | advisory |

**Description:** `ImageCache.resize_image` (lines 53-101) nests five levels deep: `try` → `with Image.open` → `try` (save) → `except` → `if tmp_path.exists` → `try` (unlink) → `except OSError`. It returns the cache path on cache-hit and on successful write, the original `image_path` on save failure, on outer failure, and after cleanup — four return points, three of which mean "fall back to original". The cleanup-on-failure logic and the happy path are interleaved, so a reader must trace every branch to know what gets returned.

**Evidence:** `src/mko_telepost/core/image_cache.py:53-101`. AST scan reports `depth=5`, `returns=4`. Excerpt of the deepest branch:

```python
try:                                           # depth 1
    with Image.open(image_path) as img:        # depth 2
        ...
        try:                                   # depth 3
            img.save(tmp_path, format=out_format)
            tmp_path.rename(cache_path)
            return cache_path
        except Exception as e:                 # depth 3
            ...
            if tmp_path.exists():              # depth 4
                try:                           # depth 5
                    tmp_path.unlink()
                except OSError:
                    pass
            return image_path
except Exception:                              # depth 1
    return image_path
```

**Recommendation:** Extract `_save_thumbnail(img, tmp_path, cache_path, out_format) -> Path` (happy path) and `_safe_unlink(path)` (cleanup helper), so `resize_image` becomes a linear sequence: open → compute cache path → return if cached → save → return. This removes the nested cleanup block and collapses the multiple fallback returns to one. Effort: small. Priority: recommended.

---

### STR-006: `_load_and_validate_config()` has nesting depth 4 and 4 return points

| Field | Value |
|-------|-------|
| **ID** | STR-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/app.py` |
| **Classification** | advisory |

**Description:** The CLI helper `_load_and_validate_config` (lines 63-118) mixes path resolution, reader construction, file validation, error categorization, and user-facing Rich output. It nests `try` → `if custom_config_path is None` / `if errors` → `if critical_errors` → `for error in critical_errors`, reaching depth 4, and has four return points (file-not-found, critical-errors, generic-exception, and the implicit success). The intermixed `console.print` calls also make the function hard to unit-test without capturing stdout.

**Evidence:** `src/mko_telepost/app.py:63-118`. AST scan reports `depth=4`, `returns=4`.

**Recommendation:** Apply guard clauses: early-return on "config not found", then early-return on "critical errors" by delegating categorization/printing to `_validate_and_categorize_errors` (already extracted) and a small `_print_errors(...)` helper. This flattens the happy path to a single sequential read at depth ≤ 2 and removes one return point. Effort: small. Priority: recommended.

---

### STR-007: `_try_load_token()` has 4 return points

| Field | Value |
|-------|-------|
| **ID** | STR-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/gsheets_reader.py` |
| **Classification** | advisory |

**Description:** `GSheetsReader._try_load_token` (lines 118-141) returns `None` in four cases: token missing, read exception, scope mismatch, and the implicit `creds` return. The phase guide caps return statements at 3. The four returns are individually clear, but each represents a distinct "give up and re-authenticate" path that a future reader must enumerate.

**Evidence:** `src/mko_telepost/core/gsheets_reader.py:118-141`. AST scan reports `returns=4` (lines 124, 134, 139, 141).

**Recommendation:** Consolidate the three failure guards into a single early-exit using a small `Optional[OAuth2Credentials]` flow, or extract a `_scopes_match(creds)` predicate so the body reads: load → if invalid return None → if scopes differ reauth → return creds. This is borderline; only act if touching this method for another reason. Effort: trivial. Priority: recommended.


---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 4 |
| LOW | 1 |

## Mandatory Fixes

None. All findings in this phase are advisory structural-quality improvements.

## Advisory Recommendations

- STR-001: Strip UTF-8 BOM from post_processor.py and add a CI guard.
- STR-002: Flatten _send_posts() (nesting depth 6) via per-post extraction.
- STR-003: Split _try_send_message() (77 lines, 4 returns) into send + exception-handler helpers.
- STR-004: Split `telegram_service.py` (327 non-blank/comment lines) into orchestration + sender modules.
- STR-005: Flatten `resize_image()` (depth 5, 4 returns) by extracting save/unlink helpers.
- STR-006: Apply guard clauses to _load_and_validate_config() (depth 4, 4 returns).
- STR-007: Consolidate the 4 return paths in _try_load_token() (borderline).

## Doc Updates Needed

None.

