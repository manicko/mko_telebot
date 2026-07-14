# Execution DAG - Validated Audit Findings Implementation

## Overview
This document visualizes the dependency graph for implementing the validated audit findings
from `.ai/audit/99-validation/`. Tasks are organized in phases for safe rollout.

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FOUNDATION LAYER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TASK_001: Remove LogLevel enum (dead code)                                  │
│       ↓                                                                     │
│  TASK_002: Type safety in config/channels                                      │
│       ├──> TASK_003: ProxyType StrEnum (model)                                │
│       ├──> TASK_004: ConfigError message improvement                         │
│       └──> TASK_005: history_days validation                                 │
│                                                                              │
│  TASK_007: CLI unused result fix (standalone)                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────────────────┐
                              │                              │
                              ▼                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RUNTIME LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TASK_008: Empty channels validation (critical)                             │
│       ↓                                                                     │
│  TASK_009: Channel init error isolation                                      │
│       ↓                                                                     │
│  TASK_010: FloodWaitError entity resolution handling                          │
│       ↓                                                                     │
│  TASK_011: RPCError fetch handling                                          │
│                                                                              │
│  TASK_012: Empty keywords forward-all fix                                   │
│       ↓                                                                     │
│  TASK_013: Media captions in matching                                       │
│       ↓                                                                     │
│  TASK_014: Extract message grouping helper                                  │
│       ↓                                                                     │
│  TASK_015: Refactor long functions                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────────────────┐
                              │                              │
                              ▼                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TEST QUALITY LAYER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TASK_016: Sequence type for covariance                                        │
│       ├──> TASK_017: Remove TestSendWithRetry                                  │
│       ├──> TASK_018: Fix unreachable code                                    │
│       └──> TASK_020: Matcher internal tests                                    │
│                                                                              │
│  TASK_019: FloodWaitError test improvement                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Parallel Execution Opportunities

Tasks that can run in parallel (no interdependencies):
- TASK_006: CLI documentation update
- TASK_007: CLI unused result fix

## Risk Assessment Summary

| Task ID | Risk Level | Justification |
|---------|------------|---------------|
| TASK_001 | Low | Dead code removal, no impact |
| TASK_002 | Low | Type annotations only |
| TASK_003 | Medium | Model change with YAML backward compatibility |
| TASK_004 | Low | Error message only |
| TASK_005 | Low | Constraint addition, rejects only invalid input |
| TASK_007 | Low | Code quality fix |
| TASK_008 | Medium | Control flow change in main entry |
| TASK_009 | Medium | Error handling change |
| TASK_010 | Medium | Async error handling |
| TASK_011 | Medium | Exception handling extension |
| TASK_012 | Medium | Semantic behavior change |
| TASK_013 | Medium | Core matching logic change |
| TASK_014 | Medium | Refactor with behavior preservation |
| TASK_015 | Medium | Refactor of complex functions |
| TASK_016 | Low | Type hint change only |
| TASK_017 | Low | Test cleanup |
| TASK_018 | Low | Dead code removal |
| TASK_019 | Low | Test quality improvement |
| TASK_020 | Low | New test file |

## File Change Impact Matrix

| File | Modified By Tasks | Impact |
|------|-------------------|--------|
| src/mko_telebot/core/channels.py | 001, 002, 005 | LogLevel removal, type annotations, history_days constraint |
| src/mko_telebot/core/config.py | 002, 004 | Type annotations, error message |
| src/mko_telebot/core/telethon.py | 003 | ProxyType StrEnum |
| src/mko_telebot/core/task.py | 010 | FloodWaitError handling |
| src/mko_telebot/monitor.py | 008, 009 | Empty channels check, error isolation |
| src/mko_telebot/monitor_forward.py | 011, 012, 013, 014, 015, 016 | Error handling, matching, refactoring |
| src/mko_telebot/cli.py | 007 | Unused result fix |
| docs/99-reference/cli-reference.md | 006 | Documentation update |
| tests/test_monitor_forward.py | 017, 018, 019 | Test cleanup, improvements |
| tests/test_monitor.py | 019 | FloodWaitError test improvement |
| tests/test_matcher.py | 020 | New file for matcher tests |