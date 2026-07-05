# Phase 08 Audit Findings â€” Code Quality, Security & Maintainability (VALIDATED)

**Executor:** auditor
**Validator:** validator
**Template:** .kilo/commands/audit/phases/08-audit-quality.md
**Status:** complete
**Validated:** yes
**Validation scope:** QLT-001 â€¦ QLT-009. All evidence re-checked against the implementation. Cross-phase duplicate (QLT-003 â†” SRV-002) and dependency chain (QLT-002 â†’ QLT-008) detected.

## Runtime Verification Summary

- **R1 â€” Ruff:** `uv run ruff check src tests` â†’ `All checks passed!`
- **R1 â€” Mypy:** `uv run mypy src` â†’ `Success: no issues found in 21 source files`
- **R2 â€” Tests:** `uv run pytest tests` â†’ `224 passed in 1.23s`
- **R3 â€” Dead code search:** performed via `grep`/`read` (see QLT-003, QLT-004, QLT-005).
- **R4 â€” Security search:** `print(`, `except:`, `TODO/FIXME`, hardcoded secrets, credential-logging â€” see findings below. No `print()` in production code (all matches are `console.print()` in `app.py` or comments/doctests). No bare `except:`. No `TODO/FIXME`. No hardcoded secrets beyond intentional template placeholders in `settings/app_config.yaml`.

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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified all five modules against the source. `post_processor.py:10` imports `Any`; uses confirmed at lines 116 (`row: list[Any]`), 144 (`row: list[Any]` / `-> Any`), 159 (`return row[txt_col]`), 183 (`gdata: list[list[Any]]`), 188 (`-> list[list[Any]]`), 202 (`posts: list[list[Any]]`). `telegram_service.py:10` imports `Any`; uses confirmed at lines 77, 81, 120, 198, 324, 332, 361 â€” note the auditor's "183" entry is a minor line-number inaccuracy (line 183 is a `)` in `_try_send_message`); the actual `dict[str, Any]` is at line 198. The inaccuracy does not affect the finding. `config_reader.py:13` imports `Any`; `dict[str, Any]` confirmed at lines 67, 132, 161, 177, 200. `gsheets_reader.py:9` imports `Any`; `list[list[Any]]` return at line 219. `utils.py:4` imports `Any`; `dict[str, Any] | None` at line 11. Rule 9 (`AGENTS.md`, `.kilo/rules/project.md`) and `.ai/context/python-code-standards.md` forbid `Any`. Classification SPEC-DEVIATION is correct: the rule is explicit and the code violates it.
> - **See also:** QLT-002 (post-path `Any` is a subset resolved by the `Post` model), QLT-008 (symptom of QLT-002).

**Description:** The project rules (`AGENTS.md`, `.kilo/rules/project.md` rule 9, `.ai/context/python-code-standards.md`) require type safety everywhere and explicitly forbid `Any`. Despite `mypy --strict`-adjacent config passing, multiple production modules annotate with `Any`, defeating static analysis for those code paths. The worst offenders are the post-data containers (`list[list[Any]]`, covered separately in QLT-002) and the YAML/Sheets I/O boundaries.

**Evidence:**

- `src/mko_telepost/core/post_processor.py:10` â€” `from typing import TYPE_CHECKING, Any`; used at lines 116 (`row: list[Any]`), 144 (`row: list[Any]` / `-> Any`), 159 (`return row[txt_col]` typed `Any`), 183 (`gdata: list[list[Any]]`), 188 (`-> list[list[Any]]`), 202 (`posts: list[list[Any]]`).
- `src/mko_telepost/core/telegram_service.py:10` â€” `from typing import Any`; used at lines 77, 81, 120, 198, 324, 332, 361 (auditor listed "183"; actual `Any` use near that region is at line 198).
- `src/mko_telepost/core/config_reader.py:13` â€” `from typing import Any`; `dict[str, Any]` at lines 67, 132, 161, 177, 200.
- `src/mko_telepost/core/gsheets_reader.py:9` â€” `from typing import TYPE_CHECKING, Any`; `list[list[Any]]` return at line 219.
- `src/mko_telepost/core/utils.py:4` â€” `from typing import Any`; `dict[str, Any] | None` at line 11.

