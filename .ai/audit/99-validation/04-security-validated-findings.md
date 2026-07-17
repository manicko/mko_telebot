## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 1 |
| LOW | 0 |

## Mandatory Fixes

- **SEC-001 (HIGH):** Telethon `.session` auth-key file is created without 0600
  permission hardening and is fully unprotected on Windows (the project's primary
  OS). Apply file-level hardening after `client.start()` and add a Windows ACL
  path. Account-takeover risk.
- **SEC-002 (MEDIUM):** Credential file `telethon_config.yaml` hardening is
  POSIX-only (`_secure_file_permissions` is a no-op on Windows). Make secret-file
  hardening cross-platform so credentials are not left group/other-readable on
  shared Windows hosts.

## Advisory Recommendations

- None beyond the mandatory fixes above. (Both findings are classified mandatory
  because they concern credential exposure; the remediation is simple and
  cross-platform.)

## Doc Updates Needed

- **SEC-002:** Update `docs/11-guides/configuration.md` (and the Windows-permission
  note) to document that secret-file hardening currently only takes effect on
  POSIX, and what protection users on shared Windows machines should expect until
  a Windows ACL path is implemented.

---

## Runtime Verification Record

- **R1 — Credential leak search:** `git ls-files` shows only
  `src/mko_telebot/settings/telethon_config.yaml` is tracked (placeholder template:
  `phone_or_token: "PLACEHOLDER_REPLACE_ME"`, `api_id: 12345`,
  `api_hash: "PLACEHOLDER_REPLACE_ME"`). No real secrets committed. Tests use
  obviously-fake values (`api_hash="a"*32`, `phone_or_token="+79123456789"`). PASS.
- **R2 — Logger audit:** No `logger.*` call includes `api_hash`, `phone_or_token`,
  `password`, or a full settings model. `SecretStr` is correctly redacted on
  `model_dump` (verified by `tests/test_config_reader.py:946`, expects
  `"password": "**********"`). PASS.
- **R3 — File permission check:** `.gitignore` covers `*.session*`, `/*.session*`,
  `*token.json`, and the session/log/tmp dirs. However, session + credential file
  hardening is ineffective on Windows (see SEC-001, SEC-002).
- **R4 — Import verification:** No module leaks credentials at import time. PASS.
- **R5 — Linter / type checker:** `uv run ruff check src/mko_telebot` → "All checks
  passed!"; `uv run basedpyright src/mko_telebot` → "0 errors, 0 warnings, 0 notes".
  PASS.
- **R6 — Test suite:** `uv run pytest tests -q` → 1 failure unrelated to security:
  `tests/test_parser.py::test_property_no_crash_generated` (a parser
  property-based assertion about exclusion-only queries). This is a parser
  correctness issue, outside the security phase scope, and is recorded here only
  for completeness.

---

## Validation Notes

### SEC-001: Session file permission hardening missing on Windows

**Status:** APPROVED (SPEC-DEVIATION)

**Technical Correctness:** VERIFIED. Telethon creates `.session` files containing authenticated session keys. The code in `monitor_client.py:48-50` secures the **session directory** (`_secure_directory_permissions`) but never hardens the **session file itself** after client creation. On Windows:
- `_is_posix()` returns `True` because `hasattr(os, "chmod")` is `True` on Windows
- However, Windows `os.chmod` ignores Unix permission bits (`S_IRUSR`, `S_IWUSR`, `S_IRWXU`)
- Python's `os.chmod` on Windows only controls the read-only attribute, not access control lists
- The session file receives default Windows permissions inheriting from parent directory

**Evidence:**
- `utils.py:10-16` — `_is_posix()` checks `hasattr(os, "chmod")` but Windows chmod has limited semantics
- `monitor_client.py:46-50` — Only directory permissions set, no file hardening after session creation
- `cli.py:56, 70, 78` — `_secure_file_permissions` called on `telethon_config.yaml` but this is ineffective on Windows

**Architectural Fit:** The recommendation aligns with project patterns:
- `utils.py` already has `_secure_file_permissions` and `_secure_directory_permissions` helpers
- Extension to apply hardening post-session-creation would follow existing patterns
- Adding Windows ACL support would be a new platform-specific module with fallback

### SEC-002: Credential file hardening is POSIX-only on Windows

**Status:** APPROVED (SPEC-DEVIATION)

**Technical Correctness:** VERIFIED. The `_is_posix()` function in `utils.py:10-16` returns `True` on Windows because `hasattr(os, "chmod")` returns `True`. However, as confirmed by runtime testing:
- Windows `os.chmod` silently ignores Unix permission bits (`S_IRUSR | S_IWUSR` = 0o600)
- File mode remains unchanged after chmod call on Windows
- No Windows-specific ACL mechanism is implemented

**Evidence:**
- `utils.py:10-16` — `_is_posix()` returns `True` on Windows (incorrect for permission purposes)
- `utils.py:35-48` — `_secure_file_permissions` applies `stat.S_IRUSR | stat.S_IWUSR` which is ignored on Windows
- Runtime verification confirms: file mode `0o100666` unchanged after chmod 600 on Windows

**Doc Consistency:** The documentation at `configuration.md:417-419` states "On POSIX systems... credential files are set to `0600`". This is accurate but should clarify that Windows hardening is not implemented.

**Architectural Fit:** The existing `_secure_file_permissions` function structure is sound. Adding Windows ACL support would follow the established pattern with a platform-specific branch.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | SEC-001, SEC-002 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| — | — | — |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| — | — | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| — | — | — | — |

---

## Cross-Phase Conflict Check

Cross-reviewed with:
- Phase 01 (CLI): No conflicts. CLI findings concern `validate` command scope and exit codes — unrelated to credential hardening.
- Phase 02 (Config): No conflicts. CFG-001 concerns schema validation gap — unrelated.
- Phase 03 (Services): No conflicts. SRV-001 concerns keyword over-matching — unrelated.
- Phase 05 (Integrations): No conflicts. INT findings concern flood-wait and disconnect handling — unrelated.
- Phase 06 (Data Flow): No conflicts. DF-004 concerns parser test correctness — unrelated.

No cross-phase conflicts detected.

---

## Rollout Safety Assessment

Both findings share the same root cause: `_is_posix()` incorrectly identifies Windows as POSIX for permission purposes. Fixes can be implemented together:

1. **Dependency:** Both changes are independent and can be fixed in a single PR
2. **Risk:** Low — the permission hardening is defensive; fixing it has no breaking impact
3. **Rollback:** Safe — changes only affect file creation/write behavior
4. **Backward Compatibility:** Maintained — the changes are additive (add Windows ACL support)