# Phase 01 DAG Analysis — Configuration & Anti-Blocking Updates

## File Modification Dependencies (Critical)

| Task ID | Files Modified | Sequential Required With |
|---------|---------------|----------------------|
| TASK_016_rename_secrets_yaml | telethon_config.yaml (rename), config.py, paths.py, test_config_reader.py | — |
| TASK_016b_add_proxy_dependency | pyproject.toml | — |
| TASK_017_add_proxy_field | telethon.py (ClientConfig.proxy) | TASK_018, TASK_019 (same file) |
| TASK_018_placeholder_validation | telethon.py (validators) | TASK_017, TASK_019 (same file) |
| TASK_019_api_hash_validation | telethon.py (ClientConfig.api_hash) | TASK_017, TASK_018 (same file) |
| TASK_020_device_examples | telethon_config.yaml | TASK_016 (same file) |

## Execution Order (Topological Sort)

```
Phase 01 Execution Sequence:

Wave 1 (parallel execution):
  TASK_016_rename_secrets_yaml      (file rename)
  TASK_016b_add_proxy_dependency    (pyproject.toml)

Wave 2 (sequential telethon.py chain):
  TASK_018_placeholder_validation   → TASK_019_api_hash_validation → TASK_017_add_proxy_field
  (all modify telethon.py - must be sequential)

Wave 3 (after TASK_016):
  TASK_020_device_examples          (adds comments to renamed file)

Verification:
  TASK_099_verify_phase_01
```

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Wave 1 (parallel)                                                       │
│   TASK_016_rename_secrets_yaml ──────────────→ TASK_020_device_examples│
│   TASK_016b_add_proxy_dependency                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Wave 2 (sequential telethon.py chain)                                   │
│   TASK_018_placeholder_validation                                       │
│                    ↓                                                    │
│   TASK_019_api_hash_validation                                          │
│                    ↓                                                    │
│   TASK_017_add_proxy_field                                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Verification                                                            │
│   TASK_099_verify_phase_01                                             │
│   (verifies TASK_016, 016b, 017, 018, 019, 020)                      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Risk Assessment

| Task | Risk Level | Notes |
|------|------------|-------|
| TASK_016 | medium | File rename across 4 files, test helper update |
| TASK_016b | low | Simple pyproject.toml addition |
| TASK_018 | low | Extends 3 validator methods in telethon.py |
| TASK_019 | low | Updates api_hash field constraint |
| TASK_017 | medium | Adds proxy field to ClientConfig model |
| TASK_020 | low | Documentation comments in YAML template |

## Conflict Resolution Applied

1. **Same-file constraint**: TASK_017, TASK_018, TASK_019 all modify `telethon.py`
   - Resolution: Explicit sequential dependencies established: 018 → 019 → 017

2. **Missing dependency**: Per RESEARCH_01.md Section 9, `python-socks[asyncio]` required for proxy
   - Resolution: Created TASK_016b_add_proxy_dependency (runs parallel with TASK_016)

## Notes

- All Phase 01 tasks are independent of previous phases (TASK_001-015)
- Sequential chain in telethon.py is: validators → field constraint → new field
- This ordering minimizes merge conflicts while preserving semantic isolation