`grep -r ": Any\b|-> Any\b|list\[Any\]|dict\[str, Any\]" src` returns 1+ match in 5 modules.

**Recommendation (single approach per category):**

1. **Google Sheets cell values** — Introduce a `CellValue: TypeAlias = str | int | float | bool | None` in a shared types module (e.g. `core/types.py`). Use it in:
   - `GSheetsReader.get_sheet_data` return: `-> list[list[CellValue]]`
   - `PostProcessor._extract_photo_paths` parameter: `row: list[CellValue]`
   - `PostProcessor._extract_text_value` parameter (`row: list[CellValue]`) and return (`-> CellValue | str` — text columns are always strings but the union documents the raw source)
   - `PostProcessor.get_posts` parameter: `gdata: list[list[CellValue]]`
   The Google Sheets API v4 `values().get()` returns cells as exactly these five types. A `CellValue` alias (not `object`) preserves the actual type info for mypy while being DRY across 5+ signatures. All callers already handle str/int/float/bool/None correctly (text extraction, photo path resolution), so this is purely a type-level change — no runtime logic changes needed.

2. **YAML config dicts** — Use `dict[str, object]` at the YAML I/O boundary only:
   - `yaml_to_dict` return: `-> dict[str, object] | None`
   - `TelepostConfigReader._load_yaml` return: `-> dict[str, object]`
   - `TelepostConfigReader._validate_settings` parameter: `config_data: dict[str, object]`
   - `TelepostConfigReader.load_logging_config` return: `-> dict[str, object]`
   - `_resolve_log_paths` / `_default_logging_config`: same
   `object` is preferred over `Any` because it forces explicit casts at consumption points. The main config `dict[str, object]` is immediately validated into Pydantic `TelepostSettings` via `model_validate()` (which accepts `object` values), so `object` correctly signals “this is unvalidated YAML data — validate before use”. Logging config dicts are consumed by `logging.config.dictConfig`, which accepts `object` values. No runtime changes needed.

3. **Post containers** (`list[list[Any]]` → `[txt_value, valid_photos]` pairs) — **Defer entirely to QLT-002.** The `Post` model introduced by QLT-002 will replace all 7 remaining `Any` usages in `telegram_service.py:77,81,324,332,361` and `post_processor.py:202`. Do not touch these signatures here — they will be fully resolved by the `granges_data: dict[str, list[Post]]` change.

4. **Telethon API kwargs** — In `telegram_service.py:120` (`raw_photos: list[Any]`) resolved by QLT-002 (becomes `list[Path]`). In `telegram_service.py:198` (`reply_to_kwargs: dict[str, Any]`), use `dict[str, InputReplyToMessage]` — the only possible value is `InputReplyToMessage` and the dict is conditionally populated in a 3-line scope.

Effort breakdown: cell values — small (alias + 5 signature changes). YAML dicts — small (6 return/parameter type changes). Post containers — zero (covered by QLT-002). Telethon kwargs — trivial (2 line-level changes). Priority: recommended.

---

### QLT-002: Post data flows through untyped `list[list[Any]]` instead of a model

