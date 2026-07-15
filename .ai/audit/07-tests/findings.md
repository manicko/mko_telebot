# Phase 07 Audit Findings — Test Quality

**Executor:** audit-executor
**Template:** .kilo/commands/audit/phases/07-audit-tests.md
**Status:** complete
**Validated:** no

> Runtime verification: `uv run pytest -v` → **353 passed in 8.87s** (0 failures, 0 errors). No import/config errors. Suite is deterministic (re-runs stable) and fast. No coverage tool is wired into `addopts` (pytest-cov present but inactive).

---

## Findings

### TST-001: `ChannelConfig.name` path-traversal validator has no regression test

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/channels.py`, `tests/test_config_reader.py` |
| **Classification** | advisory |

**Description:** `ChannelConfig.name` carries a `field_validator` that rejects path-traversal characters (`/`, `\`, `..`) to prevent a malicious/erroneous channel name from escaping the intended config/session/state directory:

```python
# src/mko_telebot/core/channels.py:43-51
@field_validator("name")
@classmethod
def validate_channel_name(cls, v: str) -> str:
    if "/" in v or "\\" in v or ".." in v:
        raise ValueError("Invalid channel name: contains forbidden path character")
    return v
```

The parallel, equivalent guard on `ClientConfig.session` (`telethon.py`) IS tested (`tests/test_config_reader.py:477-502`, `match="path traversal"`). The `ChannelConfig.name` guard is **not** referenced by any test. `ChannelConfig(name=...)` appears only with the safe literal `"@test"` (`test_config_reader.py:524,536,549,563`), so the rejection branch is never exercised.

**Evidence:** `grep -r "Invalid channel name|contains forbidden|ChannelConfig\(name=.*[/\\]" tests/` returns nothing. Channel names feed filesystem path construction (session files, state files via `task.py`/`paths.py`), so a regression here would silently re-enable path traversal in user-supplied config.

**Recommendation:** Add parametrized cases to `tests/test_config_reader.py` (or a dedicated `tests/test_channels.py`) asserting `ChannelConfig(name="a/b")`, `name="a\\b"`, and `name="a..b"` raise `ValueError` with the path-traversal message, and that a benign name such as `"@chan"` is accepted. *Effort: trivial. Priority: recommended.*

---

### TST-002: `extra="forbid"` schema-strictness guardrail is untested across all Pydantic models

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `core/models.py`, `core/channels.py`, `core/telethon.py`, `tests/test_config_reader.py` |
| **Classification** | advisory |

**Description:** Every config model sets `extra="forbid"` (`TelepostSettings` `models.py:22`, `ChannelConfig`/`ChannelDefaults`/`ChannelsConfig` `channels.py:22,60,91`, `ClientConfig`/`ProxyConfig`/`TelethonConfig` `telethon.py`). This is the primary defence against silently accepting typo'd or injected YAML keys. No test asserts that an unknown key is rejected. A `grep` for `extra|forbid|unknown|did not expect` across `tests/` yields only unrelated matches — there is no `pytest.raises` exercising `extra="forbid"` rejection for any model.

**Evidence:** Loading config always uses keys that exactly match the schema. If `extra` were accidentally relaxed to `allow` (or a key is misspelled in a shipped template), the misconfiguration would pass silently with zero test coverage to catch it.

**Recommendation:** Add a focused test asserting that constructing each model with an unexpected top-level/field key raises `ValidationError` (e.g. `TelepostSettings(**{"TELETHON_API": ..., "CHANNELS": ..., "BOGUS": 1})`). *Effort: small. Priority: recommended.*

---

### TST-003: Property-based matcher tests assert only "no crash", not correctness

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `tests/test_parser.py` |
| **Classification** | advisory |

**Description:** `test_property_no_crash_basic` and `test_property_no_crash_generated` (`tests/test_parser.py:565-582`) wrap `search_match` in a `try/except` and assert only `isinstance(result, bool)`. Because the property is "returns a bool and does not raise", the tests **cannot fail on incorrect matching logic** — a `search_match` that always returns `True` or always returns `False` still passes. They give false confidence about matcher correctness. (The companion parametrized `test_search_match` block at `:558-559` is strong and should be the model to extend.)

```python
# tests/test_parser.py:565-571
def test_property_no_crash_basic(matcher, text, query):
    try:
        result = matcher(text, query)
        assert isinstance(result, bool)
    except Exception:
        pytest.fail("Function crashed")
