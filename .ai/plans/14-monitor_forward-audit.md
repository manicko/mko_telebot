# basedpyright Audit Report: monitor_forward.py

## Summary
- **File**: `src/mko_telebot/monitor_forward.py`
- **Total Issues**: 24 (5 errors, 19 warnings)

---

## Errors

### 1. CRITICAL - Argument Type Mismatch (reportArgumentType)
**Line 72:25** - `target` entity type incompatible with `send_file`

**Issue**:
```python
await client.send_file(target, msg_media, ...)  # Line 72
```

**Description**: `target` comes from `task.forward_to_entities` which is typed as `list[object]` (see `task.py` line 50). The `send_file` method expects `EntityLike` (str, int, or Telethon peer types), but receives `object`.

**Severity**: CRITICAL
**Category**: Type Safety

**File Reference**: `src/mko_telebot/core/task.py:50` - `forward_to_entities: list[object] = []`

---

### 2. CRITICAL - Argument Type Mismatch: Caption (reportArgumentType)
**Line 72:52** - `caption` type incompatible with `send_file`

**Issue**:
```python
await client.send_file(target, msg_media, caption=caption or None, ...)  # Line 72
```

**Description**: The `caption` parameter in `send_file` expects `str | Sequence[str]`, but the code passes `LiteralString | None`. When `caption` is empty string `""`, `caption or None` evaluates to `None`, which is not assignable.

**Severity**: CRITICAL
**Category**: Type Safety

---

### 3. CRITICAL - Argument Type Mismatch: Entity (reportArgumentType)
**Line 76:21** - `target` entity type incompatible with `send_message`

**Issue**:
```python
await client.send_message(target, caption or "", ...)  # Line 76
```

**Description**: Same as error 1 - `target` is `object` instead of `EntityLike`.

**Severity**: CRITICAL
**Category**: Type Safety

---

### 4. CRITICAL - Optional Member Access (reportOptionalMemberAccess)
**Line 154:64** - Accessing `caption` on possibly-None media

**Issue**:
```python
if getattr(msg.media, "caption", None):  # Line 154 - accessing caption on media
    msg_content[group_id]["text"].append(msg.media.caption)
```

**Description**: After `getattr(msg.media, "caption", None)` check, the code accesses `msg.media.caption` directly. The type checker sees `msg.media` as potentially None on certain media types, and `caption` is not available on all `MessageMedia` subclasses.

**Severity**: CRITICAL
**Category**: Correctness

---

### 5. CRITICAL - Attribute Access on MessageMedia Types (reportAttributeAccessIssue)
**Line 154:64** - `caption` attribute not present on multiple `MessageMedia` types

**Description**: The code checks `msg.media.caption` but `caption` is not a universal attribute:
- `MessageMediaPhoto` - no `caption`
- `MessageMediaGeo` - no `caption`
- `MessageMediaContact` - no `caption`
- `MessageMediaUnsupported` - no `caption`
- And 15 other `MessageMedia` types

**Severity**: CRITICAL
**Category**: Correctness

---

### 6. CRITICAL - Argument Type Mismatch: Entity (reportArgumentType)
**Line 192:13** - `task.channel_entity` incompatible with `iter_messages`

**Issue**:
```python
messages_iter = client.iter_messages(
    task.channel_entity,  # Line 192 - Any | None not assignable to EntityLike
)
```

**Description**: `task.channel_entity` is typed as `None` in `Task.__init__` (line 48 of task.py) and can be `Any` after resolution. This should use proper Telethon entity types.

**Severity**: CRITICAL
**Category**: Type Safety

---

## Warnings

### 7-19. MEDIUM - Missing Type Stubs (reportMissingTypeStubs / reportUnknownVariableType)
**Lines 11-12, 53, 108-109, 126-132, 138-139, 150-154, 158-167, 199-226**

These warnings stem from missing Telethon type stubs causing:
- Unknown types for `msg.media`, `msg.message`, `msg.grouped_id`
- Unknown types for dynamic attribute access via `getattr()`
- Partially unknown types in loops and iterations

**Severity**: MEDIUM
**Category**: Type Safety

---

### 20. MEDIUM - Explicit Any Type (reportExplicitAny)
**Line 26:21** - `msg_media: list[Any]`

**Issue**:
```python
msg_media: list[Any]
```

**Description**: Using `Any` bypasses type checking. Should use a proper Telethon media type.

**Severity**: MEDIUM
**Category**: Type Safety

---

### 21-24. LOW - Implicit String Concatenation (reportImplicitStringConcatenation)
**Lines 85-88, 95-98, 105-108, 116-117**

These are string constants split across lines using implicit concatenation, which basedpyright flags as not best practice.

**Severity**: LOW
**Category**: Style

---

## Recommendations

1. **CRITICAL**: Define proper types for `Task.forward_to_entities` and `Task.channel_entity`:
   ```python
   from telethon.tl.types import PeerChannel, PeerChat, PeerUser, InputPeerChannel, InputPeerChat, InputPeerUser
   
   forward_to_entities: list[PeerChannel | PeerChat | PeerUser | int | str] = []
   channel_entity: PeerChannel | InputPeerChannel | None = None
   ```

2. **CRITICAL**: Handle media caption extraction safely:
   ```python
   from telethon.tl.types import MessageMediaDocument
   
   if getattr(msg, "media", None) and isinstance(msg.media, MessageMediaDocument):
       if getattr(msg.media, "caption", None):
           msg_content[group_id]["text"].append(msg.media.caption)
   ```

3. **CRITICAL**: Replace `Any` with concrete types for media list in `forward_to_users()` function signature.

4. **MEDIUM**: Use single-line strings or explicit line-continuation instead of implicit string concatenation.