| Field | Value |
|-------|-------|
| **ID** | QLT-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/telegram_service.py` |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified `post_processor.py:218` (`posts.append([txt_value, valid_photos])`), `:188` (`-> list[list[Any]]`), `telegram_service.py:101` (`raw_photos = post[1][: chat.max_photos]`), `:110` (`txt=post[0]`), and the `granges_data: dict[str, list[list[Any]]]` propagation at 77, 81, 324, 332, 361. The positional contract is real and the reordering-hazard is real. Rule 11 (`.kilo/rules/project.md`) requires Pydantic for all data models; `AGENTS.md` forbids raw dicts/lists in business logic. BEST-PRACTICE classification is correct: introducing a small `Post` model is high-ROI modularization, not overengineering. This is the **root cause** of QLT-008 and a subset of QLT-001.
> - **See also:** QLT-001 (broader `Any` usage), QLT-008 (depends on QLT-002 ï¿½ fix QLT-002 first, then delete the `# type: ignore`).

**Description:** A "post" is represented as a positional two-element list `[txt_value, valid_photos]`. The contract (index 0 = text, index 1 = photo list) exists only in the producer/consumer heads and is consumed by positional indexing in `telegram_service.py`. This violates "Pydantic for all data models" (`.kilo/rules/project.md` rule 11) and "no raw dicts/lists in business logic" (`AGENTS.md`). It is the root cause of the `# type: ignore[arg-type]` in `telegram_service.py:105` (QLT-008).

**Evidence:**

- `src/mko_telepost/core/post_processor.py:218` ï¿½ `posts.append([txt_value, valid_photos])` builds the positional pair.
- `src/mko_telepost/core/post_processor.py:188` ï¿½ `-> list[list[Any]]` return signature.
- `src/mko_telepost/core/telegram_service.py:101` ï¿½ `raw_photos = post[1][: chat.max_photos]` (positional index 1).
- `src/mko_telepost/core/telegram_service.py:110` ï¿½ `txt=post[0]` (positional index 0).
- `src/mko_telepost/core/telegram_service.py:77,81,324,332,361` ï¿½ `granges_data: dict[str, list[list[Any]]]` propagated through 4 methods.

A future maintainer reordering the append in `post_processor.py` would silently break `telegram_service.py` with no type error.

**Recommendation:** Introduce a small dataclass or Pydantic model (e.g. `Post(txt: str, photos: list[Path])`) returned by `PostProcessor.get_posts` and stored in `granges_data: dict[str, list[Post]]`. Replace `post[0]`/`post[1]` with `post.txt`/`post.photos`. This removes the `Any` usage in the post path, eliminates the `type: ignore`, and makes the contract explicit.
Effort: small. Priority: recommended.

---

### QLT-003: ~~ImageCache.get_cache_path is dead in production and diverges from resize_image~~ [REJECTED ï¿½ DUPLICATE]

> **Rejection reason:** Strict cross-phase duplicate of **SRV-002** (Phase 03 ï¿½ Services audit), already validated in `.ai/audit/99-validation/03-services-validated-findings.md`. Same method (`ImageCache.get_cache_path`), same source lines (`image_cache.py:39-51` vs `70-79`), same divergence evidence (`original_path.suffix or ".jpg"` vs alpha-channel `out_ext`), same dead-in-production evidence (1 match in `src/` ï¿½ the definition; 7 matches in `tests/test_image_cache.py`), and the same recommendation. SRV-002 was reclassified `BEST-PRACTICE ? SPEC-DEVIATION` after the mandatory dead-code spec cross-reference (`SPEC.md ï¿½4.9` does not list `get_cache_path` as a public API; no Pydantic model or config template references it). Keeping a second copy of the same finding adds no information. Resolved under SRV-002; the rollout note there already covers the required test updates (`test_get_cache_path`, `test_get_cache_path_consistency`).

> **Validation Note:**
> - **Action:** merged
> - **Detail:** Duplicate of SRV-002 (Phase 03). The earlier finding absorbs this one; SRV-002 carries the reclassification to SPEC-DEVIATION and the rollout/test-impact note.
> - **See also:** SRV-002 (Phase 03), `.ai/audit/99-validation/03-services-validated-findings.md`

---

