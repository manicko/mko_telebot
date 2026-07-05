# Phase 06 Audit Findings â€” End-to-End Data Flow (Validated)

**Executor:** auditor
**Validator:** validator
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** yes

---

## Validation Notes (Top-Level)

This report validates the Phase 06 data-flow findings against the live codebase
(`src/mko_telepost/core/utils.py`, `post_processor.py`, `task.py`, `image_cache.py`,
`telegram_service.py`) and cross-references Phases 03 and 04.

**Validation outcome:**

- **DF-001** â€” VALIDATED as `SPEC-DEVIATION`. The silent-data-loss path is real and
  reproduced by code inspection. Severity MEDIUM is appropriate. One additional
  documentation inconsistency found (see Validation Note under DF-001).
- **DF-002** â€” MERGED into Phase 03 **SRV-003**. Same root cause, same affected
  modules, same boundary fix. The Phase 06 cross-phase analysis incorrectly stated
  "no overlap"; see cross-phase conflict table below.

---

## Runtime Verification Results

| Step | Command | Result |
|------|---------|--------|
| R1 - Import Full Pipeline | `uv run python -c "import mko_telepost.app; ..."` | PASSED â€” `IMPORT OK` |
| R2 - Linter (ruff) | `uv run ruff check src/mko_telepost` | PASSED â€” `All checks passed!` (exit 0) |
| R2 - Type Checker (mypy) | `uv run mypy src/mko_telepost` | PASSED â€” `Success: no issues found in 21 source files` (exit 0) |
| R3 - Test Suite | `uv run pytest` | PASSED â€” `224 passed in 1.27s` (exit 0) |

**Validator re-confirmation:** All cited code locations match the current tree.
`get_dir_content` default extensions `("jpg", "jpeg")` confirmed at `utils.py:33`.
`_extract_photo_paths` call site at `post_processor.py:141` passes no `extensions`
override. `_extract_text_value` return type `Any` confirmed at `post_processor.py:144`.
`Task.txt: str` confirmed at `task.py:20` (finding cited line 14; the annotation is on
line 20 â€” minor citation drift, content correct).

---

## Findings

### DF-001: Directory photo entries with non-JPEG formats silently produce un-sendable directory paths

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Code path fully confirmed. `get_dir_content` defaults to
>   `("jpg", "jpeg")`; `_extract_photo_paths` passes no override; the
>   `if raw else [Path(raw_entry_resolved)]` fallback (line 142) returns the
>   directory itself when the directory holds no jpg/jpeg. `_validate_photo_path`
>   (line 80-104) only checks existence + containment, so a directory passes.
>   `ImageCache.resize_image` catches `Exception` and returns the path unchanged
>   (line 100-101). `_try_send_message` then sends the directory path to Telethon,
>   which fails and is swallowed by the generic `except Exception` (line 264).
>   End-to-end silent post loss confirmed.
> - **Additional doc inconsistency:** `docs/11-guides/troubleshooting.md` is
>   internally contradictory â€” line 138 states "Supported formats: JPEG, PNG, and
>   other Pillow-supported formats", while line 146 states "For directories:
>   ensure they contain `.jpg` or `.jpeg` files". SPEC Â§5.2 (line 380) also
>   states resize output is normalized "regardless of source format". This
>   strengthens the case that the jpg/jpeg-only directory filter is an unintended
>   deviation, not a documented restriction.
> - **Rollout dependency:** See Phase 04 **SEC-004** â€” both findings modify
>   `_extract_photo_paths`. Coordinated rollout required (see Rollout Analysis).

