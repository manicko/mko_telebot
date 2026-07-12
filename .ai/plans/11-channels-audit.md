# Type Check Audit Report: channels.py

**File:** `src/mko_telebot/core/channels.py`  
**Date:** 2026-07-12  
**Tool:** basedpyright (strict type checking)

## Summary

| Status | Count |
|--------|-------|
| Errors | 0 |
| Warnings | 24 |
| Notes | 0 |

## Findings

### Critical Issues

#### 1. Unannotated `model_config` Class Attributes (reportUnannotatedClassAttribute)

**Severity:** MEDIUM  
**Lines:** 33, 71, 102

The `model_config` class attribute is assigned in three Pydantic models without type annotation:

```python
# Line 33 (ChannelConfig)
model_config = ConfigDict(extra="forbid")

# Line 71 (ChannelDefaults)
model_config = ConfigDict(extra="forbid")

# Line 102 (ChannelsConfig)
model_config = ConfigDict(extra="forbid")
```

**Evidence:** All three models use `model_config` attribute but it lacks the required type annotation since classes are not decorated with `@final`.

**Recommendation:** Add explicit type annotation:
```python
model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
```

Requires adding `from typing import ClassVar` import.

---

### High Priority Issues

#### 2. Unused Return Value (reportUnusedCallResult)

**Severity:** LOW  
**Line:** 120

```python
# Line 120
self.channels.pop("DEFAULTS", None)
```

**Evidence:** The result of `pop()` is intentionally discarded to prevent errors if "DEFAULTS" key doesn't exist.

**Recommendation:** Use `_ = self.channels.pop("DEFAULTS", None)` to explicitly acknowledge the discard is intentional.

---

#### 3. Usage of `Any` Type in Type Casting (reportAny, reportUnknownArgumentType)

**Severity:** HIGH  
**Lines:** 130, 131, 140, 146

```python
# Lines 126-146
defaults_data = self.defaults.model_dump(exclude_none=True)
for channel_key, channel in self.channels.items():
    update_data: dict[str, object] = {}
    for field_name, default_value in defaults_data.items():
        current_val = getattr(channel, field_name)
        field_info = ChannelConfig.model_fields[field_name]
        if field_info.default_factory is not None:
            update_data[field_name] = default_value
        elif current_val is None or current_val == field_info.default:
            update_data[field_name] = default_value
    if update_data:
        merged_data = channel.model_dump()
        merged_data.update(update_data)
        self.channels[channel_key] = ChannelConfig(**merged_data)  # Line 146
```

**Evidence:** Multiple issues at line 146:
- `default_value` is `Any` (from `model_dump()` iteration)
- `current_val` is `Any` (from `getattr()`)
- `field_info.default` is `Any`
- `ChannelConfig(**merged_data)` receives `Any` arguments for `name`, `forward_to`, `keywords`, `scan_interval`, `history_limit`, `history_days`, `overlap`

**Recommendation:** Use `model_validate` instead of direct construction:
```python
self.channels[channel_key] = ChannelConfig.model_validate(merged_data)
```

This provides better type safety and validation.

---

### Root Cause Analysis

The issues stem from:

1. **Missing ClassVar import:** Pydantic 2.x recommends `ClassVar[ConfigDict]` for class-level config
2. **Dynamic data handling:** The `apply_defaults_to_channels` validator uses dynamic field access via `getattr()` which returns `Any`
3. **Unsafe model construction:** Building `ChannelConfig` from loosely-typed `dict[str, object]`

### Suggested Fix Priority

| Issue | Priority | Effort |
|-------|----------|--------|
| ClassVar annotations | HIGH | Trivial |
| Use model_validate | MEDIUM | Small |
| Explicit type declarations | MEDIUM | Small |