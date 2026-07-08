---
name: 05-integrations-validated-findings
description: Validated External Integrations Audit Findings
agent: validator
status: complete
validated: yes
problems-only: true
---

# Phase 05 Validated Findings — External Integrations

**Validator:** validator  
**Source:** `.ai/audit/05-integrations/findings.md`  
**Status:** complete  
**Validated:** yes

---

## Findings

### INT-001: Audit phase specification references non-existent Google Sheets integration (GSheetsReader)

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | CRITICAL |
| **Type** | DOC-UPDATE |
| **Affected Modules** | `.kilo/commands/audit/phases/05-audit-integrations.md` |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** Reclassified from SPEC-DEVIATION to DOC-UPDATE. The codebase is a Telegram-only channel monitor (README: "Monitors Telegram channels for new messages matching your keywords") — it has never had Google Sheets integration. The audit phase specification documents a non-existent integration. The code is fine; the specification is wrong.
> - **See also:** SRV-003 (Phase 03 — same root cause: audit phase specs copied from another project)

**Description:** The audit phase specification explicitly audits Google Sheets integration with checks for `GSheetsReader` class, OAuth2 flow, `credentials_file`/`token_file` path resolution, and `GoogleSheetsConfig` model. However, no Google Sheets integration exists in the codebase. The project is a Telegram channel monitor (as stated in README: "Monitors Telegram channels for new messages matching your keywords"), not a Google Sheets publishing tool. Grep search for `gspread|google|sheet` returns no results. The audit references services that were copied from another project or are planned but never implemented.

**Evidence:**
- `.kilo/commands/audit/phases/05-audit-integrations.md` lines 26, 65-74 specify auditing `GSheetsReader`
- `.kilo/commands/audit/phases/05-audit-integrations.md` line 104 references `GoogleSheetsConfig` model
- No `gspread`, `google.auth`, or `oauth2` imports anywhere in `src/`
- No `GSheetsReader` class or Google Sheets API calls in the codebase
- README describes "Telegram classified monitor" feature, not Google Sheets publishing
- Same pattern affects Phase 03 (SRV-003), Phase 04, Phase 06, and Phase 07 audit specs — all reference non-existent Google Sheets components

**Recommendation:** Update the audit phase specification to remove Google Sheets integration checks. The actual integration is Telegram-only with `TelegramClient` for monitoring and forwarding. Effort: trivial (documentation update).

---

### INT-002: Secret values properly used with SecretStr but could be logged in error contexts

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/telethon.py` |
| **Classification** | advisory |

> **Validation Note:**
> - **Action:** validated (unchanged)

**Description:** Credentials are properly stored using `SecretStr` type and validated against placeholder values. However, the `session` field is a plain string that could potentially contain sensitive path components. While the current implementation in `monitor.py` line 43 uses `session_path.name` to extract only the filename (mitigating path traversal), the field lacks explicit validation. Additionally, `phone_or_token.get_secret_value()` at lines 62 and 64 in monitor.py could theoretically leak in stack traces if `client.start()` raises an unhandled exception before the try block completes.

**Evidence:**
- `telethon.py` line 28: `session` field has no validation for placeholder/sensitive values
- `monitor.py` line 38: `session` is accessed without using SecretStr protection
- `monitor.py` lines 62, 64: `.get_secret_value()` called inside try block, protected but could appear in tracebacks on unexpected errors

**Recommendation:** Consider validating the session field against placeholder values similar to other credential fields. Ensure error handlers don't expose secrets in logs. Effort: trivial.

---

### INT-003: Telegram error handling has dead code path and FloodWaitError doesn't retry

| Field | Value |
|-------|-------|
| **ID** | INT-003 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/monitor.py` |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** validated (unchanged)

**Validated by code inspection:** Confirmed at `monitor.py` lines 152-172.

**Description:** The `forward_to_users` function catches `TelegramServiceError` at line 169, but Telethon `send_message` and `send_file` operations raise Telethon-native exceptions (like `RPCError`), not the custom `TelegramServiceError`. This exception handler is essentially dead code. Additionally, when `FloodWaitError` is caught (line 164-168), the code waits but does NOT retry sending the message — the message is simply lost. The audit specification requires "FloodWaitError triggers a wait-and-retry with the specified duration plus jitter" but the current implementation only waits without retrying.

