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
