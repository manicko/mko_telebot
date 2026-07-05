---
title: Consolidated Audit Report — mko_telepost
date: 2026-07-03
phases_completed: 9/9
validated: true
---

# Consolidated Audit Report — mko_telepost

## Phases Executed

| # | Phase | File | Status |
|---|-------|------|--------|
| 1 | CLI | `01-audit-cli.md` | ✅ Executed + Validated |
| 2 | Config | `02-audit-config.md` | ✅ Executed + Validated |
| 3 | Services | `03-audit-services.md` | ✅ Executed + Validated |
| 4 | Security | `04-audit-security.md` | ✅ Executed + Validated |
| 5 | Integrations | `05-audit-integrations.md` | ✅ Executed + Validated |
| 6 | Data Flow | `06-audit-data-flow.md` | ✅ Executed + Validated |
| 7 | Tests | `07-audit-tests.md` | ✅ Executed + Validated |
| 8 | Quality | `08-audit-quality.md` | ✅ Executed + Validated |
| 9 | Structural Quality | `09-structural-quality.md` | ✅ Executed + Validated |

---

## Findings by Severity

| Severity | Count |
|----------|-------|
| **CRITICAL** | 1 |
| **HIGH** | 7 |
| **MEDIUM** | 18 |
| **LOW** | 15 |
| **Total** | **41** |

---

## Validation Summary

- **Findings submitted:** 45 (across all 9 phases)
- **Validated (unchanged):** 39
- **Reclassified:** 0 (~~CFG-002~~ ~~DONE~~ — removed from audit)
- **Merged:** 2 (DF-002 → SRV-003, QLT-003 → SRV-002)
- **Rejected:** 0
- **Cross-phase findings surfaced by validators:** 2 (SEC-X01, V-DF-001)

---

## CRITICAL Findings

### SEC-001 — Credential leak via `logger.exception()` in `app.py:116`
- **Type:** SECURITY
- **Affected:** `app.py`, `log_config.yaml`
- **Issue:** `api_hash` and `phone_or_token` plaintext leak into stderr/logs via Pydantic `ValidationError` traceback (input_value embedded). Currently goes to stderr via `lastResort` handler.
- **Validator correction:** Currently leaks to stderr, not rotating log file (since logging is never configured). Would escalate to persistent disk if CLI-001 is fixed before SEC-001.
- **Recommendation:** Sanitize `ValidationError` before logging. Fix must land before or atomically with CLI-001.

---

## HIGH Findings

### CLI-001 — Logging never configured at CLI startup (HIGH/mandatory)
- **Type:** SPEC-DEVIATION
- **Issue:** `logger.exception()` calls fall through to `lastResort` handler dumping tracebacks to stderr. `load_logging_config()` is dead code.
- **Fix:** Call `load_logging_config()` at CLI startup.

### CFG-001 — Relative `--config` path resolved against user_dir, not CWD (HIGH/mandatory)
- **Type:** RUNTIME-ERROR
- **Issue:** Typer `exists=True` checks CWD, but `TelepostConfigReader._resolve_path` routes through `PathResolver(APP_PATHS.user_dir)`, so relative paths fail.
- **Fix:** Resolve against CWD before passing to PathResolver.

### SRV-001 — `max_photos` limit exceeds Telegram's 10-per-album cap (HIGH/mandatory)
- **Type:** SPEC-DEVIATION
- **Issue:** `le=20` validation accepts 11–20, then silent post loss via catch-all `except`.
- **Fix:** Reduce max to 10, update spec. Atomic change across 7 locations.

### INT-001 — `async with client:` skips configured credentials (HIGH/mandatory)
- **Type:** SPEC-DEVIATION
- **Issue:** Telethon `__aenter__` calls `self.start()` with no args, then explicit `client.start(**creds)` never reached on fresh session.
- **Fix:** Drop `async with client:`, use direct `await client.start(**creds)`. Coordinate with SEC-003/SRV-005/SRV-004 (same block).

