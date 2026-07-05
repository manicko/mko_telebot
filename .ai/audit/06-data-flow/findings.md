# Phase 06 Audit Findings — End-to-End Data Flow

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

---

## Runtime Verification Results

| Step | Command | Result |
|------|---------|--------|
| R1 - Import Full Pipeline | `uv run python -c "import mko_telepost.app; import mko_telepost.core.telegram_service; ..."` | PASSED — `IMPORT OK` (all pipeline modules importable) |
| R2 - Linter (ruff) | `uv run ruff check src/mko_telepost` | PASSED — `All checks passed!` (exit 0) |
| R2 - Type Checker (mypy) | `uv run mypy src/mko_telepost` | PASSED — `Success: no issues found in 21 source files` (exit 0) |
| R3 - Test Suite | `uv run pytest` | PASSED — `224 passed in 1.27s` (exit 0) |

---

## Findings

### DF-001: Directory photo entries with non-JPEG formats silently produce un-sendable directory paths

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/utils.py`, `src/mko_telepost/core/image_cache.py` |
| **Classification** | mandatory |

**Description:** The SPEC (§5.3, `docs/SPEC.md:415-419`) documents "Resolve directories (`get_dir_content`)" as a defined step of the image-processing pipeline, implying that a photo cell may contain a directory path whose contained images are posted. However, `get_dir_content()` (`utils.py:31-44`) hardcodes `extensions=("jpg", "jpeg")` as its default, and `_extract_photo_paths()` (`post_processor.py:116-142`) calls it without overriding that default:

```python
raw_entry_resolved = base_dir / raw_entry
raw = get_dir_content(raw_entry_resolved)
return [Path(p) for p in raw] if raw else [Path(raw_entry_resolved)]
```

When the referenced directory contains only non-JPEG files (e.g. PNG, WebP), `get_dir_content()` returns `[]`, and the `if raw else ...` fallback returns the **directory path itself** as the sole "photo". That directory path then flows unchanged through every downstream stage:

1. `_validate_photo_path()` (`post_processor.py:63-104`) only checks `resolved.exists()` / containment — a directory passes both checks, so it is returned as a "valid photo".
2. `ImageCache.resize_image()` (`image_cache.py:53-101`) calls `Image.open(directory)`, which raises; the outer `except Exception: return image_path` returns the directory path unchanged.
3. `_resolve_photo_paths()` (`telegram_service.py:119-135`) logs a "Resize fallback" warning and appends the directory path to `post.photos`.
4. `_try_send_message()` (`telegram_service.py:177-273`) calls `client.send_file(chat_id, [directory_path], caption=...)`, which fails. The failure is swallowed by the generic `except Exception` handler (line 264) → the post is recorded as failed and **never delivered**.

The result is silent data loss for an entire post whenever a user organizes photos in a folder containing non-JPEG images — a configuration the SPEC explicitly enables by documenting directory resolution. The failure surfaces only as a generic "Unexpected error sending to '<chat>'" log line, with no indication that the root cause is an unsupported image extension in a directory entry.

**Evidence:**

- `src/mko_telepost/core/utils.py:31-44` — `get_dir_content` signature defaults to `extensions=("jpg", "jpeg")`.
- `src/mko_telepost/core/post_processor.py:140-142` — call site passes no `extensions` argument.
- `src/mko_telepost/core/post_processor.py:80-104` — `_validate_photo_path` accepts directories (existence-only check).
- `src/mko_telepost/core/image_cache.py:100-101` — `except Exception: return image_path` masks the directory-open failure.
- `docs/SPEC.md:416` — "Resolve directories (`get_dir_content`)" is a documented pipeline step.
- Runtime confirmation:
  ```
  PNG-only dir: []
  JPG dir: ['b.jpg']
  ```
  And end-to-end through `PostProcessor.get_posts()` with a `content/photos` directory holding only `a.png`:
  ```
  Posts: [['hello', [WindowsPath('.../content/photos')]]]
  Photo path is directory? True
  ```
- Test gap: every `test_postprocessor.py` test patches `get_dir_content` (e.g. `@patch("mko_telepost.core.post_processor.get_dir_content")` at lines 214, 258, 293, 347, 379, 416, 454, 487), so the real extension-filtering fallback is never exercised by the suite.

**Recommendation:** Decide whether directory entries are a supported configuration and make the behavior consistent with that decision. If directories are supported (as the SPEC states), `_extract_photo_paths` should pass an extension list that matches what `image_cache.resize_image` can actually process (PIL supports PNG, WebP, GIF, BMP, etc.), or `get_dir_content` should accept `extensions=None` meaning "all files". If only JPEG directories are supported, update SPEC §5.3 to state that restriction explicitly and have `_validate_photo_path` reject directory paths (or `_extract_photo_paths` warn and return `[]` instead of the directory itself) so the post is dropped loudly at extraction time rather than failing silently at send time. The latter (reject/warn at extraction) is the smaller, safer change; widening the extension list is the more user-friendly one.

---


### DF-002: Post text value is not coerced to `str`, violating the Task contract and silently dropping falsy non-string rows

| Field | Value |
|-------|-------|
| **ID** | DF-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/task.py`, `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** The Google Sheets API v4 returns cell values as JSON scalars — a cell may legitimately be a number, boolean, or null. `_extract_text_value()` (`post_processor.py:144-159`) returns the raw `row[txt_col]` value typed as `Any`:

```python
def _extract_text_value(self, row: list[Any], txt_col: int) -> Any:
    if txt_col >= len(row):
        logger.warning(...)
        return ""
    return row[txt_col]
