---
name: 08-quality-validated-findings
description: Validated audit findings — Code Quality, Security & Maintainability
agent: validator
alwaysApply: false
---

# Phase 08 Validated Findings — Code Quality, Security & Maintainability

**Validator:** validator  
**Source:** `.ai/audit/08-quality/findings.md`  
**Status:** validated

---

## Runtime Verification Log

- **R1 — Ruff lint:** `uv run ruff check .` → All checks passed (0 issues). Source confirmed clean.
- **R2 — Ruff format:** `uv run ruff format --check .` → 29 files would be reformatted. Confirmed.
- **R3 — Type check (mypy):** `uv run mypy .` → 76 errors, all in `tests/` (src clean). Confirmed.
- **R4 — Type check (basedpyright):** `uv run basedpyright .` → 77 errors, all in `tests/`. Confirmed.
- **R5 — Test execution:** `uv run pytest tests/test_parser.py::test_property_no_crash_generated` → FAILED with falsifying example `text=''`, `query='"-X*"'` → `search_match('xyz', '"-X*"') → False`. Confirmed.
- **R6 — Exclusion-only behavior:** Verified `search_match('xyz', '-X*')` returns `False` (correct - 'xyz' starts with x which matches X* case-insensitively). The test invariant is incorrect.

---

## Findings Validation

### QLT-001: Failing property test encodes an incorrect invariant (exclusion-only ⇒ matches everything)

| Field | Value |
|-------|-------|
| **ID** | QLT-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | tests/test_parser.py |
| **Classification** | mandatory |

**Evidence Verified:**
- `tests/test_parser.py:626-629` — The invariant `if query_content.startswith("-"): assert matcher("xyz", query) is True` is incorrect.
- `core/matcher.py:124-139` — Exclusions are checked first and force `False` when the exclusion pattern matches.
- `core/matcher.py:106` — Regex uses `re.IGNORECASE`, so `X*` matches words starting with 'x' or 'X'.
- Runtime confirmed: `search_match('xyz', '-X*')` returns `False` (xyz starts with x, matches X* case-insensitively, exclusion triggers).
- `core/matcher.py:156-161` — Docstring correctly describes exclusion semantics.

> **Validation Note:**
> - **Action:** Validated (SPEC-DEVIATION)
> - **Detail:** QLT-001 correctly identifies a test defect. The test assumes "exclusion-only = matches everything" but production semantics are "exclusion-only = matches everything EXCEPT text matching the exclusion pattern". Per project rule "production code is king", the test is defective, not the code.
> - **See also:** DF-004 (Phase 06) describes identical root cause: incorrect test invariant for exclusion-only queries.

**Recommendation:** Fix or remove the faulty invariant block (lines 626-629). The test should use text guaranteed not to match the exclusion pattern (e.g., `abc` for `-X*`), not arbitrary text. This is mandatory because a failing test blocks CI.

---

### QLT-002: `ruff format --check` fails on 29 source/test files

| Field | Value |
|-------|-------|
| **ID** | QLT-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py and 28 others |
| **Classification** | mandatory |

**Evidence Verified:**
- `uv run ruff format --check .` reports 29 files needing reformatting.
- `core/task.py` has double blank lines after imports (lines 14-18, 32-36, etc.) and trailing blank lines.
- `pyproject.toml:73-74` enables `ruff` as formatter with `line-length = 88`.
- `AGENTS.md` and audit commands mandate `uv run ruff format --check <path>` as the verification command.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** The documented verify command contradicts the actual state of the codebase. Running `ruff format` once would resolve this, but the pre-commit hooks (QLT-003) currently use black instead of ruff format.

**Recommendation:** Run `ruff format .` to normalize all files. Ensure the formatter gate is enforced in pre-commit by standardizing on ruff format (see QLT-003).

---

### QLT-003: Two competing formatters configured (black/isort vs ruff format)

| Field | Value |
|-------|-------|
| **ID** | QLT-003 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | .pre-commit-config.yaml, pyproject.toml |
| **Classification** | mandatory |

**Evidence Verified:**
- `.pre-commit-config.yaml:15-25` — Configures `mirrors-isort` and `black` hooks.
- `pyproject.toml:99-124` — Configures `ruff.lint` and `ruff.format` sections.
- `AGENTS.md` documents `uv run ruff format --check <path>` as the verification command.
- Neither formatter is currently satisfied (black is not a project dependency, ruff format fails on 29 files).

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** The findings are correct. The repository has mutually inconsistent formatting configuration. Black and ruff-format produce different output for certain constructs, guaranteeing that the format gate can never be reliably green.

**Recommendation:** Standardize on `ruff format + ruff-check` (already documented in AGENTS.md). Remove isort/black hooks from `.pre-commit-config.yaml` and add ruff-format hook.

---

### QLT-004: Test suite is not type-clean (mypy 76 + basedpyright 77 errors)

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | tests/test_config_reader.py, tests/test_monitor.py, tests/test_parser.py |
| **Classification** | advisory |

**Evidence Verified:**
- `uv run mypy .` → 76 errors, all in `tests/`.
- All 3 test files pass raw `str` where `SecretStr` is required (`api_hash`, `phone_or_token`).
- Tests pass `dict[str, object]` where `ProxyConfig`/`ProxyType` enum types are required.
- Tests pass `Queue[MagicMock]` to functions typed `Queue[Task]` (invariant generic mismatch).
- Tests pass `list[ExactMatch]` to `list[ASTNode]` parameter and access `.value` on base `ASTNode`.
- Source code has 0 type errors.

