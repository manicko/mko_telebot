# basedpyright Audit Report: monitor_client.py

## Summary
- **File**: `src/mko_telebot/monitor_client.py`
- **Total Issues**: 12 (7 errors, 5 warnings)

---

## Errors

### 1. CRITICAL - Argument Type Mismatch (reportArgumentType)
**Lines 54-59** - Proxy and client configuration parameters incompatible with TelegramClient

**Issue**:
```python
return TelegramClient(
    session=str(session_path),
    api_id=client.api_id,
    api_hash=api_hash,
    proxy=proxy_dict,           # Line 54 - dict[str, object] | None not assignable
    app_version=client.app_version,      # Line 55 - str | None not assignable
    device_model=client.device_model,    # Line 56 - str | None not assignable
    system_version=client.system_version, # Line 57 - str | None not assignable
    lang_code=client.lang_code,          # Line 58 - str | None not assignable
    system_lang_code=client.system_lang_code, # Line 59 - str | None not assignable
)
```

**Description**: The `TelegramClient.__init__()` expects `str` for optional string parameters, but `ClientConfig` defines them as `str | None`. The code passes `None` values directly instead of handling the optionality.

**Severity**: CRITICAL
**Category**: Type Safety

---

### 2. CRITICAL - None Not Awaitable (reportGeneralTypeIssues)
**Line 77:19** - `await client.start(...)` in user mode

**Issue**:
```python
if settings.telethon.is_user:
    await client.start(phone=...)  # Line 77 - "TelegramClient" is not awaitable
```

**Description**: The type checker infers that `TelegramClient` itself (not a coroutine) is being awaited. This is because `start()` returns `Coroutine[Any, Any, None]` but without type stubs, the return type is unknown, causing the checker to treat the client itself as the result.

**Severity**: CRITICAL
**Category**: Type Safety

---

### 3. CRITICAL - None Not Awaitable (reportGeneralTypeIssues)
**Line 82:19** - `await client.start(...)` in bot mode

**Issue**:
```python
else:
    await client.start(bot_token=...)  # Line 82 - "TelegramClient" is not awaitable
```

**Description**: Same as above - missing type stubs cause incorrect type inference.

**Severity**: CRITICAL
**Category**: Type Safety

---

### 4. CRITICAL - Argument Type Mismatch: Proxy (reportArgumentType)
**Line 54:15** - `proxy=proxy_dict` where `proxy_dict: dict[str, object] | None`

**Description**: The `TelegramClient` expects proxy to be `tuple[Unknown, ...] | dict[Unknown, Unknown]` but the code passes `dict[str, object] | None`. The type annotations in `ProxyConfig.to_dict()` use `dict[str, object]` instead of matching Telethon's expected types.

**Severity**: HIGH
**Category**: Type Safety

---

## Warnings

### 5. MEDIUM - Missing Type Stubs (reportMissingTypeStubs)
**Line 6:6** - `from telethon import TelegramClient`

**Description**: No type stubs available for `telethon` package.

**Severity**: LOW
**Category**: Type Safety

### 6. MEDIUM - Missing Type Stubs (reportMissingTypeStubs)
**Line 11:6** - `from telethon.tl.custom.message import Message`

**Description**: No type stubs for Telethon's message types.

**Severity**: LOW
**Category**: Type Safety

### 7. MEDIUM - Unknown Type (reportUnknownVariableType / reportAny)
**Lines 108-109, 126-132, 138-139** - Dynamic attribute access on `chat`, `sender` objects

**Issue**:
```python
chat = getattr(msg, "chat", None)        # Line 106
if chat and getattr(chat, "username", None):  # Lines 108-109 - Any type

sender = await msg.get_sender()           # Line 126 - Unknown | None
if getattr(sender, "username", None):    # Lines 131-132 - Any type
```

**Description**: Without type stubs, `getattr()` returns `Any` and `msg.get_sender()` returns `Unknown`. This makes type checking ineffective for these attribute accesses.

**Severity**: MEDIUM
**Category**: Type Safety

---

## Recommendations

1. **CRITICAL**: Fix optional parameter handling in `create_client()`:
   ```python
   return TelegramClient(
       session=str(session_path),
       api_id=client.api_id,
       api_hash=api_hash,
       proxy=proxy_dict if proxy_dict else None,
       app_version=client.app_version or "",
       device_model=client.device_model or "",
       system_version=client.system_version or "",
       lang_code=client.lang_code or "",
       system_lang_code=client.system_lang_code or "",
   )
   ```
   Or update `ClientConfig` to not use `| None` for these fields.

2. **CRITICAL**: Fix `ProxyConfig.to_dict()` return type to match Telethon's expectations:
   ```python
   def to_dict(self) -> tuple[str, str, int] | dict[str, str | int]:
   ```

3. **LOW**: Install type stubs for telethon if available to improve type checking accuracy.

4. **MEDIUM**: Consider using explicit `isinstance()` checks instead of `getattr()` for better type narrowing.