### QLT-004: _coordinate_posting return value is dead; success/failure counts passed via undeclared instance attributes

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telepost/core/telegram_service.py |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified `telegram_service.py:308-310` (`await self._coordinate_posting(client, granges_data, used_cache_files)` ï¿½ return value discarded), `:172-173` (`self._last_success_count`/`self._last_failed_count` set only in `except asyncio.CancelledError`), `:400-401` (`getattr(self, "_last_success_count", 0)` / `getattr(self, "_last_failed_count", 0)`), and `__init__` (lines 51-71 ï¿½ counters never declared). The fragility described is real: if `_send_posts` exits without raising `CancelledError` the counts are never set and the tuple silently returns `(0, 0)`. BEST-PRACTICE is correct: the fix is a small, explicit restructuring (init in `__init__`, return counts through the normal path) ï¿½ not an architecture change.

**Description:** TelegramService._coordinate_posting declares -> tuple[int, int] and constructs that tuple from self._last_success_count / self._last_failed_count ï¿½ instance attributes that are (a) never declared in __init__, (b) only set inside _send_posts's except asyncio.CancelledError branch, and (c) read back with getattr(self, "_last_success_count", 0). The caller run() (line 308) discards the returned tuple entirely. The contract is therefore implicit, fragile, and partially dead: if _send_posts ever exits without raising CancelledError, the attributes are never set and the tuple silently returns (0, 0).

**Evidence:**

- src/mko_telepost/core/telegram_service.py:308-310 ï¿½ `await self._coordinate_posting(client, granges_data, used_cache_files)` ï¿½ return value ignored.
- src/mko_telepost/core/telegram_service.py:172-173 ï¿½ `self._last_success_count = success_count` / `self._last_failed_count = failed_count` (set only in `except asyncio.CancelledError`).
- src/mko_telepost/core/telegram_service.py:400-401 ï¿½ `success_count = getattr(self, "_last_success_count", 0)` / `failed_count = getattr(self, "_last_failed_count", 0)`.
- src/mko_telepost/core/telegram_service.py:51-71 ï¿½ `__init__` does not initialize `_last_success_count` / `_last_failed_count`.

**Recommendation:** Consume the return value in `run()` and initialize counters in `__init__`. This fixes the dead return value, eliminates the fragile `getattr` fallback, and adds operational value via a run summary log. Do NOT restructure the cancellation flow â€” stashing counts in `except CancelledError` and re-raising is the standard asyncio pattern and is not broken.

**Exact changes needed in `src/mko_telepost/core/telegram_service.py`:**

1. **`__init__` (after line 71):** Initialize counters to make state explicit:
   ```python
   self._last_success_count = 0
   self._last_failed_count = 0
   ```

2. **`_coordinate_posting` (lines 399-402):** Replace `getattr` fallback with direct attribute access:
   ```python
   return self._last_success_count, self._last_failed_count
   ```

3. **`run()` (line 308):** Capture the tuple and log a run-level summary:
   ```python
   success_count, failed_count = await self._coordinate_posting(
       client, granges_data, used_cache_files
   )
   logger.info(
       f"Posting complete: {success_count} succeeded, {failed_count} failed"
   )
   ```

Total: ~5 lines changed, all in one file. No restructure of the cancellation flow. The counters are now explicit in `__init__`, the `getattr` wrapper is removed, and the return value is consumed instead of discarded.
Effort: small (5 lines). Priority: recommended.

---

### QLT-005: GSheetsReader.get_sheet_data has dead fallback branches and a misleading docstring ~~DONE — DOC-UPDATE resolved~~

