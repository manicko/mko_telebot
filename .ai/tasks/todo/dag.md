# Execution Dependency Graph (DAG)
# Generated from validated findings analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MANDATORY FIXES                                     │
└─────────────────────────────────────────────────────────────────────────────┘

TASK_001_type_hints_monitor
├── affects: src/mko_telebot/monitor.py, src/mko_telebot/core/task.py
├── functions: build_message_link, build_sender_tag, forward_to_users, process_messages
├── methods: resolve_targets_entities, resolve_channel_entity
├── depends_on: (none)
└── required_before: TASK_004, TASK_006, TASK_011, TASK_014 (all modify same files)

TASK_002_exception_specificity_cli
├── affects: src/mko_telebot/cli.py
├── function: run
├── depends_on: (none)
└── parallel_with: TASK_001, TASK_003

TASK_003_apply_channel_defaults
├── affects: src/mko_telebot/core/channels.py
├── class: ChannelsConfig
├── depends_on: (none)
└── parallel_with: TASK_001, TASK_002

TASK_004_secretstr_serialization
├── affects: src/mko_telebot/monitor.py
├── function: create_client
├── depends_on: TASK_001 (same file - sequential modification required)
└── no_cross_phase_conflicts: INT-002/DF-002 are identical findings

┌─────────────────────────────────────────────────────────────────────────────┐
│                         ADVISORY TASKS                                      │
└─────────────────────────────────────────────────────────────────────────────┘

TASK_005_remove_dead_code_utils
├── affects: src/mko_telebot/core/utils.py
├── functions: list_files_in_directory, load_config, merge_dicts, resolve_path
├── depends_on: (none)
└── merges: CLI-002 + QLT-002 + QLT-004 (duplicate resolve_path)

TASK_006_remove_unnecessary_exceptions
├── affects: src/mko_telebot/monitor.py
├── functions: build_message_link, build_sender_tag, process_messages
├── depends_on: TASK_001 (same file - sequential modification)
└── merges: CLI-004 + QLT-005 (exception handling concerns)

TASK_007_fix_malformed_config_template
├── affects: src/mko_telebot/settings/keyw_config_example_keep.yaml
├── depends_on: (none)
└── independent: CFG-003 is isolated to settings

TASK_008_refactor_search_match
├── affects: src/mko_telebot/core/parser.py
├── function: search_match
├── depends_on: (none)
└── complexity_reduction: splits 77-line function (complexity 15)

TASK_009_remove_unused_dependency
├── depends_on: (none)
└── isolated_change: QLT-003 no code dependencies

TASK_010_simplify_secrets_template
├── depends_on: (none)
└── independent: SEC-004 is isolated

TASK_011_client_disconnect_cleanup
├── affects: src/mko_telebot/monitor.py
├── function: run_monitor
├── depends_on: TASK_001 (same file - sequential modification)
└── related_findings: INT-003, DF-003 (client lifecycle)

TASK_012_simplify_offset_date
├── affects: src/mko_telebot/core/task.py
├── function: set_offset_date
├── depends_on: (none)
└── related_findings: SRV-002 (redundant assignment)

TASK_013_split_parser_module
├── action: file split
├── depends_on: (none)
└── related_findings: STR-005 (file length)

TASK_014_split_monitor_module
├── action: file split
├── depends_on: TASK_001, TASK_004, TASK_006 (monitor.py modifications)
└── related_findings: STR-006 (file length)

TASK_015_fix_bom_file
├── affects: src/mko_telebot/core/__init__.py
├── action: remove UTF-8 BOM
├── depends_on: (none)
└── related_findings: STR-010 (BOM character)

TASK_099_verify_mandatory_fixes
├── type: verification
├── verifies: TASK_001, TASK_002, TASK_003, TASK_004
├── depends_on: All mandatory tasks
└── steps: ruff check, pytest, mypy smoke_check

┌─────────────────────────────────────────────────────────────────────────────┐
│                         PARALLEL EXECUTION GROUPS                           │
└─────────────────────────────────────────────────────────────────────────────┘

Group 1 (concurrent safe):
├── TASK_001_type_hints_monitor
├── TASK_002_exception_specificity_cli
├── TASK_003_apply_channel_defaults
├── TASK_005_remove_dead_code_utils
├── TASK_007_fix_malformed_config_template
├── TASK_008_refactor_search_match
├── TASK_009_remove_unused_dependency
├── TASK_010_simplify_secrets_template
└── TASK_012_simplify_offset_date

Group 2 (depends on Group 1):
├── TASK_004_secretstr_serialization (monitor.py, after TASK_001)
├── TASK_006_remove_unnecessary_exceptions (monitor.py, after TASK_001)
├── TASK_011_client_disconnect_cleanup (monitor.py, after TASK_001)
└── TASK_014_split_monitor_module (monitor.py, after TASK_001, TASK_004, TASK_006)

Group 3 (verification):
└── TASK_099_verify_mandatory_fixes (all mandatory tasks complete)

┌─────────────────────────────────────────────────────────────────────────────┐
│                         FILE MODIFICATION DEPS                              │
└─────────────────────────────────────────────────────────────────────────────┘

monitor.py: TASK_001 → TASK_004/TASK_006/TASK_011/TASK_014
  (tasks modifying same file must be sequential)

cli.py: TASK_002 (no other modifications)

channels.py: TASK_003 (no other modifications)

task.py: TASK_001 (type hints), TASK_012 (offset_date)

utils.py: TASK_005 (no other modifications)

parser.py: TASK_008, TASK_013 (file split)

pyproject.toml: TASK_009 (no other modifications)

secrets.yaml: TASK_010 (no other modifications)

keyw_config_example_keep.yaml: TASK_007 (no other modifications)

core/__init__.py: TASK_015 (BOM removal)
```