# Phase 09 Audit Findings — Structural Code Quality

**Executor:** auditor
**Template:** .kilo/commands/audit/phases/09-structural-quality.md
**Status:** complete
**Validated:** no

---

## Runtime Verification Summary

- **R1 — Radon CC:** `uv run radon cc src/ -a -nc` → 103 blocks analyzed, **average complexity 3.17 (rank A)**. No function reaches rank C (≥11). Highest individual scores: B (8) `_fetch_messages`, `_group_messages_by_album`, `process_messages`, `create_client`, `PatternParser._tokenize`, `matcher.ast_to_regex`/`patterns_for_node`/`evaluate_query`, `channels.apply_defaults_to_channels`, `TelepostConfigReader.load_logging_config`, `ClientConfig.validate_session`. None ≥ 11.
- **R2 — Radon MI:** `uv run radon mi src/ -s` → **all 19 source files rank A** (52.68–100.00). No file rank B or C.
- **R3 — Function length:** Largest function `_fetch_messages` (`monitor_forward.py:197-243`) ≈ 47 lines (incl. docstring), under the 50-line limit. No function exceeds 50 lines.
- **R4 — Nesting depth:** Manual review of every function in files >130 lines. Deepest measured nesting = 3 (`_group_messages_by_album`, `load_logging_config`, `apply_defaults_to_channels`, `load_state`). No function exceeds depth 3.
- **R5 — Control flow:** No `for...else` usage found (grep). No `if/else` arrow-code pyramids. No god modules (max file 264 lines < 300).

---

## Findings

### STR-001: `forward_to_users` exceeds recommended parameter count

| Field | Value |
|-------|-------|
| **ID** | STR-001 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` (line 123) |
| **Classification** | advisory |

**Description:** `forward_to_users(msg, msg_text, msg_media, task, client, settings)` takes **6 parameters**, exceeding the ≤5-parameters guideline. `msg_text` is fully derivable from `msg` (`"\n".join(...)` is already computed downstream in `process_messages`), so the function receives a value it could obtain itself, increasing coupling between caller and callee.

**Evidence:**
```
src/mko_telebot/monitor_forward.py:123
async def forward_to_users(
    msg: Message, msg_text: str | None, msg_media: list[Any],
    task: Task, client: TelegramClient, settings: TelepostSettings,
) -> None:
```
`msg_text` is built in `process_messages` (line 182) as `"\n".join(content.get("text", []))` and passed through solely for caption construction in `_build_caption`.

**Recommendation:** Derive `msg_text` inside `forward_to_users` from `msg` (the same grouping logic used in `process_messages`), dropping the parameter. This reduces the signature to 5 parameters and removes redundant data passing. Effort: trivial. Priority: recommended.

---

### STR-002: `_send_with_retry` exceeds recommended parameter count

| Field | Value |
|-------|-------|
| **ID** | STR-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/monitor_forward.py` (line 89) |
| **Classification** | advisory |

**Description:** `_send_with_retry(client, target, caption, msg_media, max_tries, channel_name)` takes **6 parameters**, exceeding the ≤5-parameters guideline. `channel_name` is used only for log messages (lines 101, 107-109, 114-117). It is not essential to the retry logic and could be retrieved from the `target` entity context or dropped from the log line.

**Evidence:**
```
src/mko_telebot/monitor_forward.py:89
async def _send_with_retry(
    client: TelegramClient, target: Entity, caption: str,
    msg_media: list[Any] | None, max_tries: int, channel_name: str,
) -> bool:
```
`channel_name` is referenced only in `logger.info`/`logger.warning` calls; the function's behavior (backoff, retry, return bool) is independent of it.

**Recommendation:** Drop `channel_name` and rely on `target` identity (`getattr(target, "id", target)`, already used in the log lines) for context, reducing the signature to 5 parameters. If channel context is needed for diagnostics, derive it from `task` passed once at a higher level rather than per-call. Effort: trivial. Priority: recommended.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 2 |

## Mandatory Fixes

None.

## Advisory Recommendations

- **STR-001** — Reduce `forward_to_users` parameter count (derive `msg_text` internally).
- **STR-002** — Reduce `_send_with_retry` parameter count (drop `channel_name`).

## Doc Updates Needed

None.
