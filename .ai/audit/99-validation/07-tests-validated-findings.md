# Phase 07 Validated Audit Findings — Test Quality

**Executor:** audit-executor
**Validator:** validator
**Status:** validated
**Validated:** yes

> Runtime verification: `uv run pytest -v` → **353 passed in 8.87s** (0 failures, 0 errors). Suite is deterministic and fast.

---

## Findings

### TST-001: ~~`ChannelConfig.name` path-traversal validator has no regression test~~ [VALIDATED]

| Field | Value |
|-------|-------|
| **ID** | TST-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/channels.py`, `tests/test_config_reader.py` |
| **Classification** | advisory |

**Description:** `ChannelConfig.name` carries a `field_validator` that rejects path-traversal characters (`/`, `\`, `..`) to prevent a malicious/erroneous channel name from escaping the intended config/session/state directory.

**Evidence:**
- `channels.py:43-51` contains `validate_channel_name` validator that checks for `/`, `\`, and `..`
- `test_config_reader.py:524,536,549,563` only use safe literal `"@test"` for `ChannelConfig(name=...)`
- `test_config_reader.py:477-502` tests `ClientConfig.session` path traversal but no equivalent exists for `ChannelConfig.name`

**Validation Note:**
> - **Action:** validated
> - **Detail:** The path-traversal guard on `ChannelConfig.name` exists and is critical because the name feeds filesystem path construction via `task.py:127` (`state_file = state_dir / f"{self.channel_name}.json"`). Without regression tests, a future accidental relaxation of this validator would go undetected.
> - **See also:** TST-002 (extra="forbid" guardrail is similarly untested)

**Recommendation:** Add parametrized cases asserting `ChannelConfig(name="a/b")`, `name="a\\b"`, and `name="a..b"` raise `ValueError` with the path-traversal message, and that `"@chan"` is accepted. *Effort: trivial. Priority: recommended.*

---

### TST-002: ~~`extra="forbid"` schema-strictness guardrail is untested across all Pydantic models~~ [VALIDATED]

| Field | Value |
|-------|-------|
| **ID** | TST-002 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `core/models.py`, `core/channels.py`, `core/telethon.py`, `tests/test_config_reader.py` |
| **Classification** | advisory |

**Description:** Every config model sets `extra="forbid"` as defense against silently accepting typo'd or injected YAML keys. No test asserts that an unknown key is rejected.

**Evidence:**
- `models.py:22` sets `extra="forbid"` on `TelepostSettings`
- `channels.py:22,60,91` sets `extra="forbid"` on `ChannelConfig`, `ChannelDefaults`, `ChannelsConfig`
- `telethon.py:35,101,178` sets `extra="forbid"` on `ProxyConfig`, `ClientConfig`, `TelethonConfig`
- `grep -r "extra|forbid|unknown|did not expect" tests/` yields no relevant matches for `ValidationError` testing

**Validation Note:**
> - **Action:** validated
> - **Detail:** All config models use `extra="forbid"` to reject unknown YAML keys. This is essential validation since config is user-facing (YAML files). Without tests, a future change to `extra="allow"` or a key typo in templates would silently pass invalid configuration.
> - **See also:** TST-001 (both relate to untested validator guards)

**Recommendation:** Add a focused test asserting that constructing each model with an unexpected top-level key raises `ValidationError` (e.g. `TelepostSettings(**{"BOGUS": 1})`). *Effort: small. Priority: recommended.*

---

### TST-003: ~~Property-based matcher tests assert only "no crash", not correctness~~ [VALIDATED]

| Field | Value |
|-------|-------|
| **ID** | TST-003 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `tests/test_parser.py` |
| **Classification** | advisory |

**Description:** `test_property_no_crash_basic` and `test_property_no_crash_generated` wrap `search_match` in `try/except` and assert only `isinstance(result, bool)`. A `search_match` that always returns `True` or always returns `False` would still pass.

**Evidence:**
- `test_parser.py:565-571`: Uses `try/except Exception: pytest.fail("Function crashed")` pattern
- `test_parser.py:577-582`: Same pattern with broader query generation
- The `except Exception` form masks unexpected exceptions, weakening Hypothesis diagnostics
- Strong parametrized `test_search_match` at line 558 provides actual correctness assertions

**Validation Note:**
> - **Action:** validated
> - **Detail:** Property tests with arbitrary inputs should verify meaningful invariants. The "no crash" assertion provides false confidence because incorrect matching logic would not fail. The try/except pattern also prevents Hypothesis from surfacing minimal counterexamples.
> - **See also:** `test_search_match` (lines 445-559) demonstrates the correct pattern with expected boolean outcomes

**Recommendation:** Strengthen with meaningful invariants (e.g. for query containing literal `t`, `search_match(t, f't')` is True; `search_match("", query)` is False for non-empty queries). Remove broad `except` so Hypothesis surfaces minimal counterexamples. *Effort: small. Priority: recommended.*

---

### TST-004: ~~Model/validator tests are colocated in `test_config_reader.py`, violating unit-per-module layout~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | TST-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `tests/test_config_reader.py`, `tests/test_monitor.py` |
| **Classification** | advisory |

**Description:** Validation logic for `channels.py`, `telethon.py`, and `models.py` is tested inside `tests/test_config_reader.py`; `monitor_client.py` functions are tested inside `tests/test_monitor.py` rather than dedicated per-module test files.

**Evidence:**
- `tests/test_config_reader.py` exists but no `test_models.py`, `test_channels.py`, or `test_telethon.py` files
- `TestValidators` class at line 413 covers model validation
- `tests/test_monitor.py` includes `TestCreateClient`, `TestStartClient`, `TestBuildMessageLink`, `TestBuildSenderTag` (monitor_client functions)

**Rejection reason:**
> The project's `problems_only=true` mode explicitly prioritizes bugs and security gaps over organizational preferences. Test file organization is an architectural preference, not a defect. The tests for `monitor_client` functions ARE present and comprehensive (lines 108-377 in test_monitor.py). The `TestValidators` class at line 413 validates the Pydantic models. Splitting these tests into separate files would be pure refactoring with no functional improvement. Per the validator guidelines: "Reject if ROI is negative for project scale."

---

### TST-005: ~~Audit phase spec references non-existent components (stale critical-path table)~~ [RECLASSIFIED]

| Field | Value |
|-------|-------|
| **ID** | TST-005 |
| **Severity** | LOW |
| **Original Type** | DOC-UPDATE |
| **New Type** | DOC-UPDATE |
| **Affected Modules** | `.kilo/commands/audit/phases/07-audit-tests.md` |
| **Classification** | advisory |

**Description:** The phase's "Critical Path Coverage" table mandates tests for `PostProcessor`, `ImageCache`, `TelegramPoster`, `GSheetsReader`, and `Init service`. These modules do not exist in the current codebase.

**Evidence:**
- `.kilo/commands/audit/phases/07-audit-tests.md:99-103` lists these non-existent components
- `src/mko_telebot/` contains: `cli, main, monitor, monitor_client, monitor_forward, logging` + `core/{config,matcher,models,parser,channels,errors,task,telethon,utils,paths,ast_nodes}`
- Actual forwarding/orchestration: `monitor_forward.py` / `monitor_client.py` / `monitor.py`

**Validation Note:**
> - **Action:** reclassified
> - **Detail:** The phase spec references stale component names from a different/earlier architecture. This misleads audit passes. However, the "Init service" DOES exist and IS tested: `test_cli.py:98-158` covers `init` command with template copying, force flag, and path creation tests. The spec should be updated but this is documentation debt, not missing test coverage.

**Recommendation:** Update the phase's critical-path table to actual modules (`monitor_forward.process_task`/`process_messages`/`forward_to_users`, `monitor_client`, `core/models`, `core/channels`, `core/telethon`, `cli` commands). *Effort: trivial. Priority: recommended.*

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 3 | TST-001, TST-002, TST-003 |
| Reclassified | 1 | TST-005 (clarified Init service exists and is tested) |
| Merged | 0 | — |
| Rejected | 1 | TST-004 (low ROI organizational preference, not a defect) |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| TST-004 | Model/validator tests are colocated in `test_config_reader.py` | Test file organization is an architectural preference with negative ROI for project scale; tests are present and comprehensive in existing files |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| TST-005 | DOC-UPDATE | DOC-UPDATE | Init service component exists and is tested; other listed components (PostProcessor, ImageCache, TelegramPoster, GSheetsReader) are stale references to old architecture |

---

## Warnings

- **Path traversal test gap (TST-001)**: The `ChannelConfig.name` validator guards filesystem path construction via `task.py:127`. Without regression tests, this security boundary is untested.
- **Schema strictness test gap (TST-002)**: All Pydantic models use `extra="forbid"` to prevent silent misconfiguration. This critical validation guard is untested.
- **Property test weakness (TST-003)**: Current property tests cannot detect incorrect matching logic, only crashes.

## Required Fixes

None (no production bug, data-loss, or security defect found; all 353 tests pass).

## Advisory Recommendations

- **TST-001** — Add regression tests for `ChannelConfig.name` path-traversal validator.
- **TST-002** — Add `extra="forbid"` rejection tests for all Pydantic config models.
- **TST-003** — Strengthen property-based matcher tests with meaningful invariants.
- **TST-005** — Refresh the audit phase's critical-path table to match actual architecture.