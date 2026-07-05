# Phase 08 Audit Findings — Code Quality, Security & Maintainability

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/08-audit-quality.md
**Status:** complete
**Validated:** no

## Runtime Verification Summary

- **R1 — Ruff:** `uv run ruff check src tests` → `All checks passed!`
- **R1 — Mypy:** `uv run mypy src` → `Success: no issues found in 21 source files`
- **R2 — Tests:** `uv run pytest tests` → `224 passed in 1.23s`
- **R3 — Dead code search:** performed via `grep`/`read` (see QLT-003, QLT-004, QLT-005).
- **R4 — Security search:** `print(`, `except:`, `TODO/FIXME`, hardcoded secrets, credential-logging — see findings below. No `print()` in production code (all matches are `console.print()` in `app.py` or comments/doctests). No bare `except:`. No `TODO/FIXME`. No hardcoded secrets beyond intentional template placeholders in `settings/app_config.yaml`.

Only problems are documented below.

---

## Findings

### QLT-001: `Any` type used across production modules, violating the "No `any` types" rule

| Field | Value |
|-------|-------|
| **ID** | QLT-001 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/telegram_service.py`, `src/mko_telepost/core/config_reader.py`, `src/mko_telepost/core/gsheets_reader.py`, `src/mko_telepost/core/utils.py` |
| **Classification** | advisory |

**Description:** The project rules (`AGENTS.md`, `.kilo/rules/project.md` rule 9, `.ai/context/python-code-standards.md`) require type safety everywhere and explicitly forbid `Any`. Despite `mypy --strict`-adjacent config passing, multiple production modules annotate with `Any`, defeating static analysis for those code paths. The worst offenders are the post-data containers (`list[list[Any]]`, covered separately in QLT-002) and the YAML/Sheets I/O boundaries.

**Evidence:**

- `src/mko_telepost/core/post_processor.py:10` — `from typing import TYPE_CHECKING, Any`; used at lines 116 (`row: list[Any]`), 144 (`row: list[Any]` / `-> Any`), 159 (`return row[txt_col]` typed `Any`), 183 (`gdata: list[list[Any]]`), 188 (`-> list[list[Any]]`), 202 (`posts: list[list[Any]]`).
- `src/mko_telepost/core/telegram_service.py:10` — `from typing import Any`; used at lines 77, 81, 105, 120, 183, 198, 324, 332, 361.
- `src/mko_telepost/core/config_reader.py:13` — `from typing import Any`; `dict[str, Any]` at lines 67, 132, 161, 177, 200.
- `src/mko_telepost/core/gsheets_reader.py:9` — `from typing import TYPE_CHECKING, Any`; `list[list[Any]]` return at line 219.
- `src/mko_telepost/core/utils.py:4` — `from typing import Any`; `dict[str, Any] | None` at line 11.

`grep -r ": Any\b|-> Any\b|list\[Any\]|dict\[str, Any\]" src` returns 1+ match in 5 modules.

**Recommendation:** Replace `Any` with concrete types:
- Google Sheets cell values: `str | int | float | bool | None` (or a `CellValue` alias) instead of `Any`.
- YAML config dicts: keep `dict[str, object]` (object is preferred over Any because it forces explicit casts at consumption points) or validate into Pydantic models immediately and drop the dict from public signatures.
- Post containers: see QLT-002 (introduce a `Post` model).
Effort: medium. Priority: recommended.

---

### QLT-002: Post data flows through untyped `list[list[Any]]` instead of a model

| Field | Value |
|-------|-------|
| **ID** | QLT-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

**Description:** A "post" is represented as a positional two-element list `[txt_value, valid_photos]`. The contract (index 0 = text, index 1 = photo list) exists only in the producer/consumer heads and is consumed by positional indexing in `telegram_service.py`. This violates "Pydantic for all data models" (`.kilo/rules/project.md` rule 11) and "no raw dicts/lists in business logic" (`AGENTS.md`). It is the root cause of the `# type: ignore[arg-type]` in `telegram_service.py:105` (QLT-008).

**Evidence:**

- `src/mko_telepost/core/post_processor.py:218` — `posts.append([txt_value, valid_photos])` builds the positional pair.
- `src/mko_telepost/core/post_processor.py:188` — `-> list[list[Any]]` return signature.
- `src/mko_telepost/core/telegram_service.py:101` — `raw_photos = post[1][: chat.max_photos]` (positional index 1).
- `src/mko_telepost/core/telegram_service.py:110` — `txt=post[0]` (positional index 0).
- `src/mko_telepost/core/telegram_service.py:77,81,183,324,332,361` — `granges_data: dict[str, list[list[Any]]]` propagated through 4 methods.