| Field | Value |
|-------|-------|
| **ID** | DF-001 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/utils.py`, `src/mko_telepost/core/image_cache.py` |
| **Classification** | mandatory |

**Description:** The SPEC (Â§5.3, `docs/SPEC.md:415-419`) documents "Resolve directories (`get_dir_content`)" as a defined step of the image-processing pipeline, implying that a photo cell may contain a directory path whose contained images are posted. However, `get_dir_content()` (`utils.py:31-44`) hardcodes `extensions=("jpg", "jpeg")` as its default, and `_extract_photo_paths()` (`post_processor.py:116-142`) calls it without overriding that default:

```python
raw_entry_resolved = base_dir / raw_entry
raw = get_dir_content(raw_entry_resolved)
return [Path(p) for p in raw] if raw else [Path(raw_entry_resolved)]
```

When the referenced directory contains only non-JPEG files (e.g. PNG, WebP), `get_dir_content()` returns `[]`, and the `if raw else ...` fallback returns the **directory path itself** as the sole "photo". That directory path then flows unchanged through every downstream stage:

1. `_validate_photo_path()` (`post_processor.py:63-104`) only checks `resolved.exists()` / containment â€” a directory passes both checks, so it is returned as a "valid photo".
2. `ImageCache.resize_image()` (`image_cache.py:53-101`) calls `Image.open(directory)`, which raises; the outer `except Exception: return image_path` returns the directory path unchanged.
3. `_resolve_photo_paths()` (`telegram_service.py:119-135`) logs a "Resize fallback" warning and appends the directory path to `post.photos`.
4. `_try_send_message()` (`telegram_service.py:177-273`) calls `client.send_file(chat_id, [directory_path], caption=...)`, which fails. The failure is swallowed by the generic `except Exception` handler (line 264) â†’ the post is recorded as failed and **never delivered**.

The result is silent data loss for an entire post whenever a user organizes photos in a folder containing non-JPEG images â€” a configuration the SPEC explicitly enables by documenting directory resolution. The failure surfaces only as a generic "Unexpected error sending to '<chat>'" log line, with no indication that the root cause is an unsupported image extension in a directory entry.

**Evidence:**

- `src/mko_telepost/core/utils.py:31-44` â€” `get_dir_content` signature defaults to `extensions=("jpg", "jpeg")`.
- `src/mko_telepost/core/post_processor.py:140-142` â€” call site passes no `extensions` argument.
- `src/mko_telepost/core/post_processor.py:80-104` â€” `_validate_photo_path` accepts directories (existence-only check).
- `src/mko_telepost/core/image_cache.py:100-101` â€” `except Exception: return image_path` masks the directory-open failure.
- `docs/SPEC.md:416` â€” "Resolve directories (`get_dir_content`)" is a documented pipeline step.
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
- Test gap: every `test_postprocessor.py` test patches `get_dir_content` (e.g. `@patch("mko_telepost.core.post_processor.get_dir_content")` at lines 214, 258, 293, 347, 379, 416, 454, 487), so the real extension-filtering fallback is never exercised by the suite. **Validator confirmed:** 30 patch occurrences found across `test_postprocessor.py`.

**Recommendation:** Widen `get_dir_content`'s default extensions to match the common image formats that PIL / `ImageCache.resize_image` can process. This is the single recommended approach for the following reasons:

1. **SPEC alignment:** §4.9 explicitly states that resize output is normalized "regardless of source format" — the architecture already assumes multi-format support. §5.3 documents "Resolve directories" as a standard pipeline step without a JPEG-only restriction.
2. **Implementation already handles it:** `ImageCache.resize_image` (`image_cache.py:53-101`) opens any PIL-supported format via `Image.open()` and normalizes to JPEG/PNG — widening the extension list requires zero changes in `image_cache.py`.
3. **User experience:** Users organizing photos in mixed-format folders (e.g., a mix of JPEG and PNG screenshots) currently lose entire posts silently. Widening extensions fixes this for the common case without adding configuration surface.
4. **Documentation consistency:** The `troubleshooting.md` line 138 already states "Supported formats: JPEG, PNG, and other Pillow-supported formats" — the code change aligns the implementation with the existing documentation. Line 146's contradictory jpg/jpeg-only restriction is removed.

**Exact changes:**

1. `src/mko_telepost/core/utils.py:33` — Change default:
   ```python
   extensions: tuple[str, ...] = ("jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "tif"),
   ```

2. `src/mko_telepost/core/post_processor.py:140-142` — Replace the silent-data-loss fallback with a WARNING log and return `[]`:
   ```python
   raw = get_dir_content(raw_entry_resolved)
   if raw:
       return [Path(p) for p in raw]
   logger.warning("No supported image files found in directory: %s", raw_entry_resolved)
   return []
   ```

3. `docs/SPEC.md` §5.3 — Change the bullet to: "Resolve directories (`get_dir_content`) — returns files with common image extensions (JPEG, PNG, WebP, GIF, BMP, TIFF)".

4. `docs/11-guides/troubleshooting.md:146` — Remove the sentence "For directories: ensure they contain `.jpg` or `.jpeg` files".

**Implementation sequence:** SEC-004 first (containment check in `_extract_photo_paths`), then DF-001 (widen extensions + log warning + return `[]`). The two changes touch the same function body — SEC-004 adds the containment check before filesystem access, DF-001 adjusts the extension filter. **Effort: small** (one tuple in `utils.py`, one return-value restructure + log line in `post_processor.py`, two doc edits).

### DF-002: Post text value is not coerced to `str`, violating the Task contract and silently dropping falsy non-string rows [MERGED â†’ SRV-003]

> **Validation Note:**
> - **Action:** merged
> - **Merged into:** Phase 03 **SRV-003** ("`Task.txt` typed `str` but populated with `Any` from sheet cells").
> - **Detail:** DF-002 and SRV-003 describe the **same root cause**: `_extract_text_value` returns `Any` from `row[txt_col]` without `str(...)` coercion; the `Any` value flows into `Task(txt=post[0], ...)` whose field is annotated `txt: str`; no validation enforces the contract. The recommended fix is byte-identical â€” coerce at the extraction boundary (`return str(row[txt_col])` for non-None, `""` for None) in `PostProcessor._extract_text_value`. Affected modules are identical (`post_processor.py`, `task.py`, `telegram_service.py`).
> - **Phase 06 cross-phase analysis error:** The original findings.md stated "DF-002 | None | New, data-flow-specific. Type-coercion gap at the extraction boundary is not covered by other phases." This is **factually wrong** â€” SRV-003 (Phase 03) covers exactly this gap and was filed first. The validator flags this as a missed cross-phase duplicate.
> - **DF-002 incremental value preserved:** DF-002 additionally articulates the "silent row drop" angle â€” the `if not txt_value and not valid_photos: continue` guard (line 215) treats falsy non-string cell values (`0`, `False`) as "empty content" and drops the row. This is a behavioral consequence of the same root cause and must be addressed by the same fix (after coercion, only `""` is falsy among strings). SRV-003's description already notes this (`None` text slipping past the `not txt_value` filter). No separate fix required.
> - **See also:** Phase 03 SRV-003, Phase 03 validation report.

| Field | Value |
|-------|-------|
| **ID** | DF-002 (MERGED â†’ SRV-003) |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/task.py`, `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** The Google Sheets API v4 returns cell values as JSON scalars â€” a cell may legitimately be a number, boolean, or null. `_extract_text_value()` (`post_processor.py:144-159`) returns the raw `row[txt_col]` value typed as `Any`:

```python
def _extract_text_value(self, row: list[Any], txt_col: int) -> Any:
    if txt_col >= len(row):
        logger.warning(...)
        return ""
    return row[txt_col]
```

This `Any` value then flows through the entire pipeline without coercion:

1. It is stored as `post[0]` in `get_posts()` (`post_processor.py:218`).
2. It is passed to `Task(txt=post[0], ...)` (`telegram_service.py:110`), whose dataclass field is annotated `txt: str` (`task.py:20`) â€” a type-contract violation that `mypy` cannot catch because the source is `Any` (masked by `# type: ignore[arg-type]` at `telegram_service.py:105`).
3. It reaches Telethon as `client.send_message(post.chat_id, post.txt, ...)` (`telegram_service.py:214`) or `caption=post.txt` (line 209). Telethon expects a `str`; passing an `int`/`float`/`bool` may raise or produce an unintended string representation (`"True"`, `"12345"`).

Additionally, the empty-content guard in `get_posts()` uses a truthiness check:

```python
if not txt_value and not valid_photos:
    continue
```

Because `txt_value` is `Any`, this check conflates "empty content" with "falsy non-string value". A row whose text cell is the integer `0` or the boolean `False` is **silently dropped** as if it had no text, even though the user may have intentionally entered that value. The same row with a valid photo is kept, but its `txt` is a non-string that later fails at the Telethon boundary.

The dataclass annotation `txt: str` implies a contract that is never enforced; the actual runtime type is "whatever the Sheets API returned".

**Evidence:**

- `src/mko_telepost/core/post_processor.py:144-159` â€” `_extract_text_value` return type is `Any`, returns `row[txt_col]` unchanged.
- `src/mko_telepost/core/post_processor.py:215` â€” `if not txt_value and not valid_photos: continue` (truthiness on `Any`).
- `src/mko_telepost/core/task.py:20` â€” `txt: str` annotation, but no validation (plain `@dataclass`).
- `src/mko_telepost/core/telegram_service.py:105,110` â€” `# type: ignore[arg-type]` masking `Any` leak; `txt=post[0]` (source is `Any` from `get_posts`).
- `src/mko_telepost/core/telegram_service.py:209,214` â€” passed directly to Telethon `caption=` / `send_message`.
- Runtime confirmation:
  ```
  txt value: 12345 type: int
  txt value: True type: bool
  ```
  A numeric cell value `12345` passes through `_extract_text_value` as `int` and would reach `client.send_message` unmodified.

**Recommendation (superseded by SRV-003):** Coerce the text value to `str` at the extraction boundary so the rest of the pipeline can rely on the `Task.txt: str` contract. The smallest change is in `_extract_text_value`: return `str(row[txt_col])` for non-`None` values (and `""` for `None`), or use `"" if row[txt_col] is None else str(row[txt_col])`. This also makes the `if not txt_value` guard behave correctly (only `""` is falsy among strings) and allows dropping the `# type: ignore[arg-type]` at `telegram_service.py:105`. Effort: **trivial**. Implementation should be tracked under **SRV-003** (Phase 03) to avoid duplicate fix tickets.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 1 |

## Mandatory Fixes

- **DF-001** â€” Directory photo entries with non-JPEG formats silently produce un-sendable directory paths, causing post loss. Requires either widening `get_dir_content` extensions to match PIL-supported formats, or rejecting directory entries loudly at extraction time, plus a SPEC Â§5.3 update to match the chosen behavior.

## Advisory Recommendations

- **DF-002 â†’ SRV-003** (merged) â€” Coerce `_extract_text_value` output to `str` at the extraction boundary so the `Task.txt: str` contract holds and falsy non-string cell values are not silently dropped or passed to Telethon unmodified. Trivial change, no architectural impact. **Track under SRV-003 (Phase 03).**

## Doc Updates Needed

- **DF-001** â€” `docs/SPEC.md` Â§5.3 (line 416) documents "Resolve directories (`get_dir_content`)" without stating the jpg/jpeg-only limitation. Update the SPEC to either reflect the wider extension support (if the code is widened) or explicitly document that only JPEG-containing directories are supported (if the code is tightened).
- **DF-001 (validator-added)** â€” `docs/11-guides/troubleshooting.md` is internally inconsistent: line 138 ("JPEG, PNG, and other Pillow-supported formats") contradicts line 146 ("ensure they contain `.jpg` or `.jpeg` files"). Reconcile whichever direction is chosen for DF-001. The two lines must not remain contradictory.

---

## Cross-Phase Conflict Analysis

| Finding | Conflicting With | Resolution |
|---------|---------------|------------|
| DF-001 | **Phase 04 SEC-004** (rollout dependency, not a conflict) | Both modify `_extract_photo_paths`. See Rollout Analysis. Not a duplicate â€” DF-001 addresses silent data loss from extension filtering; SEC-004 addresses filesystem probing before containment validation. Distinct root causes, shared fix location. |
| DF-002 | **Phase 03 SRV-003** (DUPLICATE â€” missed by auditor) | **MERGED â†’ SRV-003.** Same root cause, same modules, same boundary fix. Original Phase 06 analysis incorrectly claimed "no overlap". |

### Validator-Added Cross-Phase Conflict

> **V-DF-001: Missed cross-phase duplicate (DF-002 â†” SRV-003)**
>
> The Phase 06 findings.md Cross-Phase Conflict Analysis table listed DF-002 as having "None" conflict, asserting the type-coercion gap "is not covered by other phases". This is incorrect â€” Phase 03 SRV-003 covers the identical gap (same function, same field, same fix recommendation, same affected modules). DF-002 has been merged into SRV-003. The DF-002 incremental "silent row drop" observation is preserved as a consequence of the SRV-003 fix, not a separate ticket.

---

## Rollout Analysis

### Rollout Safety â€” DF-001

**Shared fix location with Phase 04 SEC-004:**

- **DF-001** recommends changing `_extract_photo_paths` (`post_processor.py:140-142`) to
  either widen the extension list or reject directory entries loudly.
- **SEC-004** (Phase 04) recommends moving the containment check into
  `_extract_photo_paths` **before** calling `get_dir_content`, to honor the
  "prevent probing" invariant.

Both fixes touch the same function body and the same call to
`get_dir_content(raw_entry_resolved)`. If implemented independently they will conflict
(a merge conflict in source, and potentially re-introducing one another's gap).

**Required sequencing:**

1. **SEC-004 first** â€” relocate the containment check to run before any filesystem
   access inside `_extract_photo_paths`. This establishes the validation boundary.
2. **DF-001 second** â€” adjust the extension behavior (widen or reject) inside the
   now-secured function. The extension decision interacts with SEC-004: if DF-001
   chooses "reject directory entries loudly and return `[]`", then
   `get_dir_content` is no longer reached for directory entries and the SEC-004
   probing concern is partially mitigated by construction. If DF-001 chooses
   "widen extensions", `get_dir_content` still runs and SEC-004's pre-validation
   remains strictly necessary.

**Backward compatibility:** Either DF-001 resolution is a behavior change for users
who currently rely on JPEG-only directory resolution. The current behavior is
already broken (silent post loss), so the change is strictly an improvement.
Widening extensions is the least surprising option for users organizing photos in
mixed-format folders.

### Rollout Safety â€” DF-002 / SRV-003

No sequencing dependency. The fix is localized to `_extract_text_value` (single
function, `post_processor.py:144-159`) and a follow-up removal of the
`# type: ignore[arg-type]` at `telegram_service.py:105`. No other findings touch
this code path. Trivial, low-risk, no rollback concern.

### Rollout Safety â€” DF-001 Doc Update

The SPEC Â§5.3 and `troubleshooting.md` updates must ship **together** with the
code change, not before (would temporarily misdescribe behavior) and not after
(would leave a documented-but-unimplemented state). The validator notes the
`troubleshooting.md` internal contradiction (line 138 vs 146) exists **today**, so
that doc fix is independently valid regardless of the DF-001 code decision.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | DF-001 |
| Reclassified | 0 | â€” |
| Merged | 1 | DF-002 â†’ SRV-003 (Phase 03) |
| Rejected | 0 | â€” |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| â€” | â€” | No findings rejected. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| DF-002 | SRV-003 (Phase 03) | Identical root cause (`_extract_text_value` returns `Any`, no `str()` coercion into `Task.txt: str`), identical affected modules (`post_processor.py`, `task.py`, `telegram_service.py`), identical boundary fix. Phase 06 cross-phase analysis erroneously claimed no overlap; SRV-003 was filed first and is the canonical tracking finding. DF-002's "silent row drop" observation is preserved as a consequence of the SRV-003 fix. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|----------|
| â€” | â€” | â€” | No findings reclassified. |

---

## Warnings

- **Architectural risk (DF-001 Ã— SEC-004):** Two mandatory findings from different
  phases converge on the same function (`_extract_photo_paths`). Uncoordinated
  implementation will produce source merge conflicts and risks reintroducing one
  finding's gap while fixing the other. **Must be sequenced: SEC-004 before DF-001.**
- **Documentation inconsistency (pre-existing):** `docs/11-guides/troubleshooting.md`
  lines 138 and 146 contradict each other today, independent of any code change.
  This is a low-effort doc fix that should not wait for the DF-001 decision.
- **Citation drift:** DF-001 and DF-002 cite `task.py:14` for the `txt: str`
  annotation; the annotation is on `task.py:20` in the current tree. Content
  correct, line number stale. Non-blocking.
- **Test gap (DF-001):** Every `test_postprocessor.py` test mocks `get_dir_content`,
  so the real extension-filtering fallback (`if raw else [Path(raw_entry_resolved)]`)
  is never exercised end-to-end. Any fix for DF-001 should add an integration test
  with a real directory containing non-JPEG files.

## Required Fixes

1. **DF-001** â€” Resolve the directory-extension gap so a non-JPEG-only directory
   does not silently drop a post. Choose widen or reject; update SPEC Â§5.3 and
   `troubleshooting.md` to match. **Sequence after SEC-004 (Phase 04).**
2. **Reconcile `troubleshooting.md` lines 138/146** â€” independently valid doc fix,
   do not gate on DF-001 decision.

## Advisory Recommendations

1. **SRV-003 / DF-002** â€” Coerce `_extract_text_value` output to `str`; drop the
   `# type: ignore[arg-type]` at `telegram_service.py:105`. Track under SRV-003.
2. **Add integration test for `get_dir_content` fallback** â€” currently untested
   due to pervasive mocking; protects against DF-001 regression.

---

## Execution Validation

- **DF-001:** Execution-ready pending the design decision (widen vs reject). Not
  blocked by stale targets â€” `_extract_photo_paths`, `get_dir_content`,
  `_validate_photo_path`, `ImageCache.resize_image`, and `_try_send_message` all
  verified present at cited locations. **Must be sequenced after SEC-004 (Phase 04)**
  due to shared function body.
- **DF-002:** Not independently executable â€” merged into SRV-003 (Phase 03).
  Execute under SRV-003.
- **Doc updates:** SPEC Â§5.3 and `troubleshooting.md` reconciliation are
  independently executable; the `troubleshooting.md` fix is executable immediately.

