
## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 2 |

## Mandatory Fixes

None. All findings are advisory (no security, data-loss, or correctness defects requiring mandatory remediation were identified in the service layer).

## Advisory Recommendations

- **SRV-001** (MEDIUM): Keyword wildcard `[^\s]*` + case-insensitive matching over-matches; reconcile with the failing property test `tests/test_parser.py:629`.
- **SRV-002** (LOW): Untracked fire-and-forget asyncio tasks cause orphaned processing/reschedule work and no graceful state drain on shutdown.
- **SRV-003** (LOW): First run replays up to `history_limit` historical messages because `last_msg_id` defaults to 0 with no date cap.

## Doc Updates Needed

- **SRV-001** (`[DOC-UPDATE]`): The matcher wildcard contract (`*` → `[^\s]*`, case-insensitive) and its over-matching implications should be documented in the keyword-filter reference so operators can configure filters predictably; the divergent test expectation should be resolved in phase 07.