A future maintainer reordering the append in `post_processor.py` would silently break `telegram_service.py` with no type error.

**Recommendation:** Introduce a small dataclass or Pydantic model (e.g. `Post(txt: str, photos: list[Path])`) returned by `PostProcessor.get_posts` and stored in `granges_data: dict[str, list[Post]]`. Replace `post[0]`/`post[1]` with `post.txt`/`post.photos`. This removes the `Any` usage in the post path, eliminates the `type: ignore`, and makes the contract explicit.
Effort: small. Priority: recommended.

---

### QLT-003: ImageCache.get_cache_path is dead in production and diverges from esize_image

| Field | Value |
|-------|-------|
| **ID** | QLT-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telepost/core/image_cache.py |
| **Classification** | advisory |

**Description:** ImageCache.get_cache_path is defined as a public method but is never called from production code — only from 	ests/test_image_cache.py. Worse, it computes the cache filename using the original file's suffix (original_path.suffix or "".jpg""), whereas the actually-used esize_image method recomputes the cache path inline (lines 70-79) and chooses the extension from the image's alpha channel (.png for RGBA/LA/P, .jpg otherwise). The two implementations therefore produce **different** cache paths for the same input. A maintainer calling get_cache_path to predict where a resized image will land would get the wrong answer.

**Evidence:**

- src/mko_telepost/core/image_cache.py:39-51 — get_cache_path returns self.cache_dir / f"{digest}{ext}" where ext = original_path.suffix or "".jpg".
- src/mko_telepost/core/image_cache.py:70-79 — esize_image ignores get_cache_path and builds cache_path = self.cache_dir / f"{digest}{out_ext}" where out_ext is .png/.jpg based on img.mode.
- grep -r get_cache_path src → 1 match (the definition only). grep -r get_cache_path tests → 7 matches (tests only).

**Recommendation:** Investigate purpose. If get_cache_path is intended as a public API, unify it with esize_image's format-aware logic (extract a shared _cache_path_for(original_path, image_mode) helper and call it from both). If it is not intended as public API, remove it and update the tests. Keeping a divergent public method that returns wrong paths is a trap.
Effort: trivial. Priority: recommended.

---

### QLT-004: _coordinate_posting return value is dead; success/failure counts passed via undeclared instance attributes

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telepost/core/telegram_service.py |
| **Classification** | advisory |

**Description:** TelegramService._coordinate_posting declares -> tuple[int, int] and constructs that tuple from self._last_success_count / self._last_failed_count — instance attributes that are (a) never declared in __init__, (b) only set inside _send_posts's except asyncio.CancelledError branch, and (c) read back with getattr(self, "_last_success_count", 0). The caller un() (line 308) discards the returned tuple entirely. The contract is therefore implicit, fragile, and partially dead: if _send_posts ever exits without raising CancelledError, the attributes are never set and the tuple silently returns (0, 0).

**Evidence:**

- src/mko_telepost/core/telegram_service.py:308-310 — wait self._coordinate_posting(client, granges_data, used_cache_files) — return value ignored.
- src/mko_telepost/core/telegram_service.py:172-173 — self._last_success_count = success_count / self._last_failed_count = failed_count (set only in except asyncio.CancelledError).
- src/mko_telepost/core/telegram_service.py:400-401 — success_count = getattr(self, "_last_success_count", 0) / ailed_count = getattr(self, "_last_failed_count", 0).
- src/mko_telepost/core/telegram_service.py:51-71 — __init__ does not initialize _last_success_count / _last_failed_count.

**Recommendation:** Either consume the returned tuple in un() (and log a run summary), or drop the return type entirely. Initialize the counters in __init__ (e.g. self._last_success_count = 0) so the state is explicit, and prefer returning the counts through the normal return path of _send_posts (restructure so the sending coroutine returns the tuple instead of stashing it on self before cancellation).
Effort: small. Priority: recommended.

---

### QLT-005: GSheetsReader.get_sheet_data has dead fallback branches and a misleading docstring

| Field | Value |
|-------|-------|
| **ID** | QLT-005 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | src/mko_telepost/core/gsheets_reader.py |
| **Classification** | advisory |

**Description:** get_sheet_data declares spreadsheet_id: str and ange_name: str as required parameters with no default, yet the body contains fallback reassignments that only trigger on empty strings — a path no caller exercises. The docstring claims the parameters are optional, which is false. This is dead code plus a documentation lie that can mislead callers into relying on a fallback that does not meaningfully exist.

