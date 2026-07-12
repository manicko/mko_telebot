---
name: 05-data-flow
status: complete
validated: no
executor: auditor
problems-only: true
---

# Phase 06 Audit — End-to-End Data Flow

## Output Mode

`problems-only: true` — **only problems, bugs, and deviations are documented.**

- **Do NOT** write sections that say "X is correct" or "no issues found in Y".
- **Do NOT** include checklist rows where the check passes — omit them entirely.
- If a dimension has zero findings after investigation, **omit the dimension entirely**.
- Every finding must be actionable: it describes a real problem, its evidence (code/logs/output), and its impact.

---

## Discovery Stage

Before performing audit checks, trace the complete data flow:

1. **Full Pipeline Mapping** — Trace the entire path: `CLI command` → `config loading` → `Telegram client auth` → `per-channel message fetching` → `keyword matching` → `message forwarding`.
2. **Config Propagation Trace** — For each config section, trace exactly how it flows from YAML → Pydantic model → function parameter. Identify every hop.
3. **Message Lifecycle** — Pick a single message and trace it from the Telegram channel to the forwarded message. Document every transformation.
4. **Error Path Mapping** — For each stage in the pipeline, identify what happens on failure. Does the error propagate correctly? Is cleanup guaranteed?

---

## Mandatory Runtime Verification

**Before evaluating any checklist item, you MUST complete these steps. Use the commands provided in the project's commands file. Skip only if a step is impossible — document why.**

### Step R1 — Import Full Pipeline

Import the CLI entry point, config reader, and all service modules. Verify the full chain is importable.

### Step R2 — Linter and Type Checker

Run the project's configured linter and type checker commands.

- Record exit codes and output.

### Step R3 — Run Test Suite

Run the complete test suite.

- Record pass/fail counts and failure output.

---

## Audit Scope

End-to-end data flow from CLI invocation through config loading, Telegram client auth, message fetching, processing, and forwarding. Cross-layer interaction verification.

---

## Audit Dimensions

### 1. Config-to-Service Propagation

**Trace each config section from YAML to its final consumer. Document every hop.**

| Config Section | Expected Consumer | Verification |
|----------------|-------------------|--------------|
| `telethon.*` | `TelegramClient()` | Verify api_id, api_hash, session all reach the client. |
| `scan_interval` | `monitor.py` main loop | Verify interval controls monitoring frequency. |
| `channels` | `Task` creation in monitor.py | Verify channel_name, forward_to, keywords all reach the Task. |

**For each field, document:** YAML key → Pydantic model field → function parameter. If any hop is missing or broken, that is a finding.

### 2. Message Lifecycle Trace

**Trace a single message from Telegram channel to forwarded message. Document every transformation.**

| Stage | Input | Output | Verification |
|-------|-------|--------|--------------|
| Telegram message fetch | channel_name | `Message` objects | Verify messages are fetched correctly. |
| Keyword matching | message text, keywords | match/no-match | Verify filter logic is correct. |
| Album grouping | messages with media_group_id | grouped message list | Verify album logic works. |
| Task state update | processed messages | `last_msg_id` update | Verify state is persisted. |
| Forwarding | matched messages, targets | Telegram API call | Verify messages are forwarded correctly. |

**If any transformation is incorrect, missing, or loses data, that is a finding.**

### 3. Multi-Channel Flow Correctness

| Check | Description |
|-------|-------------|
| Each channel gets its own messages | Messages from channel A are not fetched for channel B. |
| Channel-specific delays | `scan_interval` is applied per-channel. |
| All channels are processed | Every channel in the config list is processed, not just the first one. |
| Empty channels are handled | A channel with no new messages is skipped gracefully (no crash). |

**Evidence required:** Read the multi-channel loop in `monitor.py`. Verify messages are correctly scoped to each channel.

### 4. Error Propagation & Cleanup

| Check | Description |
|-------|-------------|
| Config error stops before fetching | If config is invalid, the CLI reports the error and exits without attempting to fetch. |
| Telegram failure doesn't crash the app | If sending to one channel fails, other channels are still processed. |
| State save failures handled | If state save fails, the error is logged but processing continues. |
| Cleanup runs on success | After all messages are forwarded, resources are cleaned up. |
| Cleanup runs on failure | If forwarding fails mid-way, cleanup still runs. |
| KeyboardInterrupt is handled | Pressing Ctrl+C during monitoring stops gracefully. |

**Evidence required:** Read error handling at each stage. Verify `try/finally` or context managers are used where needed.

### 5. Data Integrity

| Check | Description |
|-------|-------------|
| No message loss between stages | Every message that matches keywords is forwarded. No messages are silently dropped. |
| Text content is preserved | Message text is not truncated or modified incorrectly. |
| Duplicate prevention works | Messages with same id are not re-forwarded. |

**Evidence required:** Trace data through each transformation. Check for off-by-one errors or incorrect state management.

---

## Report Output

Write findings to: `.ai/audit/06-data-flow/findings.md` using template `.ai/audit/templates/audit-findings.md`.

**Write the file incrementally — append blocks of ≤100 lines each. Never write the entire report in a single call.**

Use prefix `DF-` for finding IDs.

**`problems-only: true` rules:**
- The report contains **only findings** — real problems discovered during investigation.
- Do NOT include sections, dimensions, or checklist rows where everything is correct.
- If after completing all Runtime Verification steps and all Audit Dimensions, no problems were found, write a single line: `No problems found in this phase.`
- Every finding MUST include:
  1. **Runtime evidence** — traced data flow showing where the break occurs, test failures, missing error handlers.
  2. **Not just:** "violates invariant X" — show the exact stage, the exact data, and the exact consequence (lost post, wrong chat, orphaned file).
