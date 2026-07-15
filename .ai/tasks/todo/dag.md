# Execution DAG - Task Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FOUNDATION LAYER (HIGH PRIORITY)                    │
│                           task_002 must execute first                         │
└─────────────────────────────────────────────────────────────────────────────┘

                               ┌──────────────────────┐
                               │ task_002             │
                               │ INT-001              │
                               │ monitor_client.py    │
                               │ (catch correct       │
                               │  Telethon ex)       │
                               └─────────┬────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
┌───────────────┐              ┌──────────────────────┐      ┌──────────────────────┐
│ task_001      │              │ task_003             │      │ task_008             │
│ CLI-001       │              │ INT-002              │      │ CFG-001              │
│ cli.py,       │              │ monitor_client.py    │      │ core/channels.py     │
│ monitor.py    │              │                      │      │ (fix list merge)     │
└───────────────┘              └──────────────────────┘      └──────────────────────┘
        │                                │                            │
        ▼                                ▼                            ▼
┌───────────────┐              ┌──────────────────────┐      ┌──────────────────────┐
│ task_004      │              │ task_011             │      │ task_006             │
│ CLI-002       │              │ INT-003              │      │ SRV-001/CLI-004/     │
│ cli.py        │              │ monitor_forward.py   │      │ INT-004 (dedup)      │
└───────────────┘              └──────────────────────┘      └──────────────────────┘
                                         │                            │
                                         ▼                            ▼
                              ┌──────────────────────┐      ┌──────────────────────┐
                              │ task_028 (verify)    │      │ task_029 (verify)    │
                              └──────────────────────┘      └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                           MEDIUM PRIORITY LAYER                             │
│                           Independent tasks                                 │
└─────────────────────────────────────────────────────────────────────────────┘

task_005 (CLI-003) - cli.py (init/version error handling)
task_007 (SRV-003) - monitor_forward.py (forward captionless media)
task_010 (QLT-001) - core/channels.py (keywords validation)
task_012 (QLT-002) - core/parser.py (TokenType StrEnum)
task_020 (SEC-001) - cli.py (preserve credentials on --force)
task_023 (TST-001) - tests (path traversal tests)
task_024 (TST-002) - tests (extra="forbid" tests)
task_025 (TST-003) - tests (property test invariants)
task_026 (TST-005) - docs (audit phase table)


┌─────────────────────────────────────────────────────────────────────────────┐
│                           LOW PRIORITY CLEANUP LAYER                        │
│                           Independent tasks                                   │
└─────────────────────────────────────────────────────────────────────────────┘

task_009 (CLI-005) - cli.py (exit code 130)
task_013 (QLT-003) - core/parser.py (remove None guard)
task_014 (QLT-005) - telethon.py, monitor_forward.py (f-strings)
task_015 (SRV-006) - core/task.py (remove unused param)
task_016 (INT-005) - monitor_forward.py (dead except branch)
task_017 (QLT-008) - core/paths.py (remove PathResolver)
task_018 (CLI-006) - pyproject.toml (type checker config)
task_019 (QLT-006) - core/task.py (set_offset_date error)
task_021 (SEC-002) - remove test.session (repo cleanup)
task_022 (SEC-003) - core/paths.py (file permissions)


┌─────────────────────────────────────────────────────────────────────────────┐
│                           VERIFICATION TASKS                                │
│                           Execute after dependencies                          │
└─────────────────────────────────────────────────────────────────────────────┘

task_027 - Verify CLI auth + exception handling (depends: 001, 002, 004)
task_028 - Verify fire-and-forget fixes (depends: 006, 011)
task_029 - Verify config/forwarding changes (depends: 007, 008, 010)
task_030 - Verify low-priority cleanup (depends: 009, 013-019)
task_031 - Verify security + test improvements (depends: 005, 020-026)
```

## File Modification Boundaries

| File | Tasks Modifying |
|------|-----------------|
| cli.py | task_001, task_004, task_005, task_020 |
| monitor.py | task_001, task_006 |
| monitor_client.py | task_002, task_003 |
| monitor_forward.py | task_007, task_011, task_016 |
| core/channels.py | task_008, task_010 |
| core/task.py | task_015, task_019 |
| core/parser.py | task_012, task_013 |
| core/telethon.py | task_014 |
| core/paths.py | task_017, task_022 |
| pyproject.toml | task_018 |
| tests/test_config_reader.py | task_023, task_024 |
| tests/test_parser.py | task_025 |
| test.session | task_021 (delete) |
| .kilo/commands/audit/phases/07-audit-tests.md | task_026 |


## Cross-Finding Resolution Summary

| Conflict | Resolution |
|----------|------------|
| INT-004 → SRV-001 | INT-004 is duplicate; see SRV-001 for fix |
| QLT-007 → SRV-002 | QLT-007 merged into SRV-002 (fire-and-forget pattern) |
| DF-004 → SRV-002 | Same fire-and-forget issue; consolidated |
| QLT-001 + SRV-004 | Same root cause (error swallowing); consolidated as task_010 |
| CLI-001 + INT-001 | INT-001 must be fixed first for CLI-001 to work correctly |
| INT-002 + INT-001 | Same exception-type mismatch pattern; INT-002 follows INT-001 |
| CLI-002 + INT-001 | Same broad exception handling; CLI-002 follows INT-001 |


## Duplicate Findings Addressed

| Original | Merged Into | Reason |
|----------|-----------|--------|
| INT-004 | TASK_006 | Duplicate fire-and-forget task issue |
| QLT-007 | TASK_006 | Same fire-and-forget pattern |
| DF-004 | TASK_006 | Same root cause |
| QLT-001 | TASK_010 | Same keywords error handling |
| SRV-004 | TASK_010 | Same keywords validation pattern |