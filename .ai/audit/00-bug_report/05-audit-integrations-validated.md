---
name: 05-audit-integrations-validated
description: Validated findings for external integrations phase
agent: validator
alwaysApply: false
---

# Phase 05 Audit Findings — External Integrations

**Executor:** auditor
**Validator:** validator
**Template:** .ai/audit/templates/audit-findings.md
**Status:** validated
**Validated:** yes

---

## Findings

### INT-001: Forum Topic Support Uses Incorrect Telethon Parameter

| Field | Value |
|-------|-------|
| **ID** | INT-001 |
| **Severity** | CRITICAL |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | mandatory |

> **Validation Note:**
> - **Action:** merged
> - **Detail:** INT-001 duplicates SRV-001 (Phase 03 - Services) which addresses the identical issue. The same code in `telegram_service.py` lines 226-238 passes `topic_id` as an integer to `reply_to` parameter, which is incorrect for forum topic posting. Both findings have been validated against SPEC.md (lines 220-234, 254) which documents forum topic support, and against the Telethon source code (uploads.py line 475, messages.py lines 892, 916) which shows `reply_to` integer is converted to `InputReplyToMessage(reply_to_msg_id=int)` instead of using `top_msg_id` for forum topics.
> - **See also:** SRV-001 (Phase 03), merged into INT-001

**Description:** The code passes topic_id as the reply_to parameter to Telethon send_message and send_file methods (lines 226-238). This is incorrect - reply_to is documented as the ID of the message that it should reply to, not the forum topic ID. Telethon's InputReplyToMessage type supports a top_msg_id parameter specifically for forum topics, which should be used instead. Using reply_to for topic IDs will cause messages to either fail with API errors or be sent to the wrong location (potentially replying to a non-existent message).

**Evidence:**
- `telegram_service.py` lines 226-231: `await client.send_file(post.chat_id, files, caption=post.txt, reply_to=post.topic_id)`
- `telegram_service.py` lines 234-238: `await client.send_message(post.chat_id, post.txt, reply_to=post.topic_id)`
- Telethon `InputReplyToMessage` signature: `reply_to_msg_id: int, top_msg_id: int | None = None`
- Telethon documentation: reply_to is "If an integer is provided, it should be the ID of the message that it should reply to."
- Telethon source (`uploads.py` line 475, `messages.py` lines 892/916): `reply_to = None if reply_to is None else types.InputReplyToMessage(reply_to)` - integer becomes `reply_to_msg_id`

**Recommendation:** Replace `reply_to=post.topic_id` with proper forum topic handling using `InputReplyToMessage`:
```python
from telethon.tl import types

reply_to = None
if post.topic_id > 0:
    reply_to = types.InputReplyToMessage(
        reply_to_msg_id=post.topic_id,
        top_msg_id=post.topic_id,
    )
await client.send_file(..., reply_to=reply_to, ...)
```

### INT-002: ~~RPCError Not Caught for Transient Error Retry~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | INT-002 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | mandatory |

> **Rejection reason:** The recommendation to catch `errors.RPCError` broadly would break the intentional separation between permanent and transient error handling. Verification shows:
> - All errors currently caught as permanent (`ForbiddenError`, `ChatAdminRequiredError`, `ChannelPrivateError`) ARE subclasses of `RPCError`
> - Catching `RPCError` would cause permanent errors to be retried (incorrect behavior)
> - The current code correctly distinguishes: permanent errors fail fast without retry, specific transient errors (WorkerBusyTooLongRetryError, ServerError, RpcCallFailError, TimedOutError) are retried with exponential backoff
> - `ConnectionError` is caught separately as a Python built-in exception (network-level), which is appropriate
> - The existing error list targets known transient RPC errors specifically; broadening to `RPCError` would introduce operational risk

The code at lines 247-282 implements intentional error classification. The first except block (lines 247-256) catches permanent errors and returns `False` immediately. The second block (lines 268-282) catches specific transient RPC errors and retries. Catching `RPCError` broadly would collapse this distinction and cause messages to be retried on permanent failures (e.g., ForbiddenError due to lacking permissions).

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 0 | |
| Reclassified | 0 | |
| Merged | 1 | INT-001 → SRV-001 (Phase 03) |
| Rejected | 1 | INT-002 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| INT-002 | RPCError Not Caught for Transient Error Retry | Recommendation would break permanent/transient error distinction. All caught errors ARE RPCError subclasses; broadening would retry permanent errors incorrectly. Current implementation correctly distinguishes error types. |

### Merged Findings

| Original ID | Merged Into | Rationale |
|-------------|-------------|----------|
| INT-001 | SRV-001 (Phase 03) | Duplicate finding addressing identical root cause: incorrect forum topic parameter handling in telegram_service.py. Both validated against same code (lines 226-238) and SPEC.md documentation. |

---

## Rollout Safety Assessment

**Dependency Chain:** INT-001 depends on SRV-001 fix being implemented. Once merged, the fix is the same.

**Rollout Risk:** Low - the fix involves conditional logic for `topic_id > 0` using Telethon's `InputReplyToMessage` type. The change is isolated to the `_try_send_message` method.

**Sequencing:** Can be implemented independently. Requires adding `from telethon.tl import types` import (or using `types.InputReplyToMessage` directly).

**Hidden Dependencies:** None detected. The `_try_send_message` method is called only from `_send_posts` within the same class.

---

## Warnings

- **Feature Impact:** INT-001 indicates `topic_id` forum support is currently non-functional. Users attempting to post to Telegram forum topics will experience incorrect behavior (messages posted as replies instead of topic posts).

- **Error Handling:** The current error handling strategy correctly distinguishes permanent (no permissions, private chat) from transient (server errors, timeouts) errors. The rejection of INT-002 preserves this intentional design.

---

## Required Fixes

- `src/mko_telepost/core/telegram_service.py lines 226-238`: Replace `reply_to=post.topic_id` with conditional `InputReplyToMessage` construction when `topic_id > 0` (same fix as SRV-001).

---

## Advisory Recommendations

- Add integration test for forum topic posting with real Telethon API expectations.
- Consider documenting the distinction between reply_to and forum topic usage in the code comments.