```

**Evidence:** The `except Exception: pytest.fail` form also masks unexpected exceptions as a plain failure rather than letting Hypothesis report the falsifying example, weakening the property test's diagnostic value.

**Recommendation:** Strengthen with a meaningful invariant, e.g. for any `query` containing a non-wildcard literal term `t`, `search_match(t, f'"{t}"') is True`; and `search_match("", query) is False` for non-empty queries. Remove the broad `except` so Hypothesis surfaces the minimal counterexample. *Effort: small. Priority: recommended.*

---

### TST-004: Model/validator tests are colocated in `test_config_reader.py`, violating unit-per-module layout

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `tests/test_config_reader.py`, `tests/test_monitor.py` |
| **Classification** | advisory |

**Description:** Validation logic for `channels.py`, `telethon.py`, and `models.py` (plus `TelepostConfigReader`) is tested inside `tests/test_config_reader.py` (class `TestValidators`, `:413`). Likewise, `monitor_client.py` functions (`build_message_link`, `build_sender_tag`, `create_client`, `start_client`) are tested inside `tests/test_monitor.py` rather than a `tests/test_monitor_client.py`. This contradicts the project's stated architecture rule "Small modules and functions … unit per module" (`AGENTS.md`, `.kilo/rules/project.md`) and the phase's own "map test organization (unit per module)" discovery expectation. Tests for a module are harder to locate, and a reader scanning `tests/` cannot tell that model validation is covered.

**Evidence:** `tests/` contains no `test_models.py`, `test_channels.py`, `test_telethon.py`, or `test_monitor_client.py`; model/validator and client tests live inside unrelated files.

**Recommendation:** Extract `TestValidators` (and model-level `extra="forbid"` cases from TST-002) into `tests/test_models.py` / `tests/test_channels.py` / `tests/test_telethon.py`, and the `monitor_client` tests into `tests/test_monitor_client.py`. *Effort: small. Priority: recommended.*

---

### TST-005: Audit phase spec references non-existent components (stale critical-path table)

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | LOW |
| **Type** | DOC-UPDATE |
| **Affected Modules** | `.kilo/commands/audit/phases/07-audit-tests.md` |
| **Classification** | advisory |

**Description:** The phase's "Critical Path Coverage" table mandates tests for `PostProcessor`, `ImageCache`, `TelegramPoster`, `GSheetsReader`, and an `Init service`. None of these modules exist in the current codebase (`src/mko_telebot/` has `cli, main, monitor, monitor_client, monitor_forward, logging` + `core/{config,matcher,models,parser,channels,errors,task,telethon,utils,paths,ast_nodes}`). The phase spec was written against a different/earlier architecture and misrepresents the actual critical paths, which can mislead future audit passes.

**Evidence:** `Get-ChildItem -Recurse src` shows no `post_processor`, `image_cache`, `telegram_poster`, `gsheets_reader`, or `init` modules; the real forwarding/orchestration logic lives in `monitor_forward.py` / `monitor.py` / `monitor_client.py`, which ARE tested.

**Recommendation:** Update the phase's critical-path table to the actual modules (`monitor_forward.process_task`/`process_messages`/`forward_to_users`, `monitor_client`, `core/models`, `core/channels`, `core/telethon`, `cli` commands). *Effort: trivial. Priority: recommended.*

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 3 |
| LOW | 2 |

## Mandatory Fixes

None (no production bug, data-loss, or security defect found; all 353 tests pass). Findings are test-gap / quality improvements.

## Advisory Recommendations

- **TST-001** — Add regression tests for `ChannelConfig.name` path-traversal validator.
- **TST-002** — Add `extra="forbid"` rejection tests for all Pydantic config models.
- **TST-003** — Strengthen property-based matcher tests beyond "no crash".
- **TST-004** — Split model/client validation tests into per-module test files.
- **TST-005** — Refresh the audit phase's critical-path table to match the real architecture.

## Doc Updates Needed

- **TST-005** — `.kilo/commands/audit/phases/07-audit-tests.md` critical-path table references components not present in the codebase.