**Evidence:**

- src/mko_telepost/core/gsheets_reader.py:215-219 — signature: def get_sheet_data(self, spreadsheet_id: str, range_name: str) -> list[list[Any]]: (both required).
- src/mko_telepost/core/gsheets_reader.py:224 — docstring: "spreadsheet_id: Spreadsheet ID (uses config value if not provided)".
- src/mko_telepost/core/gsheets_reader.py:225 — docstring: "range_name: Range to retrieve (e.g., ""Sheet1!A1:Z100"")" (implies optional).
- src/mko_telepost/core/gsheets_reader.py:243-244 — spreadsheet_id = spreadsheet_id or self.config.spreadsheet_id / ange_name = range_name or "Sheet1!A1:Z100" — only triggers on ""/None; all callers (	elegram_service.py:337-340) pass real values.
- grep -rn "get_sheet_data(" src → only caller passes both args explicitly.

**Recommendation:** Remove the dead or fallbacks (lines 243-244) and correct the docstring to state both parameters are required. If config-fallback behavior is actually desired, make the parameters str | None = None and keep the branches.
Effort: trivial. Priority: recommended.

---

### QLT-006: TelegramPoster stores client config as a raw dict[str, Any] with string-keyed access

| Field | Value |
|-------|-------|
| **ID** | QLT-006 |
| **Severity** | LOW |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telepost/core/telegram_poster.py |
| **Classification** | advisory |

**Description:** TelegramPoster.__init__ calls settings.client.model_dump() and stores the resulting dict[str, Any] on self.client_config. create_client then accesses config["session"] by string key and mutates it. This violates "Pydantic for all data models — not raw dicts in business logic" (AGENTS.md, rule 11). The if "api_hash" in self.client_config: guard at line 35 is a symptom of untyped dict access: with a typed model the field's existence is guaranteed by the schema. A typo in any key (e.g. config["sesion"]) would fail at runtime, not at type-check time.

**Evidence:**

- src/mko_telepost/core/telegram_poster.py:34 — self.client_config = settings.client.model_dump().
- src/mko_telepost/core/telegram_poster.py:35-36 — if "api_hash" in self.client_config: then self.client_config["api_hash"] = settings.client.api_hash.get_secret_value() (manual secret extraction because model_dump() returns the SecretStr object).
- src/mko_telepost/core/telegram_poster.py:42-43,55 — config = self.client_config.copy(); config["session"] keyed access; config["session"] = str(session_path).
- src/mko_telepost/core/telegram_poster.py:57 — eturn TelegramClient(**config) (the dict exists only to splat into Telethon kwargs).

**Recommendation:** Keep a TelethonConfig/ClientConfig reference on the instance instead of a dict, and build the kwargs dict at call time in create_client from the typed fields (resolving session, extracting pi_hash.get_secret_value() there). This removes the in guard, the manual mutation, and the string-key fragility. The dict is only needed at the Telethon boundary, not as stored instance state.
Effort: small. Priority: recommended.

---

### QLT-007: Stray maintenance artifacts tracked in git at repo root

| Field | Value |
|-------|-------|
| **ID** | QLT-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | repo root (ix_readme_script.py, 	emp_findings.txt) |
| **Classification** | advisory |

**Description:** Two non-source artifacts sit at the repository root and are tracked by git. ix_readme_script.py is a 10.8 KB one-off script that embeds the entire README content as a string literal to regenerate README.md; it is not part of the package, not tested, and not referenced by any tooling. 	emp_findings.txt is a 4-byte file containing the literal string 	est — a leftover temp file. Both are listed in .ai/structure/map.md and docs/STRUCT.md, which means the structure docs have codified clutter rather than flagging it for removal. This bloats the repo root and makes the project structure harder to scan.

**Evidence:**

- git ls-files fix_readme_script.py temp_findings.txt → both tracked.
- 	emp_findings.txt content: 	est (4 bytes).
- ix_readme_script.py lines 1-40: a Python script whose body is a triple-quoted README string plus regeneration logic; no 	ests/ reference, no pyproject.toml entry.
- .ai/structure/map.md:7,10 and docs/STRUCT.md:7,10 list both files as part of the structure.

**Recommendation:** Remove 	emp_findings.txt (clearly a leftover). For ix_readme_script.py: if README regeneration is a maintained workflow, move it under a scripts/ directory and reference it from docs or CI; otherwise remove it. Update .ai/structure/map.md and docs/STRUCT.md to reflect the cleanup.
Effort: trivial. Priority: recommended.