**Evidence:**
- `monitor.py` line 15: Only `FloodWaitError` is imported from `telethon.errors`
- `monitor.py` line 169: `except TelegramServiceError as e:` catches an exception type that Telethon never raises directly at this boundary
- `monitor.py` lines 164-168: Flood wait triggers sleep but then proceeds without sending the message
- `task.py` lines 70, 82: Catch generic `Exception` and wrap as `TelegramServiceError` for entity resolution (correct usage)
- No `RPCError`, `AuthKeyError`, or other Telethon exceptions are caught at the send boundary

**Recommendation:** Import additional Telethon exceptions (`RPCError`) and catch them appropriately. Implement proper retry logic for FloodWaitError that re-attempts the send after waiting. Effort: medium.

---

### INT-004: max_retries field defined in config but never used in Telegram posting logic

| Field | Value |
|-------|-------|
| **ID** | INT-004 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/telethon.py`, `src/mko_telebot/monitor.py` |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** validated (unchanged)
> - **See also:** DF-004 (Phase 06 — same finding, duplicate)

**Description:** The `TelethonConfig.max_retries` field (lines 85-87 in telethon.py) is configured for retry attempts when posting fails, but the `forward_to_users` function in `monitor.py` has no retry logic. It attempts to send once and logs errors without retrying. The audit specification requires "Flood control is handled" and "Other transient errors are retried" but the implementation only handles `FloodWaitError` with a sleep, and lacks any retry mechanism for other failures.

**Evidence:**
- `telethon.py` line 85-87: `max_retries: int = Field(default=5, ge=1, le=20, ...)` is defined
- `monitor.py` lines 152-172: `forward_to_users` catches `FloodWaitError` once and logs, no retry loop
- `monitor.py` line 164-168: Flood wait triggers sleep but then continues without retry
- No loop or counter uses `settings.telethon.max_retries`
- Config documentation at `docs/11-guides/configuration.md` lines 165, 186 documents `max_retries`

**Recommendation:** Implement retry logic in `forward_to_users` that catches transient errors, uses `max_retries` from config, and applies exponential backoff with jitter. Effort: medium.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 3 | INT-002, INT-003, INT-004 |
| Reclassified | 1 | INT-001 (SPEC-DEVIATION → DOC-UPDATE) |
| Merged | 0 | — |
| Rejected | 0 | — |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| INT-001 | SPEC-DEVIATION | DOC-UPDATE | Code is correct — no Google Sheets integration exists, was never planned per README. Only the audit phase specification is wrong. Same root cause as SRV-003. |

### Rejected Findings

No findings were rejected.

### Merged Findings

No findings were merged within this phase. Note: INT-004 (max_retries unused) overlaps with DF-004 from Phase 06 — same root cause.

---

## Cross-Phase Concerns

| Issue | Phase(s) | Details |
|-------|----------|---------|
| Non-existent Google Sheets integration referenced in audit specs | 02, 03, 04, 05, 06, 07 | The audit phase specifications for Phases 02–07 all contain references to `GSheetsReader`, `GoogleSheetsConfig`, spreadsheet IDs, and Google OAuth2 flows that do not exist in the codebase. This is a systemic copy-paste issue across all audit phase documents. |
| INT-004 / DF-004 duplicate | 05, 06 | Both phases independently discovered the `max_retries` unused field. INT-004 (Phase 05) and DF-004 (Phase 06) describe the same issue. DF-004 should be merged into INT-004 as it provides the same evidence. |

---

## Rollout Analysis

| Concern | Detail |
|---------|--------|
| INT-003 and INT-004 are related | Fixing INT-004 (retry logic with max_retries) naturally addresses the retry gap in INT-003. Both should be implemented together. |
| No circular dependencies | Findings are independent; no rollout ordering constraints. |
| Low risk | All findings are in `monitor.py` (send boundary) — changes are well-scoped and easy to roll back. |

---

## Advisory Recommendations

- Fix INT-003 and INT-004 together in a single change — retry logic for `forward_to_users` addresses both the missing retry on `FloodWaitError` and the unused `max_retries` field.
- Batch all audit phase doc fixes (Phases 02–07) to remove Google Sheets references in a single PR.
