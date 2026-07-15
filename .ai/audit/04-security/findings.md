
## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 2 |

## Mandatory Fixes

- **SEC-001** — `init --force` overwrites the user's real `telethon_config.yaml` with the placeholder template, causing irreversible loss of Telegram credentials and invalidating the session. Should be fixed (separate the secrets file from the template-copy flow) and the CLI reference updated.

## Advisory Recommendations

- **SEC-002** — Remove the stray real `test.session` (28 KB auth DB) from the repo root and add a guard ensuring sessions are never created outside `USER_DIR`.
- **SEC-003** — Enforce `0600` on `telethon_config.yaml` (and `0700` on its directory) so credentials are not world/group-readable on multi-user POSIX systems.

## Doc Updates Needed

- **SEC-001** — `docs/99-reference/cli-reference.md` (lines 67-74, 89-93) should state that `telethon_config.yaml` (the credential store) is never overwritten by `init`, even with `--force`, and that credentials are created from a non-destructive example.
