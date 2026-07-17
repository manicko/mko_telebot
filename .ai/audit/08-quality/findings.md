---
name: audit-findings
description: Phase 08 — Code Quality, Security & Maintainability findings
agent: auditor
alwaysApply: false
---

# Phase 08 Audit Findings — Code Quality, Security & Maintainability

**Executor:** auditor
**Template:** .kilo\commands\audit\phases\08-audit-quality.md
**Status:** complete
**Validated:** no

**Runtime Verification Performed:**
- `uv run ruff check .` → All checks passed (0 issues).
- `uv run ruff format --check .` → 29 files would be reformatted (FAIL).
- `uv run mypy .` → 76 errors, all in `tests/` (src clean).
- `uv run basedpyright .` → 77 errors, 0 warnings, all in `tests/`.
- `uv run pytest .` → 1 failed, 372 passed (test_property_no_crash_generated).
- Dead-code / security / convention searches executed (see evidence per finding).

---

## Findings

### QLT-001: Failing property test encodes an incorrect invariant (exclusion-only ⇒ matches everything)

| Field | Value |
|-------|-------|
| **ID** | QLT-001 |
| **Severity** | HIGH |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | tests/test_parser.py |
| **Classification** | mandatory |

**Description:** `tests/test_parser.py::test_property_no_crash_generated` (lines 592-629) asserts that any query whose stripped content starts with `-` matches arbitrary text: `if query_content.startswith("-"): assert matcher("xyz", query) is True`. This is incorrect. An exclusion-only query (`-X*`, `-car`, etc.) still filters: the matcher returns `False` whenever the exclusion pattern matches the text (see `core/matcher.py::evaluate_query`, lines 124-139 — exclusions are checked first and force `False`). The test conflates "no positive inclusion" with "matches everything", which is false.

**Evidence:** `uv run pytest .` output:
```
FAILED tests/test_parser.py::test_property_no_crash_generated - assert False is True
+  where False = search_match('xyz', '"-X*"')
Falsifying example: text='', query='"-X*"'
```
Reproduction confirms production behavior is correct per the documented semantics (exclusion filters matching text): `matcher("xyz", '"-X*"') -> True` only because "xyz" starts with `X`; for text that matches the exclusion the result is `False`, exactly as the production docstring (matcher.py:156-161) specifies. The test invariant is wrong, not the code. Per project rule "production code is king", this is a defective test.

**Recommendation:** Fix or remove the faulty invariant block (lines 626-629). If the intent is to assert "exclusion pattern does not accidentally exclude unrelated text", assert against text guaranteed not to match the exclusion (e.g. text containing none of the excluded tokens), not arbitrary generated text. This is mandatory because a failing test blocks CI and the broken invariant gives false confidence in matcher correctness.

---

### QLT-002: `ruff format --check` fails on 29 source/test files