### TST-001 — GSheets test non-hermetic — can make real API calls (HIGH/mandatory)
- **Type:** RUNTIME-ERROR
- **Affected:** `test_get_sheet_data_returns_empty_when_service_not_initialized`
- **Issue:** Can hang (browser OAuth flow) or make real Google Sheets calls when credentials exist in user config dir.
- **Fix:** Isolate with proper mocking.

### STR-002 — `_send_posts()` nesting depth 6/7 — pyramid of doom (HIGH/advisory)
- **Type:** BEST-PRACTICE
- **Issue:** Deeply nested control flow in `core/telegram_service.py`.
- **Fix:** Extract inner logic into focused helper functions. Sequence after STR-004 → STR-003.

### STR-005 — `resize_image()` nesting depth 5/7, 4 returns, cleanup interleaved (HIGH/advisory)
- **Type:** BEST-PRACTICE
- **Issue:** Complex method with cleanup interleaved with happy path.
- **Fix:** Extract cleanup to finally block. Coordinate with QLT-009.

---

## MEDIUM Findings

| ID | Phase | Description |
|----|-------|-------------|
| CLI-002 | CLI | Core modules reference `mko init` but registered command is `mko-telepost init` (5 locations, not 2) |
| CFG-003 | Config | `HumanizationConfig` accepts `base_delay_seconds > max_delay_seconds` — validator gap |
| CFG-004 | Config | `TelegramPoster` stores raw `model_dump()` dict as instance state (violates SPEC §4.2) |
| SRV-002 | Services | `ImageCache.get_cache_path` dead code + extension logic diverges from `resize_image` |
| SRV-003 | Services | `Task.txt` typed `str` from `Any` cell values — type contract broken |
| SRV-004 | Services | `run()` labels every failure as "Telegram authentication failed" |
| SEC-002 | Security | Orphaned `test.session` at repo root with world-readable perms |
| SEC-003 | Security | `.session` file restrictive perms applied only on success path |
| DF-001 | Data Flow | Directory photo entries with non-JPEG formats silently lose entire post |
| TST-002 | Tests | GSheets credential happy paths untested (`_try_refresh_token`, `_save_token`) |
| QLT-001 | Quality | `Any` used across 5 production modules |
| QLT-002 | Quality | Post data flows as untyped `list[list[Any]]` |
| QLT-004 | Quality | `_coordinate_posting` return value dead; undeclared instance attrs |
| QLT-009 | Quality | `resize_image` outer `except Exception` silently swallows `Image.open` errors |
| STR-001 | Structure | `post_processor.py` starts with UTF-8 BOM → radon aborts |
| STR-003 | Structure | `_try_send_message()` 77 lines, 4 returns, 4 except branches |
| STR-004 | Structure | `telegram_service.py` 327 lines (exceeds 300) |
| STR-006 | Structure | `_load_and_validate_config()` complexity |

---

## LOW Findings

| ID | Phase | Description |
|----|-------|-------------|
| CLI-003 | CLI | `config` command Rich table truncates Path column |
| CFG-005 | Config | Template ships `api_id: 12345` with no placeholder guard |
| CFG-006 | Config | `log_config.yaml` targets non-existent `teleposter` logger |
| CFG-007 | Config | `HumanizationConfig` numeric bounds asymmetry |
| SRV-005 | Services | `.session` perms hardened only after posting success |
| SEC-004 | Security | Glob before containment check in `_extract_photo_paths` |
| INT-002 | Integrations | Dead `or` fallbacks + false docstring in `get_sheet_data` |
| TST-003 | Tests | Brittle wall-clock assertion in `test_resize_image_cache_hit` |
| TST-004 | Tests | CLI wiring tests assert mock invocations only |
| TST-005 | Tests | `ruff format` not in lint gate; mixed indentation in test file |
| QLT-005 | Quality | Dead `or` fallbacks + false docstring in `get_sheet_data` |
| QLT-006 | Quality | `TelegramPoster` stores client config as raw `dict[str, Any]` |
| QLT-007 | Quality | `fix_readme_script.py` + `temp_findings.txt` tracked in repo root |
| QLT-008 | Quality | `# type: ignore[arg-type]` masks untyped post structure |
| STR-007 | Structure | `_try_load_token()` 4 return points |

