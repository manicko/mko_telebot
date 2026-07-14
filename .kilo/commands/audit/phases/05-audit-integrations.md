---
name: 04-integrations
status: complete
validated: no
executor: auditor
problems-only: true
---

# Phase 05 Audit — External Integrations

## Output Mode

`problems-only: true` — **only problems, bugs, and deviations are documented.**

- **Do NOT** write sections that say "X is correct" or "no issues found in Y".
- **Do NOT** include checklist rows where the check passes — omit them entirely.
- If a dimension has zero findings after investigation, **omit the dimension entirely**.
- Every finding must be actionable: it describes a real problem, its evidence (code/logs/output), and its impact.

---

## Discovery Stage

Before performing audit checks, discover the integration architecture:

1. **Telegram Integration Discovery** — Locate the Telethon client setup. Map the auth flow: api_id/api_hash → session → client → send operations. Identify how messages are fetched and forwarded.
2. **Error Handling Discovery** — Identify error handling patterns for the Telegram integration: what happens when the API is unreachable? When credentials are invalid? When rate limits are hit?
3. **Config Injection Discovery** — Trace how API credentials and settings flow from Pydantic models into the integration clients.

---

## Audit Scope

Telegram API integration (TelegramClient), Telethon error handling, credential management.

---

## Audit Dimensions

### 1. Telegram Integration

| Check | Description |
|-------|-------------|
| Client creation is correct | `TelegramClient` is created with the correct session name, api_id, and api_hash from config. |
| Auth supports both user and bot | The `is_user` flag correctly switches between phone auth and bot token auth. |
| Messages sent with correct parameters | `send_message` and `send_file` are called with the correct chat_id and content. |
| Flood control is handled | `FloodWaitError` triggers a wait-and-retry with the specified duration plus jitter. |
| Other transient errors are retried | `WorkerBusyTooLongRetryError` and `RPCError` trigger retries with exponential backoff. |
| Permanent errors are not retried indefinitely | After max retries, the error is logged and the post is skipped (not retried forever). |
| Client lifecycle is managed | The Telegram client is properly started and stopped. |

**Evidence required:** Read `monitor_client.py` and `monitor_forward.py`. Verify retry logic and client lifecycle.

---

## Report Output

Write findings to: `/.ai/audit/05-integrations/findings.md` using template `/.ai/audit/templates/audit-findings.md`.

**Write the file incrementally — append blocks of ≤100 lines each. Never write the entire report in a single call.**

Use prefix `INT-` for finding IDs.

**`problems-only: true` rules:**
- The report contains **only findings** — real problems discovered during investigation.
- Do NOT include sections, dimensions, or checklist rows where everything is correct.
- If after completing all Runtime Verification steps and all Audit Dimensions, no problems were found, write a single line: `No problems found in this phase.`
- Every finding MUST include:
  1. **Runtime evidence** — import errors, test failures, code analysis showing the bug.
  2. **Not just:** "violates invariant X" — show the exact code that violates it and the exact consequence.