| Field | Value |
|-------|-------|
| **ID** | QLT-005 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | src/mko_telepost/core/gsheets_reader.py |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified `gsheets_reader.py:215-219` (signature `def get_sheet_data(self, spreadsheet_id: str, range_name: str) -> list[list[Any]]:` ï¿½ both required, no defaults), `:224` docstring ("spreadsheet_id: Spreadsheet ID (uses config value if not provided)"), `:225` ("range_name: Range to retrieve ..."), and `:243-244` (`spreadsheet_id = spreadsheet_id or self.config.spreadsheet_id` / `range_name = range_name or "Sheet1!A1:Z100"`). The single production caller (`telegram_service.py:337-340`) passes both args explicitly, so the `or` fallbacks are dead. Dead-code spec cross-reference performed: `SPEC.md ï¿½4.4` (line 155) lists `spreadsheet_id` as `required` and `range_names` come from chat config ï¿½ the spec does not describe any config-fallback behavior for `get_sheet_data`'s positional params. The model (`GoogleSheetsConfig.spreadsheet_id`) is a required constrained field. The docstring is therefore the actual lie; DOC-UPDATE is the correct primary classification. (The dead `or`-branch removal is a minor code cleanup bundled with the doc fix; it does not warrant a separate BEST-PRACTICE finding.)

**Description:** get_sheet_data declares `spreadsheet_id: str` and `range_name: str` as required parameters with no default, yet the body contains fallback reassignments that only trigger on empty strings ï¿½ a path no caller exercises. The docstring claims the parameters are optional, which is false. This is dead code plus a documentation lie that can mislead callers into relying on a fallback that does not meaningfully exist.

**Evidence:**

- src/mko_telepost/core/gsheets_reader.py:215-219 ï¿½ signature: `def get_sheet_data(self, spreadsheet_id: str, range_name: str) -> list[list[Any]]:` (both required).
- src/mko_telepost/core/gsheets_reader.py:224 ï¿½ docstring: "spreadsheet_id: Spreadsheet ID (uses config value if not provided)".
- src/mko_telepost/core/gsheets_reader.py:225 ï¿½ docstring: "range_name: Range to retrieve (e.g., 'Sheet1!A1:Z100')" (implies optional).
- src/mko_telepost/core/gsheets_reader.py:243-244 ï¿½ `spreadsheet_id = spreadsheet_id or self.config.spreadsheet_id` / `range_name = range_name or "Sheet1!A1:Z100"` ï¿½ only triggers on `""`/`None`; all callers (`telegram_service.py:337-340`) pass real values.
- grep -rn "get_sheet_data(" src ? only caller passes both args explicitly.

**Recommendation:** Remove the dead `or` fallbacks (lines 243-244) and correct the docstring to state both parameters are required. If config-fallback behavior is actually desired, make the parameters `str | None = None` and keep the branches.
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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified `telegram_poster.py:34` (`self.client_config = settings.client.model_dump()`), `:35-36` (`if "api_hash" in self.client_config:` then manual `get_secret_value()` extraction because `model_dump()` returns the `SecretStr`), `:42-43,55` (`config = self.client_config.copy(); config["session"]` keyed access and mutation), `:57` (`return TelegramClient(**config)`). The recommendation keeps the typed `TelethonConfig`/`ClientConfig` reference and builds the kwargs dict only at the Telethon boundary ï¿½ aligns with rule 11 (`AGENTS.md`, `.kilo/rules/project.md`) and adds no new abstraction. SPEC-DEVIATION is correct: the stored-instance-state form violates the explicit "no raw dicts in business logic" rule.

**Description:** TelegramPoster.__init__ calls `settings.client.model_dump()` and stores the resulting `dict[str, Any]` on `self.client_config`. create_client then accesses `config["session"]` by string key and mutates it. This violates "Pydantic for all data models ï¿½ not raw dicts in business logic" (AGENTS.md, rule 11). The `if "api_hash" in self.client_config:` guard at line 35 is a symptom of untyped dict access: with a typed model the field's existence is guaranteed by the schema. A typo in any key (e.g. `config["sesion"]`) would fail at runtime, not at type-check time.

**Evidence:**

