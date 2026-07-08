# Execution DAG - Implementation Task Graph

## Graph Legend

- **Priority Levels:**
  - HIGH: CRITICAL bugs that break the application
  - MEDIUM: Security improvements, code quality fixes
  - LOW: Advisory changes, documentation updates

- **Dependency Types:**
  - `depends_on`: Task must complete before this one starts
  - `conflicts_with`: Tasks that modify same file must be sequential
  - `shares_infrastructure`: Tasks that benefit from shared test fixtures

## Phase 1: Critical Blocking Fixes (Must be first)

```
task_001_fix_monitoring_attribute → task_003_implement_retry_logic
                       ↘
                    task_013_verify_init_copied_config

task_002_fix_secrets_template → task_005_fix_config_template
                        ↘
                   task_020_verify_critical_fixes

task_003_implement_retry_logic ↗
task_005_fix_config_template ↗
task_020_verify_critical_fixes (depends on both)
```

## Parallel Execution Groups (within phases)

### Group A: Parallel (no dependencies)
- task_001_fix_monitoring_attribute
- task_002_fix_secrets_template
- task_004_add_channel_name_validation
- task_006_add_extra_forbid
- task_009_add_task_model_tests
- task_010_add_monitor_tests
- task_014_add_type_hints_task
- task_016_add_type_hints_parser
- task_017_remove_unused_logger
- task_018_update_chatsconfig_docs
- task_019_update_monkeypatch_tests

### Group B: Sequential (depends on Group A)
- task_003_implement_retry_logic (depends on task_001)
- task_005_fix_config_template (depends on task_002)
- task_011_add_validator_tests (depends on task_005)
- task_012_add_run_error_tests (depends on task_008)
- task_013_verify_init_copied_config (depends on task_001, task_005)
- task_015_add_type_hints_monitor (depends on task_007)

### Group C: Cleanup / Removal (no dependencies)
- task_007_remove_dead_code_launcher
- task_008_add_exception_handling_run (depends on task_007)

### Group D: Verification (final)
- task_020_verify_critical_fixes (depends on tasks 001, 002, 003, 005)

## File-Based Dependencies (sequential modifications)

| File | Tasks (must run sequentially) |
|------|-------------------------------|
| `src/mko_telebot/monitor.py` | task_001, task_003, task_007, task_015 |
| `tests/test_cli.py` | task_012, task_013, task_019 |
| `tests/test_config_reader.py` | task_011 |
| `src/mko_telebot/core/task.py` | task_014 |
| `src/mko_telebot/core/parser.py` | task_016 |
| `src/mko_telebot/core/paths.py` | task_017 |
| `src/mko_telebot/core/models.py` | task_006 |
| `src/mko_telebot/core/channels.py` | task_004 |
| `src/mko_telebot/cli.py` | task_008 |
| `src/mko_telebot/settings/secrets.yaml` | task_002 |
| `src/mko_telebot/settings/config.yaml` | task_005 |
| `docs/11-guides/configuration.md` | task_018 |

## Execution Order Summary

| Order | Task ID | Title | Priority |
|-------|---------|-------|----------|
| 1 | task_001 | Fix settings.monitoring attribute error | HIGH |
| 2 | task_002 | Fix secrets.yaml template placeholders | HIGH |
| 3 | task_003 | Implement retry logic for Telegram sending | HIGH |
| 4 | task_004 | Add channel name validators | MEDIUM |
| 5 | task_005 | Fix config.yaml template structure | HIGH |
| 6 | task_006 | Add extra="forbid" to TelepostSettings | MEDIUM |
| 7 | task_007 | Remove dead code launcher() | MEDIUM |
| 8 | task_008 | Add exception handling in run command | MEDIUM |
| 9 | task_009 | Add Task model unit tests | HIGH |
| 10 | task_010 | Add monitor module unit tests | HIGH |
| 11 | task_011 | Add Pydantic validator tests | MEDIUM |
| 12 | task_012 | Add run CLI error path tests | MEDIUM |
| 13 | task_013 | Verify init-copied config loads | MEDIUM |
| 14 | task_014 | Add type hints to Task methods | MEDIUM |
| 15 | task_015 | Add type hints to monitor functions | MEDIUM |
| 16 | task_016 | Add type hints to parser methods | LOW |
| 17 | task_017 | Remove unused logger in paths.py | LOW |
| 18 | task_018 | Update documentation to ChannelsConfig | MEDIUM |
| 19 | task_019 | Refactor tests to use monkeypatch | LOW |
| 20 | task_020 | Verify critical fixes | HIGH |
| 21 | task_021 | Rollback procedure | - |

## Risk Assessment

| Risk Level | Tasks | Rationale |
|------------|-------|-----------|
| HIGH | task_001, task_002, task_003, task_005, task_009, task_010 | Runtime breakage potential, no existing tests |
| MEDIUM | task_004, task_006, task_007, task_008, task_011, task_012, task_013, task_014, task_015, task_018 | Security improvements, code quality |
| LOW | task_016, task_017, task_019 | Trivial effort, minimal impact |

## Notes

1. **CFG-004 must precede CFG-002** - Fixed in task_002 before task_005 so sentinel validation errors don't mask config structure errors.

2. **CLI-002 and SRV-002 overlap** - task_007 removes launcher(), making the type hint recommendation in task_015 only apply to build_message_link (not launcher).

3. **TST-001 and TST-002 share infrastructure** - Both require async test patterns with mocked TelethonClient. Consider adding shared conftest fixture.

4. **No SPEC.md exists** - Advisory recommendations (CFG-006, QLT-002/003/004) lack spec cross-reference but are still valuable for code quality.