---

### QLT-008: # type: ignore[arg-type] masks the untyped post structure

| Field | Value |
|-------|-------|
| **ID** | QLT-008 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telepost/core/telegram_service.py |
| **Classification** | advisory |

**Description:** A 	ype: ignore[arg-type] suppression is the only thing keeping mypy quiet when slicing photo data out of a post. It is a direct symptom of QLT-002 (posts typed as list[list[Any]]). pyproject.toml sets warn_unused_ignores = true, so the ignore is currently "used" — but only because the post type is Any. Once posts are typed (QLT-002), this ignore becomes unused and mypy will itself flag it as dead. Leaving the ignore in place documents that the surrounding code is not actually type-checked.

**Evidence:**

- src/mko_telepost/core/telegram_service.py:105 — esized_photos = self._resolve_photo_paths(raw_photos, max_w, max_h)  # type: ignore[arg-type].
- src/mko_telepost/core/telegram_service.py:101 — aw_photos = post[1][: chat.max_photos] where post is list[Any] (from granges_data: dict[str, list[list[Any]]]).
- pyproject.toml:140 — warn_unused_ignores = true.

**Recommendation:** Resolve QLT-002 first (type posts as a model), then delete this # type: ignore. Do not leave suppression comments as a substitute for types.
Effort: trivial (once QLT-002 is done). Priority: recommended.

---

### QLT-009: ImageCache.resize_image silently swallows all errors from Image.open

| Field | Value |
|-------|-------|
| **ID** | QLT-009 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telepost/core/image_cache.py |
| **Classification** | advisory |

**Description:** The outer 	ry/except around Image.open(image_path) catches Exception and returns the original image_path with **no logging whatsoever**. This violates AGENTS.md ("Never silently swallow errors") and core/errors.py's intent. When a photo fails to open (corrupt file, permission denied, unsupported format, truncated download), the service silently posts the original (potentially oversized/invalid) file, and operators have no log line to diagnose why uploads are misbehaving. The inner save block (line 92) logs correctly; the outer open block does not, which is inconsistent.

**Evidence:**

- src/mko_telepost/core/image_cache.py:74-101:
  `python
  try:
      with Image.open(image_path) as img:
          ...
          try:
              img.save(tmp_path, format=out_format)
              ...
          except Exception as e:
              logger.error(f"Error resizing image {image_path}: {e}")  # logged
              ...
              return image_path
  except Exception:           # <-- NO logging
      return image_path
  `
- Contrast with image_cache.py:127-128 (cleanup_unused) and 	elegram_poster.py:68-69, which both log on except Exception.

**Recommendation:** Add logger.warning(f"Failed to open image {image_path}: {e}; forwarding original") (or re-raise as a custom error from core/errors.py) in the outer except. At minimum, log the file path and exception type so operators can trace silent fallbacks during a posting run.
Effort: trivial. Priority: recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 4 |
| LOW | 5 |

## Mandatory Fixes

None. No security vulnerabilities, data-loss risks, or correctness-breaking defects were found. Ruff, mypy, and the full test suite (224 tests) pass clean.

## Advisory Recommendations

- **QLT-001** — Replace Any with concrete types across post_processor.py, 	elegram_service.py, config_reader.py, gsheets_reader.py, utils.py.
- **QLT-002** — Introduce a typed Post model instead of list[list[Any]] for the post data flow.
- **QLT-003** — Investigate ImageCache.get_cache_path: unify with esize_image's format-aware logic or remove (it is dead in production and returns divergent paths).
- **QLT-004** — Make _coordinate_posting's success/failure counts explicit (initialize in __init__, return through normal path, or consume the tuple in un()).
- **QLT-006** — Stop storing client_config as a raw dict on TelegramPoster; keep the typed ClientConfig and build kwargs at the Telethon boundary.
- **QLT-007** — Remove 	emp_findings.txt; relocate or remove ix_readme_script.py; update structure docs.
- **QLT-008** — Delete the # type: ignore[arg-type] once QLT-002 lands.
- **QLT-009** — Log the exception in ImageCache.resize_image's outer except Exception block instead of silently returning the original path.

## Doc Updates Needed

- **QLT-005** — GSheetsReader.get_sheet_data docstring claims spreadsheet_id/ange_name are optional; they are required. Either fix the docstring or make the parameters optional. Also remove the dead or fallback branches.
- **QLT-007** — .ai/structure/map.md and docs/STRUCT.md list stray root artifacts; update after cleanup.
