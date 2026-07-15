## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 0 |
| LOW | 2 |

## Mandatory Fixes

- **CFG-001** (HIGH, correctness): Per-channel `keywords`/`forward_to` are unconditionally overwritten by `defaults` in `ChannelsConfig.apply_defaults_to_channels`. With the shipped template's empty-list defaults, every channel silently loses its forwarding targets, disabling the core feature. Fix the list-field merge so explicit per-channel values are preserved; add test coverage for list overrides.

## Advisory Recommendations

- **CFG-002** (LOW): `init` copies `keyw_config_example_keep.yaml` (unused example) into the user config dir. Exclude example files from the copy or relocate the example outside `settings/`.
- **CFG-003** (LOW): `log_config.yaml` defines loggers `"__main__"` and `"telebot"` that never match the real `mko_telebot.*` logger names; those blocks are dead. Use `"mko_telebot"` (or rely on `root`).

## Doc Updates Needed

- **CFG-002**: Docs/example placement should reflect that `keyw_config_example_keep.yaml` is not part of the active config set copied by `init`.
- **CFG-003**: `log_config.yaml` logger names should match the documented `getLogger(__name__)` hierarchy (`mko_telebot.*`).