- src/mko_telepost/core/telegram_poster.py:34 ï¿½ `self.client_config = settings.client.model_dump()`.
- src/mko_telepost/core/telegram_poster.py:35-36 ï¿½ `if "api_hash" in self.client_config:` then `self.client_config["api_hash"] = settings.client.api_hash.get_secret_value()` (manual secret extraction because `model_dump()` returns the `SecretStr` object).
- src/mko_telepost/core/telegram_poster.py:42-43,55 ï¿½ `config = self.client_config.copy(); config["session"]` keyed access; `config["session"] = str(session_path)`.
- src/mko_telepost/core/telegram_poster.py:57 ï¿½ `return TelegramClient(**config)` (the dict exists only to splat into Telethon kwargs).

**Recommendation:** Keep a `TelethonConfig`/`ClientConfig` reference on the instance instead of a dict, and build the kwargs dict at call time in `create_client` from the typed fields (resolving session, extracting `api_hash.get_secret_value()` there). This removes the `in` guard, the manual mutation, and the string-key fragility. The dict is only needed at the Telethon boundary, not as stored instance state.
Effort: small. Priority: recommended.

---

### QLT-007: Stray maintenance artifacts tracked in git at repo root

| Field | Value |
|-------|-------|
| **ID** | QLT-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | repo root (`fix_readme_script.py`, `temp_findings.txt`) |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified via `git ls-files`: both `fix_readme_script.py` (10 818 bytes) and `temp_findings.txt` are tracked. `temp_findings.txt` content confirmed as the literal string `test` (a leftover temp file). `.ai/structure/map.md:7,10` and `docs/STRUCT.md:7,10` list both files ï¿½ the structure docs have indeed codified clutter. `fix_readme_script.py` is a one-off README regeneration script with no `tests/` reference and no `pyproject.toml` entry. BEST-PRACTICE is correct: cleanup is trivial and improves repo-root scannability. No spec/model/config references either file.

**Description:** Two non-source artifacts sit at the repository root and are tracked by git. `fix_readme_script.py` is a 10.8 KB one-off script that embeds the entire README content as a string literal to regenerate README.md; it is not part of the package, not tested, and not referenced by any tooling. `temp_findings.txt` is a 4-byte file containing the literal string `test` ï¿½ a leftover temp file. Both are listed in `.ai/structure/map.md` and `docs/STRUCT.md`, which means the structure docs have codified clutter rather than flagging it for removal. This bloats the repo root and makes the project structure harder to scan.

**Evidence:**

- `git ls-files fix_readme_script.py temp_findings.txt` ? both tracked.
- `temp_findings.txt` content: `test` (4 bytes).
- `fix_readme_script.py` lines 1-40: a Python script whose body is a triple-quoted README string plus regeneration logic; no `tests/` reference, no `pyproject.toml` entry.
- `.ai/structure/map.md:7,10` and `docs/STRUCT.md:7,10` list both files as part of the structure.

**Recommendation:** Remove both files. `fix_readme_script.py` is a one-off snapshot that embeds the entire README as a hardcoded string — it is not referenced in CI (`.github/workflows/ci.yml`), `pyproject.toml`, or any documentation as a maintained workflow. Creating a `scripts/` directory for a single file with frozen content contradicts the project's `avoid overengineering` rule; the README is maintained directly as `README.md`. Delete `fix_readme_script.py` and `temp_findings.txt`. Remove both entries from `.ai/structure/map.md` (lines 7, 10) and `docs/STRUCT.md` (lines 7, 10).
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

> **Validation Note:**
> - **Action:** validated (unchanged) - with sequencing dependency
> - **Detail:** Re-verified `telegram_service.py:105` (`resized_photos = self._resolve_photo_paths(raw_photos, max_w, max_h)  # type: ignore[arg-type]`), `:101` (`raw_photos = post[1][: chat.max_photos]` where `post` is `list[Any]`), and `pyproject.toml` `warn_unused_ignores = true`. The suppression is a direct symptom of QLT-002. BEST-PRACTICE is correct. **Sequencing:** QLT-002 must land first; once posts are typed, this `# type: ignore` becomes unused and mypy will itself flag it (because `warn_unused_ignores = true`). Do not delete it in isolation - that would just re-expose the untyped-`Any` error. Keep separate from QLT-002 (distinct actionable item) but treat as a dependency.
> - **See also:** QLT-002 (root cause - fix first).

