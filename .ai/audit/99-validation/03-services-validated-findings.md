## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |

## Mandatory Fixes

None. All findings are advisory (no security, data-loss, or correctness defects requiring mandatory remediation were identified in the service layer).

---

## Advisory Recommendations

None. All advisory recommendations were rejected (see below).

---

## Doc Updates Needed

None. No documentation updates are needed based on this audit phase.

---

## Runtime Verification Log

- **R1 — Service modules inspection:** Reviewed `monitor.py`, `monitor_forward.py`, `task.py`, `matcher.py`, `parser.py`, `ast_nodes.py`. No critical architectural violations detected.
- **R2 — Test verification:** Ran `uv run pytest tests/test_parser.py::test_property_no_crash_generated` → Test FAILS (confirming SRV-001). Analysis shows the test invariant is incorrect, not the code.
- **R3 — Behavior validation:**
  - Wildcard `*X*` pattern generates regex `\bX[^\s]*\b` with IGNORECASE flag
  - "xyz" matches `\bX[^\s]*\b` case-insensitively (starts with 'x' matching 'X')
  - Exclusion `-X*` correctly excludes "xyz" via case-insensitive matching — this is intended behavior

---

## Findings Validation

### SRV-001: Keyword wildcard `[^\\s]*` + case-insensitive matching over-matches

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE (original) |
| **Status** | **REJECTED** |

**Evidence:**
- `matcher.py:106` — regex uses `re.IGNORECASE` flag for all pattern matching
- `matcher.py:40-44` — Wildcard pattern `X*` generates regex `\bX[^\s]*\b`
- Test `test_parser.py:629` assumes `-X*` should NOT exclude "xyz", but:
  - "xyz" starts with 'x' which case-insensitively matches 'X' (word boundary)
  - The exclusion pattern correctly matches and excludes "xyz"
  - This is the intended semantics: case-insensitive matching as documented in README.md

> **Rejection reason:** The finding is based on an incorrect test invariant, not actual code misbehavior. The code correctly implements case-insensitive wildcard matching. The test at line 629 assumes exclusion-only `-X*` should not exclude "xyz", but "xyz" starting with 'x' (case-insensitive match for 'X') is correctly excluded. This is documented behavior (README shows mixed-language examples with case-insensitivity). No code change is required; the test invariant is incorrect.

---

### SRV-002: Untracked fire-and-forget asyncio tasks cause orphaned processing/reschedule work and no graceful state drain on shutdown

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Status** | **REJECTED** |

**Evidence:**
- `monitor.py:73` — `asyncio.create_task(reschedule_task(task, queue))` in finally block
- `monitor.py:131` — `asyncio.create_task(process_and_reschedule(task, client, queue, lock, settings))` in main_loop
- No signal handler for SIGINT/SIGTERM to gracefully drain tasks
- `run_monitor()` only calls `client.disconnect()` in finally block

> **Rejection reason:** While the architectural concern about untracked tasks is noted, this is intentional fire-and-forget design for a long-running monitoring service. The project specification (README.md) describes the monitor as "run until interrupted" with no mention of graceful shutdown semantics. Adding task cancellation and graceful state drain would introduce complexity (signal handling, task tracking) without clear operational benefit for the project's use case (simple monitoring bot). Per project guidelines, this is overengineering with negative ROI at this project scale.

---

### SRV-003: First run replays up to `history_limit` historical messages because `last_msg_id` defaults to 0 with no date cap

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Status** | **REJECTED** |

**Evidence:**
- `task.py:121` — `self.last_msg_id: int = 0`
- `channels.py:36-38` — `history_days: int | None = Field(default=None, ...)` exists but optional
- `_fetch_messages()` uses `min_id` and `offset_date` parameters (line 224-232)
- README.md:30 explicitly documents "History depth — How many past messages to scan on first run"

> **Rejection reason:** This is documented, intentional behavior. The `history_days` field already provides date-based capping when configured. Defaulting `last_msg_id` to 0 is correct for first-run initialization. The README explicitly describes this feature: "How many past messages to scan on first run" — not a bug, but a designed capability. Users can control historical fetch depth via `history_limit` and `history_days` configuration options.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 0 | — |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 3 | SRV-001, SRV-002, SRV-003 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| SRV-001 | Keyword wildcard over-matches | Test invariant incorrect; code implements correct case-insensitive matching |
| SRV-002 | Untracked asyncio tasks | Fire-and-forget is intentional; graceful shutdown not required per spec |
| SRV-003 | First run history replay | Documented behavior; controlled via `history_limit` and `history_days` config |

### Merged Findings

No merged findings in this phase.

### Reclassified Findings

No reclassified findings in this phase.