> **Validation Note:**
> - **Action:** Validated
> - **Detail:** The findings correctly identify type-unsafety in tests. The test code bypasses typed models by using raw `dict` literals and raw `str` values instead of `SecretStr`. The `Queue[MagicMock]` vs `Queue[Task]` mismatch is a type-system issue with invariant generics in Python.

**Recommendation:** Construct test fixtures through the real typed models (wrap secrets in `SecretStr`, use `ProxyConfig`/`ProxyType` enums). For `Queue[Task]` parameters, use `cast(Queue[Task], queue)` or type mock queues as `Queue[Task]`. Advisory because source is clean.

---

### QLT-005: `search_match` swallows all exceptions and silently returns False

| Field | Value |
|-------|-------|
| **ID** | QLT-005 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/matcher.py (lines 172-183) |
| **Classification** | advisory |

**Evidence Verified:**
- `core/matcher.py:172-183` — The `except Exception as e:` catch-all with `return False` is present.
- `core/parser.py:199-218` — `parse_query` raises `ValueError` for empty queries, but other parsing errors may raise other exception types.
- The pattern is intentional for runtime safety: malformed filters return no match rather than crashing.

> **Validation Note:**
> - **Action:** Validated (BEST-PRACTICE)
> - **Detail:** Finding is correct. The broad exception catch is a design gap. However, the recommendation to narrow the catch is appropriate for an advisory finding. The current behavior is intentional for defensive operation, but configuration-time validation could be improved.

**Recommendation:** Replace the broad `except Exception` catch in `search_match` (matcher.py:172-183) with `except (ValueError, re.error) as e:`. Keep defensive `return False` but change `logger.exception` to `logger.warning("Filter evaluation failed for query %r: %s", query, e)` to log without the full traceback overhead. This narrows the exception scope to expected error types while preserving runtime safety; broader exceptions should propagate (not be swallowed).

---

### QLT-006: `Any` used at polymorphic boundaries without concrete typing

| Field | Value |
|-------|-------|
| **ID** | QLT-006 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor_forward.py, src/mko_telebot/core/config.py, src/mko_telebot/core/channels.py |
| **Classification** | advisory |

**Evidence Verified:**
- `monitor_forward.py:84` — `msg_media: list[Any] | None` for Telegram media objects.
- `core/config.py:50` — `_load_yaml(path) -> dict[str, Any]` with `# pyright: ignore[reportExplicitAny]`.
- `core/channels.py:151-171` — Uses `dict[str, Any]` for YAML merge with pyright ignore comments.
- Project rule (from AGENTS.md) states: "The project rule mandates avoiding `Any`."

> **Validation Note:**
> - **Action:** Validated (BEST-PRACTICE)
> - **Detail:** Finding is correct. The `dict[str, Any]` for YAML parsing is a necessary boundary type (heterogeneous YAML → typed models). The `list[Any]` for media is less defensible but reflects Telethon's heterogeneous media types. Both use `# pyright: ignore` to suppress warnings.

**Recommendation:** Keep `dict[str, Any]` at the raw YAML parse boundary — this is the standard Pydantic/PyYAML interop type and is validated to `TelepostSettings` immediately (lines 171-179 in config.py). For the media list in `monitor_forward.py` (lines 84, 97, 139), keep `list[Any]` but add an explicit `# pyright: ignore[reportExplicitAny]` with a comment documenting it as a Telethon `FileLike` boundary: Telethon's `FileLike` union contains 63 variants (Photo, Document, InputPhoto, InputDocument, etc.) and `send_file` accepts `Sequence[FileLike]`. Creating a narrow union would be overengineering; the current `list[Any]` is the pragmatic boundary type. In `channels.py` (lines 151-171), the `dict[str, Any]` is used internally for Pydantic model merging and is acceptable.

**Action:** Add `# pyright: ignore[reportExplicitAny]` on line 84 (and 97, 139) with comment: `# Telethon FileLike boundary: 63-type union, keep Any to avoid overengineering`.

---

## Cross-Phase Analysis

- **QLT-001** overlaps with **DF-004** (Phase 06) — same root cause: incorrect test invariant for exclusion-only queries. QLT-001 is the quality-phase version; DF-004 is the data-flow phase version; TST-001 is the tests-phase version. All describe the same defective test at tests/test_parser.py:626-629.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 6 | QLT-001 through QLT-006 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None — all findings were validated as correct.

### Merged Findings

No merged findings. QLT-001 duplicates DF-004 but both remain valid in their respective contexts.

### Reclassified Findings

None — all findings correctly classified.

---

## Rollout Analysis

### Dependencies

- QLT-002 and QLT-003 are coupled: formatting cannot be fixed until the formatter conflict is resolved.
- QLT-004 fixes are independent but should follow QLT-002/003 to ensure consistent formatting.

### Sequencing Concerns

1. Resolve formatter conflict (QLT-003): update `.pre-commit-config.yaml` to use ruff format hooks.
2. Run `ruff format .` to satisfy format gate (QLT-002).
3. Fix failing test (QLT-001): modify `tests/test_parser.py:626-629`.
4. Type-clean test suite (QLT-004): optional improvement.

### Architectural Risks

- None significant. Changes are cosmetic (format) or test-focused.