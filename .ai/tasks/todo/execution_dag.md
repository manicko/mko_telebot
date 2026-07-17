# Execution DAG for Validated Findings Implementation

## Dependency Graph

```
task_022_research_windows_acl_approach (BLOCKED)
    └── blocks: task_004, task_005

task_001_fix_validate_schema
    └── files: cli.py, config.py
    └── independent

task_002_skip_orphan_file_in_init
    └── files: cli.py
    └── independent

task_003_format_log_config_yaml
    └── files: settings/log_config.yaml, config.py
    └── independent

task_004_secure_session_file_windows (blocked until research complete)
    └── files: monitor_client.py, utils.py
    └── depends: task_022

task_005_credential_file_hardening_cross_platform (blocked until research complete)
    └── files: utils.py
    └── depends: task_004

task_006_wrap_rpcerror_telegram_service
    └── files: monitor_forward.py, monitor.py
    └── independent (first critical integration fix)

task_007_retry_floodwait_fetch
    └── files: monitor_forward.py
    └── depends: task_006

task_008_enable_telethon_flood_sleep_threshold
    └── files: monitor_client.py, task.py
    └── independent

task_009_add_2fa_password_support
    └── files: telethon.py, monitor_client.py, settings/telethon_config.yaml
    └── depends: task_004 (security context)

task_010_add_sender_tag_retry
    └── files: monitor_client.py
    └── independent

task_011_retry_entity_resolution_floodwait
    └── files: task.py
    └── depends: task_008

task_012_await_client_disconnect
    └── files: monitor.py
    └── depends: task_006

task_013_multi_entity_target_error
    └── files: task.py
    └── independent

task_014_move_queue_put_before_sleep
    └── files: monitor.py
    └── independent

task_015_update_docs_exit_code
    └── files: docs/cli-reference.md
    └── independent

task_016_update_docs_auth_failure
    └── files: docs/cli-reference.md
    └── independent

task_017_fix_property_test_invariant
    └── files: tests/test_parser.py
    └── independent

task_018_resolve_formatter_conflict
    └── files: .pre-commit-config.yaml
    └── independent

task_019_run_ruff_format
    └── files: all Python files
    └── depends: task_018

task_020_add_smoke_test_main_entry
    └── files: tests/test_main.py (new)
    └── independent

task_021_verify_integration_fixes
    └── type: verification
    └── verifies: 006, 007, 011, 012, 013
    └── depends: all integration tasks
```

## Parallel Execution Groups

### Group A (No dependencies, can start immediately)
- task_001_fix_validate_schema
- task_002_skip_orphan_file_in_init
- task_003_format_log_config_yaml
- task_006_wrap_rpcerror_telegram_service
- task_008_enable_telethon_flood_sleep_threshold
- task_010_add_sender_tag_retry
- task_013_multi_entity_target_error
- task_014_move_queue_put_before_sleep
- task_015_update_docs_exit_code
- task_016_update_docs_auth_failure
- task_017_fix_property_test_invariant
- task_018_resolve_formatter_conflict
- task_020_add_smoke_test_main_entry

### Group B (Depends on Group A tasks)
- task_007_retry_floodwait_fetch (after 006)
- task_011_retry_entity_resolution_floodwait (after 008)
- task_012_await_client_disconnect (after 006)
- task_019_run_ruff_format (after 018)

### Group C (Security tasks, blocked on research)
- task_022_research_windows_acl_approach
- task_004_secure_session_file_windows (blocked)
- task_005_credential_file_hardening_cross_platform (blocked)
- task_009_add_2fa_password_support (after 004)

### Group D (Verification)
- task_021_verify_integration_fixes (after all integration tasks)

## File-Level Sequencing Requirements

| File | Tasks Modifying | Sequential Order |
|------|-----------------|------------------|
| cli.py | 001, 002 | 001 → 002 (different functions, can be parallel) |
| config.py | 001, 003 | 001 → 003 (different areas, can be parallel) |
| monitor_forward.py | 006, 007 | 006 → 007 |
| task.py | 008, 011, 013 | Can be parallel (different functions) |
| monitor_client.py | 004, 008, 009, 010 | 008 → 004 → 009 → 010 |
| utils.py | 004, 005 | 004 → 005 |
| .pre-commit-config.yaml | 018 | standalone |
| telethon_config.yaml | 009 | standalone |
| tests/test_parser.py | 017 | standalone |
| tests/test_main.py | 020 | standalone |
| docs/cli-reference.md | 015, 016 | can be parallel |

## Risk Assessment

### High Risk (Blocked)
- task_022_research_windows_acl_approach: Unclear Windows ACL implementation approach
- task_004_secure_session_file_windows: Blocked pending research
- task_009_add_2fa_password_support: Requires new config field migration path

### Medium Risk
- task_006_wrap_rpcerror_telegram_service: Core error handling change, could affect all forwarding
- task_007_retry_floodwait_fetch: State persistence on flood wait edge cases
- task_011_retry_entity_resolution_floodwait: Startup reliability

### Low Risk
- All documentation, formatting, and test-fix tasks
- task_014_move_queue_put_before_sleep: Simple reordering