---

## Cross-Phase Dependencies Identified by Validators

1. **SEC-001 ↔ CLI-001** (CRITICAL ordering): Fixing CLI-001 (logging init) before SEC-001 escalates credential leak from transient stderr to persistent log file. **SEC-001 must land before or atomically with CLI-001.**

2. **SEC-003 ↔ SRV-005 ↔ INT-001** (four-way conflict): All rewrite `telegram_service.py:305-315`. Must be coordinated as one change.

3. **CFG-006 ↔ CLI-001**: Dead `teleposter` logger config has zero impact today because logging never loads. Fix together.

4. **DF-001 ↔ SEC-004**: Both modify `_extract_photo_paths`. Sequence: SEC-004 before DF-001.

5. **QLT-002 → QLT-008**: Implement `Post` model first, then delete `type: ignore`. mypy will auto-flag the unused suppression.

6. **STR-004 → STR-003 → STR-002**: Overlap on same functions. Must be sequenced.

7. **STR-005 ↔ QLT-009**: Both touch `resize_image` — implement in one pass.

---

## Duplicates Merged During Validation

| Source | Merged Into | Reason |
|--------|-------------|--------|
| DF-002 (Phase 06) | SRV-003 (Phase 03) | Same root cause: `Task.txt` typed `str` from `Any` cell values |
| QLT-003 (Phase 08) | SRV-002 (Phase 03) | Same dead-code finding: `ImageCache.get_cache_path` |

---

## Reclassifications

| Finding | Original | Reclassified To | Reason |
|---------|----------|-----------------|--------|
| ~~CFG-002~~ ~~REMOVED~~ | ~~SPEC-DEVIATION~~ | ~~DOC-UPDATE (resolved)~~ | Code behavior is correct (Pydantic v2 `model_validate` always runs after-validators); only docstrings lie |

---

## Rollout Safety Notes

- **Mandatory fix ordering:** SEC-001 → CLI-001 (credential leak escalation risk)
- **Four-way block merge required:** INT-001 + SEC-003 + SRV-005 + SRV-004 (same `telegram_service.py` block)
- **No circular dependencies detected**
- **All testability-impacting fixes** (INT-001, TST-001) include calls for new integration tests
- **8 HIGH severity findings** (1 CRITICAL + 7 HIGH) require priority treatment before the 18 MEDIUM + 15 LOW advisory items

---

## Audit Artifacts

| Artifact | Path |
|----------|------|
| Phase 01 CLI findings | `.ai/audit/01-cli/findings.md` |
| Phase 02 Config findings | `.ai/audit/02-config/findings.md` |
| Phase 03 Services findings | `.ai/audit/03-services/findings.md` |
| Phase 04 Security findings | `.ai/audit/04-security/findings.md` |
| Phase 05 Integrations findings | `.ai/audit/05-integrations/findings.md` |
| Phase 06 Data Flow findings | `.ai/audit/06-data-flow/findings.md` |
| Phase 07 Tests findings | `.ai/audit/07-tests/findings.md` |
| Phase 08 Quality findings | `.ai/audit/08-quality/findings.md` |
| Phase 09 Structural Quality findings | `.ai/audit/09-structural-quality/findings.md` |
| Phase 01 validated | `.ai/audit/99-validation/01-cli-validated-findings.md` |
| Phase 02 validated | `.ai/audit/99-validation/02-config-validated-findings.md` |
| Phase 03 validated | `.ai/audit/99-validation/03-services-validated-findings.md` |
| Phase 04 validated | `.ai/audit/99-validation/04-security-validated-findings.md` |
| Phase 05 validated | `.ai/audit/99-validation/05-integrations-validated-findings.md` |
| Phase 06 validated | `.ai/audit/99-validation/06-data-flow-validated-findings.md` |
| Phase 07 validated | `.ai/audit/99-validation/07-tests-validated-findings.md` |
| Phase 08 validated | `.ai/audit/99-validation/08-quality-validated-findings.md` |
| Phase 09 validated | `.ai/audit/99-validation/09-structural-quality-validated-findings.md` |