**Description:** A `# type: ignore[arg-type]` suppression is the only thing keeping mypy quiet when slicing photo data out of a post. It is a direct symptom of QLT-002 (posts typed as `list[list[Any]]`). pyproject.toml sets `warn_unused_ignores = true`, so the ignore is currently "used" - but only because the post type is `Any`. Once posts are typed (QLT-002), this ignore becomes unused and mypy will itself flag it as dead. Leaving the ignore in place documents that the surrounding code is not actually type-checked.

**Evidence:**

- src/mko_telepost/core/telegram_service.py:105 - `resized_photos = self._resolve_photo_paths(raw_photos, max_w, max_h)  # type: ignore[arg-type]`.
- src/mko_telepost/core/telegram_service.py:101 - `raw_photos = post[1][: chat.max_photos]` where `post` is `list[Any]` (from `granges_data: dict[str, list[list[Any]]]`).
- pyproject.toml:140 - `warn_unused_ignores = true`.

**Recommendation:** Resolve QLT-002 first (type posts as a model), then delete this `# type: ignore`. Do not leave suppression comments as a substitute for types.
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

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **Detail:** Re-verified `image_cache.py:74-101`: the outer `try` (around `Image.open(image_path)`) has `except Exception:` at line 100-101 returning `image_path` with **no logging**, while the inner save block (lines 88-99) logs `logger.error(...)` at line 93 on its `except Exception as e`. The inconsistency is real. `AGENTS.md` ("Never silently swallow errors") and `core/errors.py`'s intent are violated. SPEC-DEVIATION is correct: the project rule is explicit. The recommendation (add `logger.warning` with file path + exception, or re-raise as a custom error) is minimal and aligns with the established logging pattern in the same file (`cleanup_unused`, line 128) and in `telegram_poster.py:69`.

**Description:** The outer `try/except` around `Image.open(image_path)` catches `Exception` and returns the original `image_path` with **no logging whatsoever**. This violates AGENTS.md ("Never silently swallow errors") and `core/errors.py`'s intent. When a photo fails to open (corrupt file, permission denied, unsupported format, truncated download), the service silently posts the original (potentially oversized/invalid) file, and operators have no log line to diagnose why uploads are misbehaving. The inner save block (line 92) logs correctly; the outer open block does not, which is inconsistent.

**Evidence:**

- src/mko_telepost/core/image_cache.py:74-101:
  ```python
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
  ```
- Contrast with `image_cache.py:127-128` (`cleanup_unused`) and `telegram_poster.py:68-69`, which both log on `except Exception`.

**Recommendation:** Add `logger.warning(f"Failed to open image {image_path}: {e}; forwarding original")` (or re-raise as a custom error from `core/errors.py`) in the outer `except`. At minimum, log the file path and exception type so operators can trace silent fallbacks during a posting run.
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

- **QLT-001** - Replace `Any` with concrete types across `post_processor.py`, `telegram_service.py`, `config_reader.py`, `gsheets_reader.py`, `utils.py`.
- **QLT-002** - Introduce a typed `Post` model instead of `list[list[Any]]` for the post data flow. **Fix before QLT-008.**
- **QLT-003** - Resolved as duplicate of SRV-002 (Phase 03). See `.ai/audit/99-validation/03-services-validated-findings.md`.
- **QLT-004** - Consume the return value in `run()` and log a run-level summary; initialize `_last_success_count`/`_last_failed_count` in `__init__` to eliminate the `getattr` fallback. All changes in `telegram_service.py` (~5 lines).
- **QLT-006** - Stop storing `client_config` as a raw dict on `TelegramPoster`; keep the typed `ClientConfig` and build kwargs at the Telethon boundary.
- **QLT-007** - Remove `temp_findings.txt` and `fix_readme_script.py` from repo root; update `.ai/structure/map.md` and `docs/STRUCT.md`.
- **QLT-008** - Delete the `# type: ignore[arg-type]` once QLT-002 lands (sequenced dependency).
- **QLT-009** - Log the exception in `ImageCache.resize_image`'s outer `except Exception` block instead of silently returning the original path.

