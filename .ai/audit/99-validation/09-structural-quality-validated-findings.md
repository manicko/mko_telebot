# Phase 09 Validation — Structural Code Quality

**Validator:** validator
**Source:** `.ai/audit/09-structural-quality/findings.md`
**Mode:** `problems_only = TRUE` — this report lists only discrepancies, evidence issues, and concerns detected during validation. Findings not mentioned here were validated as-is against the implementation and require no correction.
**Scope:** `src/mko_telepost/**/*.py`

**Validation method:** every metric (BOM presence, line counts, nesting depth, return counts, except-branch counts, radon output, ruff output) was re-derived directly from the source via `ast` + `radon` + `ruff`. All 7 findings were re-checked; 5 carried evidence inaccuracies worth recording.

---

## Evidence-Quality Problems

### STR-002 — excerpt misrepresents nesting structure

| Field | Value |
|-------|-------|
| **Finding** | STR-002 |
| **Severity of problem** | LOW (finding stands) |
| **Claim** | Excerpt shows the micro-break `if chat_config:` at depth 4 and `if should_micro_break:` at depth 5, with `asyncio.sleep` at depth 6. |
| **Verified reality** | In the actual `_send_posts` (lines 137-175) there are **two separate** `if chat_config:` blocks: one for the pre-send delay (depth 4) and one inside `if send_success:` for the micro-break (depth 5). The micro-break `if should_micro_break:` is therefore at depth 6 and the `await asyncio.sleep(micro_delay)` at depth 7 by statement-level counting. |
| **AST re-derivation** | `max_depth=6` (control-flow-node counting, function body = 0). Matches the finding's headline figure; the excerpt is just simplified. |
| **Decision** | Finding VALIDATED unchanged — deep nesting (>4) confirmed. **Fix the evidence excerpt** so it shows the real second `if chat_config:` inside `if send_success:`, otherwise a maintainer executing the recommendation literally may miss one nesting source. |

### STR-003 — wrong except-branch count

| Field | Value |
|-------|-------|
| **Finding** | STR-003 |
| **Severity of problem** | LOW (finding stands) |
| **Claim** | Title and description state "**3 except branches**". |
| **Verified reality** | `_try_send_message` (lines 177-273) has **4** `except` clauses: (1) `ForbiddenError/ChatAdminRequired/ChannelPrivate`, (2) `FloodWait/SlowMode`, (3) `WorkerBusy/Server/RpcFail/TimedOut/ConnectionError`, (4) bare `Exception`. AST confirms `except branches: 4`. |
| **Other claims** | 77 non-blank/comment lines — **confirmed exact**. 4 return points — **confirmed exact** (lines 225, 236, 267, 273). Radon rank B — plausible. |
| **Decision** | Finding VALIDATED — **correct "3 except branches" to "4 except branches"** in the title and description. The maintainability argument only gets stronger (one more error path than claimed). |

### STR-005 — depth figure under-counts

| Field | Value |
|-------|-------|
| **Finding** | STR-005 |
| **Severity of problem** | LOW (finding stands) |
| **Claim** | `resize_image` has nesting depth **5** and **4 return points**. |
| **Verified reality** | AST re-derivation reports `max_depth=7` (control-flow-node counting, function body = 0) — i.e. the deepest statement is at depth 7, not 5. The discrepancy is a depth-counting convention difference, not a factual error: the finding likely counts only `try`/`if` openers without crediting the nested `with`/`except` levels. Either way, depth exceeds the >4 threshold. 4 return points — **confirmed exact**. |
| **Decision** | Finding VALIDATED — depth violation confirmed (and is actually worse than stated). **Update the depth figure from 5 to 7** and replace the claim wording to include the explicit nesting chain (`try > with > try > except > if > try > unlink`). This single change subsumes the "note convention" alternative � the chain itself documents the counting convention, making the figure reproducible, and reveals the problem is more severe than originally reported. |

### STR-006 — line range is slightly off

| Field | Value |
|-------|-------|
| **Finding** | STR-006 |
| **Severity of problem** | LOW (finding stands) |
| **Claim** | `_load_and_validate_config` spans lines **63-118**. |
| **Verified reality** | AST `end_lineno` is **120** (lines 63-120). 58 total lines, 47 non-blank/comment. |
| **Other claims** | `depth=4` — **confirmed exact**. `returns=4` — **confirmed exact**. |
| **Decision** | Finding VALIDATED — **correct the line range to 63-120**. |

### STR-001 — confirmed; classification note