```

This `Any` value then flows through the entire pipeline without coercion:

1. It is stored as `post[0]` in `get_posts()` (`post_processor.py:218`).
2. It is passed to `Task(txt=post[0], ...)` (`telegram_service.py:110`), whose dataclass field is annotated `txt: str` (`task.py:14`) — a type-contract violation that `mypy` cannot catch because the source is `Any`.
3. It reaches Telethon as `client.send_message(post.chat_id, post.txt, ...)` (`telegram_service.py:214`) or `caption=post.txt` (line 209). Telethon expects a `str`; passing an `int`/`float`/`bool` may raise or produce an unintended string representation (`"True"`, `"12345"`).

Additionally, the empty-content guard in `get_posts()` uses a truthiness check:

```python
if not txt_value and not valid_photos:
    continue
```

Because `txt_value` is `Any`, this check conflates "empty content" with "falsy non-string value". A row whose text cell is the integer `0` or the boolean `False` is **silently dropped** as if it had no text, even though the user may have intentionally entered that value. The same row with a valid photo is kept, but its `txt` is a non-string that later fails at the Telethon boundary.

The dataclass annotation `txt: str` implies a contract that is never enforced; the actual runtime type is "whatever the Sheets API returned".

**Evidence:**

- `src/mko_telepost/core/post_processor.py:144-159` — `_extract_text_value` return type is `Any`, returns `row[txt_col]` unchanged.
- `src/mko_telepost/core/post_processor.py:215` — `if not txt_value and not valid_photos: continue` (truthiness on `Any`).
- `src/mko_telepost/core/task.py:14,19-25` — `txt: str` annotation, but no validation (plain `@dataclass`).
- `src/mko_telepost/core/telegram_service.py:110` — `txt=post[0]` (source is `Any` from `get_posts`).
- `src/mko_telepost/core/telegram_service.py:209,214` — passed directly to Telethon `caption=` / `send_message`.
- Runtime confirmation:
  ```
  txt value: 12345 type: int
  txt value: True type: bool
  ```
  A numeric cell value `12345` passes through `_extract_text_value` as `int` and would reach `client.send_message` unmodified.

**Recommendation:** Coerce the text value to `str` at the extraction boundary so the rest of the pipeline can rely on the `Task.txt: str` contract. The smallest change is in `_extract_text_value`: return `str(row[txt_col])` for non-`None` values (and `""` for `None`), or use `"" if row[txt_col] is None else str(row[txt_col])`. This also makes the `if not txt_value` guard behave correctly (only `""` is falsy among strings). Effort: **trivial**. Priority: **recommended** — it closes a real type-safety gap and prevents both silent row drops and Telethon-side type errors, with no architectural impact.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 1 |

## Mandatory Fixes

- **DF-001** — Directory photo entries with non-JPEG formats silently produce un-sendable directory paths, causing post loss. Requires either widening `get_dir_content` extensions to match PIL-supported formats, or rejecting directory entries loudly at extraction time, plus a SPEC §5.3 update to match the chosen behavior.

## Advisory Recommendations

- **DF-002** — Coerce `_extract_text_value` output to `str` at the extraction boundary so the `Task.txt: str` contract holds and falsy non-string cell values are not silently dropped or passed to Telethon unmodified. Trivial change, no architectural impact.

## Doc Updates Needed

- **DF-001** — `docs/SPEC.md` §5.3 (line 416) documents "Resolve directories (`get_dir_content`)" without stating the jpg/jpeg-only limitation. Update the SPEC to either reflect the wider extension support (if the code is widened) or explicitly document that only JPEG-containing directories are supported (if the code is tightened).

---

## Cross-Phase Conflict Analysis

| Finding | Conflicting With | Resolution |
|---------|---------------|------------|
| DF-001 | None | New, data-flow-specific. Does not overlap with Phase 03/04 session-permission or log-message findings. |
| DF-002 | None | New, data-flow-specific. Type-coercion gap at the extraction boundary is not covered by other phases. |

Note: The "Telegram authentication failed" misleading log message and the session-file permissions-on-failure-path issue were already filed in Phase 03 (SRV-004, SRV-005) and Phase 04 (SEC-003). They are intentionally not re-reported here to avoid duplication.