## Doc Updates Needed

- **QLT-005** - `GSheetsReader.get_sheet_data` docstring claims `spreadsheet_id`/`range_name` are optional; they are required. Either fix the docstring or make the parameters optional. Also remove the dead `or` fallback branches.
- **QLT-007** - `.ai/structure/map.md` and `docs/STRUCT.md` list stray root artifacts; update after cleanup.

## Rollout Safety Analysis

- **No circular dependencies detected.**
- **Dependency chain - QLT-002 -> QLT-008:** QLT-008 is a symptom of QLT-002. Sequence: implement the `Post` model (QLT-002) first; then remove the `# type: ignore` (QLT-008). Because `pyproject.toml` sets `warn_unused_ignores = true`, mypy will flag QLT-008 as a dead suppression automatically once QLT-002 lands - a built-in safety net. Reversing the order (deleting the ignore before typing posts) merely re-exposes the untyped-`Any` mypy error.
- **Subset relationship - QLT-002 subset of QLT-001:** The `Post` model resolves the post-path portion of QLT-001. The remaining `Any` usages in `config_reader.py`, `utils.py`, and `gsheets_reader.py` I/O boundaries are independent and can be tackled separately.
- **QLT-003 / SRV-002 test impact:** If `get_cache_path` is removed (per SRV-002), `tests/test_image_cache.py::test_get_cache_path` and `::test_get_cache_path_consistency` must be removed in the same change; no production callers exist. Low risk.
- **No fragile insertion points:** all recommendations target named methods/classes (`PostProcessor.get_posts`, `TelegramService._coordinate_posting`, `TelegramPoster.create_client`, `ImageCache.resize_image`, `GSheetsReader.get_sheet_data`), not line numbers.

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 8 | QLT-001, QLT-002, QLT-004, QLT-005, QLT-006, QLT-007, QLT-008, QLT-009 (QLT-008 carries a sequencing dependency on QLT-002) |
| Reclassified | 0 | - |
| Merged | 1 | QLT-003 -> SRV-002 (Phase 03) |
| Rejected | 1 | QLT-003 (duplicate of SRV-002) |

> 9 source findings; 8 retained in Phase 08 after QLT-003 is folded into SRV-002. QLT-003 is both merged and rejected-as-duplicate (single outcome).

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| QLT-003 | ImageCache.get_cache_path is dead in production and diverges from resize_image | Strict cross-phase duplicate of SRV-002 (Phase 03), already validated and reclassified to SPEC-DEVIATION. Same method, same lines, same evidence, same recommendation. Resolved under SRV-002. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| QLT-003 | SRV-002 (Phase 03) | Identical finding: same `ImageCache.get_cache_path` (image_cache.py:39-51 vs 70-79), same divergence, same dead-code evidence (1 prod match / 7 test matches). SRV-002 carries the reclassification and rollout/test-impact note. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| - | - | - | No reclassifications within Phase 08. (QLT-003's target SRV-002 was reclassified in Phase 03 validation, not here.) |

### Cross-Phase Notes

- **QLT-003 <-> SRV-002 (Phase 03):** duplicate. SRV-002 is authoritative.
- **No cross-phase conflicts detected.** Phase 03 services audit and Phase 08 quality audit agree on `get_cache_path` (dead, divergent) and on `resize_image`'s silent error-swallowing (QLT-009 / SRV-002's logging note). No contradictory evidence between phases.
