---
name: 03-services-validated-findings
description: Validated Service Layer & Business Logic Audit Findings
agent: validator
status: complete
---

# Phase 03 Validated Findings — Service Layer & Business Logic

**Validator:** validator
**Source:** `.ai/audit/03-services/findings.md`
**Status:** complete

---

## Findings

### SRV-001: Task class mixes data, entity resolution, and state persistence

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | MEDIUM *(downgraded from HIGH)* |
| **Type** | BEST-PRACTICE *(reclassified from SPEC-DEVIATION)* |
| **Affected Modules** | src/mko_telebot/core/task.py |
| **Classification** | advisory *(downgraded from mandatory)* |

> **Validation Note:**
> - **Action:** Reclassified + severity downgraded
> - **Detail:** The finding correctly identifies that `Task` contains methods that mix data holding, Telegram API calls, and filesystem I/O. However:
>   1. No project specification (SPEC.md does not exist) mandates that `Task` be a pure dataclass. The audit spec checklist (03-audit-services.md line 129) is an aspirational guideline, not a binding requirement.
>   2. For this project's scale (~15 source files, ~160 lines in task.py), extracting a `TelegramResolver` and `StateManager` introduces unnecessary indirection. The actual methods (`resolve_targets_entities`, `resolve_channel_entity`, `resolve_state_file`, `load_state`, `save_state`) are each ≤20 lines and directly coupled to their call sites in `monitor.py`.
>   3. The recommendation's "large effort — architectural restructuring" is overstated. A pragmatic fix (move entity resolution to module-level functions in `monitor.py`) would be small effort.
>   4. Per validation rules: splitting small modules is high ROI, but introducing full service abstractions (`TelegramResolver`, `StateManager`) for ~50 lines of logic adds indirection without proportionate benefit.
> - **Reclassified to:** BEST-PRACTICE (improvement opportunity, not spec violation)
> - **Severity lowered to:** MEDIUM (code organization issue, not correctness bug)

**Corrected Description:** The `Task` class in `task.py` holds configuration data AND performs Telegram entity resolution AND manages state persistence. This mixes three concerns in one class. However, for this project's scale, the coupling is manageable — the methods are short and their call sites are clearly visible in `monitor.py`. A full architectural split would be overengineering; a lighter refactor (moving entity resolution functions into `monitor.py`) would be sufficient if pursued.

**Verified Evidence:**
- `task.py` lines 61-76: `resolve_targets_entities` calls `client.get_entity()` — couples Task to Telethon client
- `task.py` lines 78-88: `resolve_channel_entity` calls `client.get_entity()` — same coupling
- `task.py` lines 90-104: `resolve_state_file` performs filesystem path I/O
- `task.py` lines 125-158: `load_state` and `save_state` perform async file I/O via `aiofiles`
- `task.py` lines 44-59: `__init__` holds configuration data (data container role)
- All methods are called directly from `monitor.py` `main_loop` (lines 314-318) and `process_and_reschedule` (line 288)

**Corrected Recommendation:** If pursued, move entity resolution methods (`resolve_targets_entities`, `resolve_channel_entity`) to module-level async functions in `monitor.py` or a small `resolver.py` module. The state persistence methods are less critical to move — they depend only on `state_file` and `last_msg_id` attributes and could stay on Task or move to a utility module. Effort: small to medium (not "large architectural restructuring").

---

### SRV-002: Missing return type hints on public methods

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | src/mko_telebot/core/task.py, src/mko_telebot/monitor.py |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** Validated with dependency note
> - **Detail:** The finding is technically correct. However, one of the three cited functions (`launcher()` in `monitor.py`) is identified as dead code in cross-phase finding CLI-002 (reclassified BEST-PRACTICE) and slated for removal. The remaining two functions have missing return type hints per project standards. The mandatory classification is appropriate — type hints on public functions is a project rule.
> - **Cross-phase dependency:** SRV-002's reference to `launcher()` is affected by CLI-002 (validated in phase 01). If `launcher()` is removed, that part of this finding becomes moot.

**Corrected Description:** Three public functions/methods lack return type annotations, violating the project rule "Type hints on all public functions" (`AGENTS.md`). Two are genuine; one is dead code.

**Verified Evidence:**
- `task.py` line 90: `def resolve_state_file(self):` — no return type. Returns `None` implicitly.
- `monitor.py` line 72: `def build_message_link(msg):` — no return type (no `self` — function, not method). Returns `str | None`.
- `monitor.py` line 343: `def launcher():` — no return type. Returns `None` implicitly.
  - **Note:** `launcher()` is confirmed dead code per CLI-002. If CLI-002 is executed, this reference becomes irrelevant.