| Field | Value |
|-------|-------|
| **ID** | QLT-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py and 28 others (cli.py, core/*.py, logging.py, main.py, monitor*.py, tests/*.py) |
| **Classification** | mandatory |

**Description:** The documented verify command `uv run ruff format --check <path>` is part of the project's required quality gate, but 29 files are not formatted to ruff's standard. `core/task.py` is the worst offender: a 90-line pure-whitespace gap (double blank lines after every import and many stray blank lines). `core/matcher.py` is missing its trailing newline. None of these are caught by `ruff check` (lint), only by ruff format.

**Evidence:** `uv run ruff format --check .`:
```
Would reformat: src\mko_telebot\core\task.py
Would reformat: src\mko_telebot\core\matcher.py
... (29 files total) ...
29 files would be reformatted, 3 files already formatted
```
`uv run ruff format --diff src/mko_telebot/core/task.py` shows ~90 lines of import/blank-line normalization only.

**Recommendation:** Run `uv run ruff format .` once to normalize all files, and ensure the formatter gate is enforced in CI/pre-commit (currently the pre-commit config uses `black`, see QLT-003 — pick ONE formatter). Mandatory because the project's own verify command fails today, signalling the format gate is not actually enforced.

---

### QLT-003: Two competing formatters configured (black/isort vs ruff format)

| Field | Value |
|-------|-------|
| **ID** | QLT-003 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | .pre-commit-config.yaml, pyproject.toml, AGENTS.md |
| **Classification** | mandatory |

**Description:** The repository configures two mutually inconsistent formatting stacks. `.pre-commit-config.yaml` (lines 15-25) installs `mirrors-isort` (isort v5.10.1) and `black` (rev 25.9.0) as the format/lint gate. Meanwhile AGENTS.md, the audit commands, and `pyproject.toml` `[tool.ruff.format]` mandate `ruff format` + `ruff-check` as the standard. Black and ruff-format do NOT produce identical output for many constructs despite both defaulting to line-length 88, so the two gates will fight each other and any file passing one may fail the other. Neither is currently satisfied (QLT-002 shows ruff format fails on 29 files; black is not even a project dependency, only pulled by pre-commit).

**Evidence:** `.pre-commit-config.yaml` lines 15-32 (isort + black hooks) vs `pyproject.toml` `[tool.ruff.lint]` + `[tool.ruff.format]` (indent-style = "space") and AGENTS.md verify commands `uv run ruff format --check <path>` / `uv run ruff check <path>`. `uv run ruff format --diff src/mko_telebot/core/task.py` already diverges from black's expected layout (double blank lines after imports).

**Recommendation:** Choose ONE formatter. Recommended: drop the `black`/`isort` pre-commit hooks and standardize on `ruff format` + `ruff-check` (already the documented command set and already configured in pyproject). Remove isort/black from `.pre-commit-config.yaml` and replace with the ruff-format hook. Mandatory because the conflicting config guarantees the format gate can never be reliably green and causes churn on every commit.

---

### QLT-004: Test suite is not type-clean (mypy 76 + basedpyright 77 errors)

| Field | Value |
|-------|-------|
| **ID** | QLT-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | tests/test_config_reader.py, tests/test_monitor.py, tests/test_parser.py |
| **Classification** | advisory |

**Description:** The project's verify commands `uv run mypy <path>` and `uv run basedpyright <path>` are documented as required gates, but the full type check fails entirely due to test files. All 76 mypy and 77 basedpyright errors are in `tests/`. The dominant pattern is tests bypassing the typed models: they pass raw `str` where `SecretStr` is required (`api_hash`, `phone_or_token`), raw `str`/`dict` where `ProxyConfig`/`ProxyType` enums are required, and construct models with `unknown_key=` kwargs that the models forbid (`extra="forbid"`). `test_monitor.py` passes `Queue[MagicMock]` to functions typed `Queue[Task]` (invariant generic mismatch). `test_parser.py` passes `list[ExactMatch]` to a `list[ASTNode]` parameter and accesses `.value` on a base `ASTNode`.

**Evidence:** `uv run mypy .` → "Found 76 errors in 3 files (checked 30 source files)" — only tests/test_config_reader.py, tests/test_monitor.py, tests/test_parser.py. `uv run basedpyright .` → "77 errors, 0 warnings". Sample: `tests/test_config_reader.py:658: error: Argument "phone_or_token" to "TelethonConfig" has incompatible type "str"; expected "SecretStr"`.

**Recommendation:** Make the test suite type-clean so the documented type-check gate is meaningful: construct test fixtures through the real typed models (wrap secrets in `SecretStr`, build `ProxyConfig`/`ProxyType` instead of raw dicts), and type mock queues as `Queue[Task]` (or use `cast`). Advisory because src is clean and functionality passes; but the type gate is currently non-functional as a safety net for tests.

---

### QLT-005: `search_match` swallows all exceptions and silently returns False

| Field | Value |
|-------|-------|
| **ID** | QLT-005 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/matcher.py (lines 172-183) |
| **Classification** | advisory |

**Description:** `search_match` wraps the entire parse+evaluate path in `except Exception as e:` and returns `False` on any error, only logging via `logger.exception`. A malformed query (e.g. unbalanced parentheses, unsupported syntax, or a transient runtime error) is therefore indistinguishable from a legitimate non-match. Operators debugging "why did my keyword filter match nothing" get a silent `False` and only a stack trace buried in logs.

**Evidence:** `core/matcher.py` lines 172-183:
```python
try:
    inclusions, exclusions = parse_query(query)
    return evaluate_query(text, inclusions, exclusions)
except Exception as e:
    logger.exception(f"Error while evaluating search_match for query '{query}': {e}")
    return False
```

**Recommendation:** Narrow the catch to the specific parse/validation errors (`ValueError` from `parse_query`, regex `re.error`) and let unexpected errors propagate or be surfaced as a distinct result. At minimum, fail loud for configuration-time queries (the keyword filters are static config, so a malformed filter is a config error that should abort startup, not silently never match). Advisory — no crash today, but it masks real misconfiguration.

---

### QLT-006: `Any` used at polymorphic boundaries without concrete typing

| Field | Value |
|-------|-------|
| **ID** | QLT-006 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor_forward.py, src/mko_telebot/core/config.py, src/mko_telebot/core/channels.py |
| **Classification** | advisory |

**Description:** Several modules use `Any` for heterogeneous data: `monitor_forward.py` uses `list[Any]` for `msg_media` (Telegram media objects, lines 84/97/139), and `config.py`/`channels.py` use `dict[str, Any]` for parsed YAML with `# pyright: ignore[reportExplicitAny]` suppressions. The project rule mandates avoiding `Any`. These are boundary cases, so they are tolerated, but the `list[Any]` for media loses all type safety on the forwarding path.

**Evidence:** `monitor_forward.py:84` `msg_media: list[Any] | None`; `core/config.py:50` `_load_yaml(path) -> dict[str, Any]`; `core/channels.py:151` `dict[str, Any]` with pyright ignore.

**Recommendation:** For Telegram media, prefer `list[MessageMedia]` (or a narrow `Union` of the media types actually handled) over `list[Any]` so the forwarder's branching is type-checked. For YAML parsing, `dict[str, Any]` at the boundary is acceptable but should be narrowed to typed models at the earliest point (it already is, via `TelepostSettings`); keep the pyright ignores localized. Low priority — functionally correct, only a maintainability/type-safety gap.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 2 |
| LOW | 1 |

## Mandatory Fixes

- **QLT-001** — Fix/remove defective test invariant in `test_property_no_crash_generated` (failing test blocks CI).
- **QLT-002** — Run `ruff format .` to satisfy the documented `ruff format --check` gate (29 files).
- **QLT-003** — Resolve the black/isort vs ruff-format conflict (standardize on one formatter in pre-commit + pyproject).

## Advisory Recommendations

- **QLT-004** — Make the test suite type-clean so mypy/basedpyright gates are meaningful.
- **QLT-005** — Narrow exception handling in `search_match`; surface malformed-filter config errors instead of silent `False`.
- **QLT-006** — Replace `list[Any]` media typing with concrete Telegram media types.

## Doc Updates Needed

- **QLT-003** — AGENTS.md / audit command list already mandate `ruff format`; `.pre-commit-config.yaml` must be updated to match (remove black/isort) or the docs must be updated to name black as authoritative. The two must agree.
