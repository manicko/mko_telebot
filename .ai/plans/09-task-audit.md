# Type Check Audit Report: task.py

**File:** `src/mko_telebot/core/task.py`  
**Date:** 2026-07-12  
**Tool:** basedpyright (strict type checking)

## Summary

| Status | Count |
|--------|-------|
| Errors | 0 |
| Warnings | 12 |
| Notes | 0 |

## Findings

### Critical Issues

#### 1. Unannotated Class Attributes (reportUnannotatedClassAttribute)

**Severity:** MEDIUM  
**Lines:** 47-61

Multiple instance attributes are assigned in `__init__` without type annotations:

```python
# Lines 47-61
self.channel_name = config.name
self.channel_entity = None
self.forward_to = config.forward_to
self.forward_to_entities: list[object] = []  # Only this one has annotation
self.keywords = config.keywords
self.scan_interval = config.scan_interval
self.history_days = config.history_days
self.last_msg_id = last_msg_id or 0
self.overlap = config.overlap
```

**Evidence:** Lines 47 (channel_name), 48 (channel_entity), 49 (forward_to), 51 (keywords), 52 (scan_interval), 53 (history_limit), 54 (history_days), 60 (last_msg_id), 61 (overlap) all report missing annotations.

**Recommendation:** Add explicit type annotations to all instance attributes. Since Pydantic's `ChannelConfig` provides type information:

- `channel_name: str`
- `channel_entity: object | None` (Telethon entity type)
- `forward_to: list[str]`
- `keywords: list[str]`
- `scan_interval: int`
- `history_limit: int`
- `history_days: int | None`
- `last_msg_id: int`
- `overlap: int`

---

### High Priority Issues

#### 2. Use of `Any` Type (reportExplicitAny, reportAny)

**Severity:** HIGH  
**Lines:** 63, 63, 73, 73, 74, 86, 86, 89, 89

The `Any` type is used extensively for Telethon client and entity types:

```python
# Line 63, 86
async def resolve_targets_entities(self, client: Any) -> None:
async def resolve_channel_entity(self, client: Any) -> None:
```

**Evidence:** Type parameter `Any` is used for `client` parameter, and return types are inferred as `Any` when calling `client.get_entity()`.

**Recommendation:** Use proper Telethon types from `telethon` package. Consider importing:
- `from telethon import TelegramClient` for client
- `from telethon.tl.types import Channel, Chat, User` for entity types

The project guideline requires "Type Safety Everywhere" with Pydantic v2 + type hints. Using `Any` defeats this purpose.

---

#### 3. Unknown Type from `json.loads` (reportUnknownVariableType, reportUnknownMemberType)

**Severity:** MEDIUM  
**Lines:** 138, 139

```python
# Lines 137-139
content = await f.read()
state = json.loads(content) if content else {}
self.last_msg_id = max(self.last_msg_id, state.get("last_id", 0))
```

**Evidence:** `json.loads()` returns `Any` in strict mode, causing the `state` variable to have unknown type, which propagates to the `max()` call.

**Recommendation:** Use explicit type annotation:
```python
state: dict[str, int] = json.loads(content) if content else {}
self.last_msg_id = max(self.last_msg_id, state.get("last_id", 0))
```

Or use a Pydantic model for state deserialization.

---

#### 4. Unused Call Result (reportUnusedCallResult)

**Severity:** LOW  
**Line:** 157

```python
# Line 157
await f.write(json.dumps({"last_id": self.last_msg_id}))
```

**Evidence:** The result of `await f.write()` is not used. This is typically a warning about ignoring potential errors.

**Recommendation:** Consider using `_ = await f.write(...)` to acknowledge intentional discard.

---

### Additional Observations

The Task class is a Pydantic-like configuration class but implemented manually. Consider converting to a `BaseModel` with `TypeAdapter` for state persistence, or at minimum add explicit type annotations to all attributes.