| Field | Value |
|-------|-------|
| **Finding** | STR-001 |
| **Severity of problem** | LOW (finding stands) |
| **Verified reality** | BOM `b'\xef\xbb\xbf'` confirmed at `post_processor.py` byte 0. `radon cc` and `radon mi` both emit `ERROR: invalid non-printable character U+FEFF`. Only this single file is affected (repo-wide scan: 1 BOM file). `uv run ruff check` passes on this file, so ruff is **not** a guard for BOM today. No `pre-commit-config.yaml` and no BOM rule exists in `[tool.ruff.lint]`. |
| **Decision** | Finding VALIDATED — the defect and the missing-CI-guard claim are both real. **Classification note:** `SPEC-DEVIATION` is defensible (radon is in the dev dependency group and the project's own "After every edit, run uv run ruff check" rule presumes toolable source), but no SPEC line explicitly mandates UTF-8-without-BOM. If a stricter reading is desired, `BEST-PRACTICE` would also fit. Recommend keeping `SPEC-DEVIATION` and adding an explicit "no BOM" rule to the spec so the classification is grounded. |

### STR-004 — confirmed; dependency-chain note

| Field | Value |
|-------|-------|
| **Finding** | STR-004 |
| **Severity of problem** | LOW (finding stands) |
| **Verified reality** | `telegram_service.py` = 433 total lines / **327 non-blank** lines — **confirmed exact**. Largest source file in the project (next is `app.py` at 249). Radon MI 52.95 is the lowest in the project. |
| **Decision** | Finding VALIDATED unchanged. See dependency-chain note below — STR-004 is the umbrella change; STR-002 and STR-003 must be sequenced after it, not before. |

---

## Cross-Finding & Rollout Concerns

These concerns were **not** surfaced in the source findings and are added by validation.

### CFC-001 — STR-002, STR-003, STR-004 form an ordered dependency chain

All three findings target `core/telegram_service.py` and overlap on the same two functions (`_send_posts`, `_try_send_message`). The source findings treat them as independent; in practice the recommendations must be sequenced.

- **STR-004** (extract `telegram_sender.py`) must be done **first**. It relocates `_try_send_message` out of the orchestrator.
- **STR-003** (split `_try_send_message` into `_build_send_call` + `_handle_send_exception`) applies **inside** the newly extracted module from STR-004. Doing STR-003 first would just re-split a function that STR-004 then moves again — wasted churn.
- **STR-002** (flatten `_send_posts` via `_process_post` helper) applies to the **orchestrator** remaining after STR-004. Its `send_success = await self._try_send_message(...)` call site must point at the extracted sender, so STR-002 also depends on STR-004.

**Recommended execution order:** STR-001 (trivial, isolated) → STR-004 → STR-003 → STR-002. STR-005, STR-006, STR-007 are independent of this chain and can run in any order.

### CFC-002 — STR-004 extraction has a hidden dependency surface

The source finding proposes a `telegram_sender.py` "taking `client` + `settings.telethon.max_retries`". `_try_send_message` actually also depends on `post.topic_id` (InputReplyToMessage construction) and `post.photos` / `post.txt` — fine, those come via the `Task` arg — but it does **not** touch `self.delay_engine`, `self._chat_configs`, or `self.settings` beyond `max_retries`. That makes the extraction clean. However, `_send_posts` (STR-002's target) **does** use `self._chat_configs`, `self.delay_engine`, `self._last_success_count` / `self._last_failed_count` (set only in the `except asyncio.CancelledError` branch — see QLT-005 in Phase 08). The orchestrator therefore retains that coupling; the sender extraction itself does not pull those dependencies along. This is a positive finding but the source recommendation should state it explicitly so the implementer does not over-extract.

### CFC-003 — STR-005 and QLT-009 (Phase 08) touch the same function

`ImageCache.resize_image` is the target of **both** STR-005 (structural: extract `_save_thumbnail` / `_safe_unlink`) and QLT-009 from Phase 08 (quality: log the exception in the outer `except Exception` instead of silently returning `image_path`). These are **complementary, not conflicting** — QLT-009 was validated as retained in Phase 08. The structural refactor in STR-005 naturally exposes the outer `except` for the logging fix in QLT-009, so both should be implemented in the same pass to avoid double-touching the function.

### CFC-004 — no cross-phase conflicts detected

Phase 08 (quality) and Phase 03 (services) validated reports agree with the structural assessment of `telegram_service.py` and `image_cache.py`. No finding in another phase claims these functions are clean/healthy, so there is no conflict with STR-002…STR-005.

---

## Summary

| Problem | Finding | Severity | Action |
|---------|---------|----------|--------|
| Excerpt misrepresents nesting structure | STR-002 | LOW | Fix evidence excerpt to show the real second `if chat_config:` inside `if send_success:` |
| Wrong except-branch count (says 3, actual 4) | STR-003 | LOW | Correct title/description to "4 except branches" |
| Depth figure under-counts (says 5, AST reports 7) | STR-005 | LOW | Update depth figure to 7 with explicit nesting chain (try > with > try > except > if > try > unlink) |
| Line range off (says 63-118, actual 63-120) | STR-006 | LOW | Correct line range to 63-120 |
| BOM classification borderline | STR-001 | LOW | Keep SPEC-DEVIATION; add explicit "no BOM" rule to spec to ground it |
| Hidden dependency chain STR-002/003/004 | STR-002, STR-003, STR-004 | MEDIUM | Sequence as STR-004 → STR-003 → STR-002; document in rollout plan |
| Hidden coupling of _send_posts to self state | STR-004 | LOW | State explicitly that sender extraction does not pull delay_engine/_chat_configs |
| Same function touched by STR-005 + QLT-009 | STR-005, QLT-009 | LOW | Implement both in one pass |

## Required Fixes (to the audit findings, not to source code)

1. **STR-003**: change "3 except branches" → "4 except branches" in the title and description.
2. **STR-005**: update the depth figure from 5 to 7 and include the explicit nesting chain (`try > with > try > except > if > try > unlink`) for reproducibility.
3. **STR-006**: correct the line range from `63-118` to `63-120`.
4. **STR-002**: fix the evidence excerpt to reflect the real two-`if chat_config` structure.
5. **STR-004**: state explicitly which `self.*` dependencies stay in the orchestrator vs. move to the sender.

## Advisory Recommendations

- Add a BOM-rejecting CI guard (ruff rule or pre-commit) as part of STR-001's fix; ruff does not catch BOM by default today.
- Record the STR-004 → STR-003 → STR-002 execution order in the rollout plan.

## Rejected Findings

None. All 7 source findings are retained; only evidence wording is corrected.

## Reclassified / Merged Findings

None. No findings were reclassified or merged. STR-005 and QLT-009 (Phase 08) are noted as complementary cross-phase touchers but remain separate findings addressing distinct concerns (structure vs. error logging).




