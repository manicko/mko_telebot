---
name: 03-audit-services-validated
description: Validated findings for service layer phase
agent: validator
alwaysApply: false
---

# Phase 03 Audit Findings — Service Layer & Business Logic

**Executor:** auditor  
**Validator:** validator
**Template:** .ai/audit/templates/audit-findings.md  
**Status:** validated  
**Validated:** yes

---

## Findings

### SRV-001: Forum Topic Support Uses Incorrect Parameter

| Field | Value |
|-------|-------|
| **ID** | SRV-001 |
| **Severity** | CRITICAL |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/telegram_service.py` |
| **Classification** | mandatory |

**Description:** The code implements `topic_id` support for forum topics but passes it to Telethon's `send_message` and `send_file` methods via the `reply_to` parameter. This is incorrect - `reply_to` as an integer replies to a specific message, not sends to a forum topic.

**Evidence:**
- Line 230 in `telegram_service.py`: `await client.send_file(post.chat_id, files, caption=post.txt, reply_to=post.topic_id)`
- Line 237 in `telegram_service.py`: `await client.send_message(post.chat_id, post.txt, reply_to=post.topic_id)`
- `get_dir_content` (utils.py line 31-44) returns `list[Path]` via `Path.glob()` which is correct
- Tests (test_telegram_service.py) use `topic_id` values but do not validate Telethon API format

**Telethon API Behavior:**
- `reply_to` integer: replies to that message ID
- `reply_to` as `InputReplyToMessage`: requires `top_msg_id` for forum topic posting
- Forum topic message ID (from URL like `t.me/chat/12345`) needs `InputReplyToMessage(reply_to_msg_id=topic_id, top_msg_id=topic_id)`

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed SRV-001 is a valid finding. The current implementation passes `topic_id` as an integer to `reply_to`, which will send messages as replies rather than posting to forum topics. The SPEC.md explicitly documents forum topic support (lines 220-234, 254) with the requirement that `topic_id` enables posting to topics. The fix requires using `InputReplyToMessage` for `topic_id > 0`.
> - **See also:** CLI-002 (different issue, same topic_id feature area)

---

### SRV-002: Task Model Missing Status Tracking Field

| Field | Value |
|-------|-------|
| **ID** | SRV-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/task.py`, `.kilo/commands/audit/phases/03-audit-services.md` |
| **Classification** | advisory |

> **Rejection reason:** The audit template (03-audit-services.md line 128) states "Task status tracking — Task has a status field to track success/failure" as a checklist item. However, the primary SPEC.md documentation (docs/SPEC.md) does not specify or require a status field on the Task model. The Task is correctly documented in SPEC.md line 85 as a "dataclass" with no mention of status. The `_send_posts` method tracks success/failure via local counters which is sufficient for the current architecture. Adding a status field would add complexity without clear benefit - the success/failure counts are logged at INFO level (line 202 in telegram_service.py) and the Task is not persisted. This is not a spec deviation; the audit template requirement is not grounded in the actual specification.

---

### SRV-003: Photo Directory Resolution Timing Issue

| Field | Value |
|-------|-------|
| **ID** | SRV-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telepost/core/post_processor.py`, `src/mko_telepost/core/utils.py` |
| **Classification** | advisory |

> **Rejection reason:** The analysis is incorrect. Looking at the actual flow:
> 1. `post_processor.py` line 127: `raw_entry_resolved = base_dir / raw_entry` resolves relative to base_dir
> 2. `post_processor.py` line 128: `get_dir_content(raw_entry_resolved)` reads files from the resolved path
> 3. `post_processor.py` line 131: Files are collected and returned
> 4. `post_processor.py` line 203: `_validate_photo_paths(photo_paths)` validates each path via `_validate_photo_path` (line 166)
> 5. `post_processor.py` line 83: `is_relative_to()` check prevents directory traversal
>
> The validation DOES occur after extraction, but the resolution step (`base_dir / raw_entry`) confines the path to `content_dir` or `user_dir`. Any files outside these bounds would fail the `is_relative_to` check. Additionally, `allow_absolute_paths` mode explicitly allows any valid path (line 67-70 in post_processor.py). The code functions correctly per the specification's security requirements.

---

### SRV-004: get_dir_content Return Type Mismatch

| Field | Value |
|-------|-------|
| **ID** | SRV-004 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Classification** | mandatory |

> **Rejection reason:** The evidence does not support this finding. Verification:
> - `utils.py` line 35: `def get_dir_content(...) -> list[Path]:` - correct return type annotation
> - `utils.py` line 40: `files.extend(Path(path).glob(...))` - glob returns `Path` objects, correctly added to `files: list[Path]`
> - `post_processor.py` line 131: `[Path(p) for p in raw]` - this is syntactically safe since `Path(Path(...))` is idempotent (returns the same Path)
> - `mypy` passes with no errors on both files
> - Tests in `test_utils.py` line 67-74 confirm `get_dir_content` returns `list[Path]` objects
>
> There is no type mismatch. The code is type-correct and functions as designed.

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
| Validated (unchanged) | 1 | SRV-001 |
| Reclassified | 0 |
| Merged | 0 |
| Rejected | 3 | SRV-002, SRV-003, SRV-004 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| SRV-002 | Task Model Missing Status Tracking Field | Audit template requirement not grounded in actual SPEC.md. Task as dataclass is correct. Success/failure tracking via local counters is architecturally appropriate. |
| SRV-003 | Photo Directory Resolution Timing Issue | Security analysis incorrect. Path resolution (`base_dir / raw_entry`) confines to allowed directory before `get_dir_content` call. `is_relative_to()` check prevents directory traversal. Code functions correctly per spec. |
| SRV-004 | get_dir_content Return Type Mismatch | No type mismatch exists. `get_dir_content` returns `list[Path]` correctly. `Path(Path(...))` is idempotent. mypy passes without errors. |

---

## Rollout Safety Assessment

**Dependency Chain:** SRV-001 is independent - no dependencies on other findings.

**Rollout Risk:** Low for the single validated finding. The fix involves conditional logic for `topic_id > 0` using Telethon's `InputReplyToMessage` type.

**Sequencing:** Can be implemented independently. Requires adding `from telethon.types import InputReplyToMessage` import.

**Hidden Dependencies:** None detected. The `_try_send_message` method is called only from `_send_posts` within the same class.

---

## Warnings

- **Feature Impact:** SRV-001 indicates `topic_id` forum support is currently non-functional. Users attempting to post to Telegram forum topics will experience incorrect behavior (messages posted as replies instead of topic posts).

---

## Required Fixes

- `src/mko_telepost/core/telegram_service.py lines 221-245`: Replace `reply_to=post.topic_id` with conditional `InputReplyToMessage` construction when `topic_id > 0`.

---

## Advisory Recommendations

- Add integration test for forum topic posting with real Telethon API expectations.
- Consider adding `top_msg_id` parameter support if topics need to reference different root messages.