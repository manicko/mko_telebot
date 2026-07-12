# Execution DAG for Validated Findings Implementation

## Task Dependencies Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Phase 1: Independent Configuration Fixes (can run in parallel)              │
└─────────────────────────────────────────────────────────────────────────────┘
         │               │               │               │               │
         ▼               ▼               ▼               ▼               ▼
  ┌─────────────┐  ┌──────────┐   ┌──────────┐   ┌───────────────┐   ┌──────────┐
  │ TASK_001    │  │ TASK_002 │   │ TASK_003 │   │ TASK_004      │   │ TASK_005 │
  │ cli package   │  │ utf8_bom │   │ proxy rdns │  │ google sheets   │  │ worker     │
  │ discovery     │  │ remove   │   │ validate   │   │ spec refs       │   │ busy      │
  └─────────────┘  └──────────┘   └──────────┘   └───────────────┘   └──────────┘
         │               │               │               │               │
         ▼               │               ▼               ▼               ▼
  ┌─────────────┐        │        ┌──────────┐   ┌───────────────┐   ┌──────────┘
  │ TASK_008    │        │        │ TASK_006 │   │ TASK_010      │   │ TASK_015
  │ atomic      │        │        │ proxy    │   │ test process  │   │ extract  │
  │ entity      │        │        │ secret   │   │ and forward   │   │ retry    │
  └─────────────┘        │        └──────────┘   └───────────────┘   │ helper   │
         │             │              │              ▲            └──────────┘
         ▼             │              ▼              │                   │
  ┌─────────────┐      │        ┌──────────┐         │                   │
  │ TASK_009    │      │        │ TASK_007 │         │                   ▼
  │ state save  │      │        │ session  │         │             ┌─────────────┐
  │ wrap        │      │        │ validate │         │             │ TASK_016    │
  └─────────────┘      │        └──────────┘         │             │ entity      │
         │             │              │              │             │ error tests │
         ▼             │              ▼              │             └─────────────┘
  ┌─────────────┐      │        ┌──────────┐         │
  │ TASK_014    │      │        │ TASK_014 │◄────────┘
  │ return type │      │        │ return type│
  │ annotation  │      │        │ annotation │
  └─────────────┘      │        └──────────┘
                       │
                       ▼
                ┌─────────────┐
                │ TASK_011    │
                │ setup_logging │
                │ and resolve_  │
                │ path tests  │
                └─────────────┘


                ┌─────────────┐
                │ TASK_012    │
                │ parser      │
                │ unit tests  │
                └─────────────┘


                ┌─────────────┐
                │ TASK_013    │
                │ fix over-   │
                │ mocking     │
                └─────────────┘
```

## Parallel Execution Groups

### Group A - Independent (run first, no dependencies)
- TASK_001: Fix pyproject.toml package discovery
- TASK_002: Remove UTF-8 BOM from template
- TASK_003: Validate proxy rdns field
- TASK_004: Remove Google Sheets spec references
- TASK_005: Add WorkerBusyTooLongRetryError handling
- TASK_008: Atomic entity resolution refactoring
- TASK_009: Wrap state save errors
- TASK_014: Add return type annotation

### Group B - After TASK_003
- TASK_006: Protect proxy credentials with SecretStr
- TASK_007: Validate session name path traversal

### Group C - After TASK_004
- TASK_010: Test process_task, run_monitor, main_loop, reschedule_task
- TASK_013: Fix over-mocking in process_messages tests

### Group D - After TASK_005
- TASK_015: Extract retry helper in forward_to_users
- TASK_016: Entity resolution error scenario tests

### Group E - Independent (no prerequisites)
- TASK_011: Test setup_logging and resolve_path
- TASK_012: Parser unit tests

### Verification Task
- TASK_099: Verify all implementations

## File Conflict Mapping

| File | Conflicting Tasks | Sequential Order |
|------|------------------|------------------|
| pyproject.toml | TASK_001 only | - |
| src/mko_telebot/.../telethon.py | TASK_003, TASK_005, TASK_006, TASK_007 | 003 → 005 → 006 → 007 |
| src/mko_telebot/.../task.py | TASK_008 only | - |
| src/mko_telebot/.../monitor_forward.py | TASK_005, TASK_014, TASK_015 | 005 → 015 → 014 |
| src/mko_telebot/.../monitor.py | TASK_008, TASK_009 | 008 → 009 |
| .kilo/commands/audit/... | TASK_004 only | - |
| tests/... | TASK_010, TASK_011, TASK_012, TASK_013, TASK_016 | Independent (different test files) |

## Risk Assessment

| Task | Risk | Reason |
|------|------|--------|
| TASK_001 | low | Configuration-only change |
| TASK_002 | low | File encoding fix |
| TASK_003 | low | Input validation addition |
| TASK_004 | low | Documentation-only change |
| TASK_005 | medium | Exception handling change in critical path |
| TASK_006 | medium | Model refactoring, credential protection |
| TASK_007 | low | Input validation addition |
| TASK_008 | medium | Refactoring Task entity resolution logic |
| TASK_009 | medium | Error handling changes could affect reliability |
| TASK_010 | low | Test addition only |
| TASK_011 | low | Test addition only |
| TASK_012 | low | Test addition only |
| TASK_013 | medium | Test refactoring could expose missing coverage |
| TASK_014 | low | Type annotation only |
| TASK_015 | medium | Function extraction in critical forwarding logic |
| TASK_016 | low | Test addition only |

## Rollout Notes

1. **TASK_001** should be verified first - if package still fails to import, subsequent fixes may be blocked

2. **TASK_003 → TASK_006** sequence: Proxy rdns validation must be added before introducing ProxyConfig model

3. **TASK_005 → TASK_015** sequence: WorkerBusyTooLongRetryError handling added before extracting retry helper ensures the helper includes all exception types

4. **TASK_010, TASK_013** depend on TASK_004: Tests may reference corrected operation patterns from spec updates

5. **All tasks are independently reversible** - no irreversible migrations or breaking schema changes exist