**Recommendation:** Add return type hints:
- `resolve_state_file(self) -> None`
- `build_message_link(msg) -> str | None`  (and add `from __future__ import annotations` if not present — `monitor.py` already has no annotations import; verify with type checker)
- `launcher() -> None` — add only if `launcher()` is retained (see CLI-002: recommended for removal)

Effort: trivial (minutes).

---

### SRV-003: ~~Audit phase references non-existent services~~ [RECLASSIFIED]

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM *(downgraded from HIGH)* |
| **Type** | DOC-UPDATE *(reclassified from SPEC-DEVIATION)* |
| **Affected Modules** | .kilo/commands/audit/phases/03-audit-services.md |
| **Classification** | advisory *(downgraded from mandatory)* |

> **Validation Note:**
> - **Action:** Reclassified
> - **Detail:** The finding's evidence is correct: `TelegramService`, `PostProcessor`, `ImageCache`, `TelegramPoster`, and `GSheetsReader` do not exist in the codebase. No Google Sheets integration (gspread) is present. However, this is a documentation issue, not a code issue:
>   1. Per validation rules: "If code is better than docs → reclassify as `DOC-UPDATE`." The production code is correct — it doesn't need these services because the project is a Telegram channel monitor, not a Google Sheets publisher.
>   2. The SPEC.md does not exist, so there is no spec document claiming these services exist.
>   3. The README accurately describes a Telegram channel monitor — no mention of Google Sheets.
>   4. The audit phase specification (03-audit-services.md) was apparently templated from a different project or an aspirational design. This is a documentation error in the audit phase spec, not a production code deviation.
> - **Reclassified to:** DOC-UPDATE (audit phase spec needs alignment with actual architecture)
> - **Severity lowered to:** MEDIUM (documentation issue, not a code correctness problem)

**Corrected Description:** The audit phase specification `03-audit-services.md` (line 63) lists service classes `TelegramService`, `PostProcessor`, `ImageCache`, `TelegramPoster`, and `GSheetsReader` that do not exist in the codebase. The actual architecture uses module-level functions in `monitor.py` and the `Task` model for Telegram operations. No Google Sheets integration exists or is described in the README. The audit phase spec should be updated to reflect the actual codebase architecture.

**Verified Evidence:**
- Grep for `class (TelegramService|PostProcessor|ImageCache|TelegramPoster|GSheetsReader)` across all `src/` — no matches (only `TelegramServiceError` in `errors.py`)
- Grep for `gspread|google|sheet` across all `src/` — no matches
- README.md describes a Telegram classified monitor with keyword filtering — no Google Sheets mention
- `03-audit-services.md` checklist dimensions reference `ImageCache`, `PostProcessor`, `TelegramPoster`, `GSheetsReader` — none exist
- `docs/SPEC.md` does not exist (no project specification document to cross-reference)

**Recommendation:** Update `03-audit-services.md` to audit the actual services present:
1. Remove or replace the service class list (line 63) with actual module-level service functions in `monitor.py`: `create_client`, `start_client`, `build_message_link`, `build_sender_tag`, `forward_to_users`, `process_messages`, `process_task`, `main_loop`, `run_monitor`
2. Remove audit dimensions 3 (Image Processing), 4 (Post Processing), 5 (Telegram Posting) — these are specific to a Google Sheets publishing workflow that does not exist
3. Keep task model integrity checks (dimension 6) but adjust to the actual `Task` implementation
4. Remove data transformation chain step (discovery stage, step 4) referencing "raw data from Google Sheets"

Effort: small (documentation only).

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 0 | — |
| Reclassified | 2 | SRV-001, SRV-003 |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

None.

### Merged Findings

None.

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| SRV-001 | SPEC-DEVIATION | BEST-PRACTICE | No spec mandates pure-dataclass Task. SRP improvement opportunity, not a spec deviation. Severity downgraded HIGH→MEDIUM, classification mandatory→advisory. |
| SRV-003 | SPEC-DEVIATION | DOC-UPDATE | Code is correct — audit phase spec references non-existent services. Per rules: "If code is better than docs → reclassify as DOC-UPDATE." Severity downgraded HIGH→MEDIUM, classification mandatory→advisory. |

### Cross-Phase Conflicts

| Finding ID | Related Phase | Finding | Issue |
|------------|--------------|---------|-------|
| SRV-002 | Phase 01 (CLI) | CLI-002 | Both findings reference `launcher()` in `monitor.py`. CLI-002 classifies it as dead code (BEST-PRACTICE, slated for removal). SRV-002 cites it for missing type hints. If CLI-002 is executed (launcher removed), the launcher portion of SRV-002 becomes moot. These are not in conflict — they are additive: SRV-002's type hint finding for launcher is contingent on whether launcher is retained. |

### Rollout Safety Issues

None detected. All validated findings concern code quality improvements and documentation updates — no runtime changes that could introduce regressions.