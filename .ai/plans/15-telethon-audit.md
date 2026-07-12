# basedpyright Audit Report: telethon.py

## Summary
- **File**: `src/mko_telebot/core/telethon.py`
- **Total Issues**: 6 (0 errors, 6 warnings)

---

## Warnings

### 1. MEDIUM - Unannotated Class Attribute (reportUnannotatedClassAttribute)
**Line 23:5** - `model_config` in `ProxyConfig`

**Issue**:
```python
class ProxyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Line 23 - no type annotation
```

**Description**: Pydantic `BaseModel` subclasses require explicit type annotations for `model_config` class attribute when the class is not decorated with `@final`. The type checker cannot infer the type.

**Severity**: MEDIUM
**Category**: Type Safety

---

### 2. MEDIUM - Implicit String Concatenation (reportImplicitStringConcatenation)
**Line 59:21** - Multi-line string literal

**Issue**:
```python
raise ValueError(
    f"{v} appears to be a placeholder value. "
    "Replace with your actual value."
)
```

**Description**: The type checker flags implicit string concatenation across lines. While valid Python, it prefers explicit multi-line strings or proper line-joining.

**Severity**: LOW
**Category**: Style

---

### 3. MEDIUM - Unannotated Class Attribute (reportUnannotatedClassAttribute)
**Line 100:5** - `model_config` in `ClientConfig`

**Description**: Same as warning 1 - missing type annotation for `model_config`.

**Severity**: MEDIUM
**Category**: Type Safety

---

### 4. MEDIUM - Implicit String Concatenation (reportImplicitStringConcatenation)
**Line 161:17** - Multi-line string literal

**Issue**:
```python
raise ValueError(
    "api_id value 12345 is a template placeholder. "
    "Replace with your actual API ID from https://my.telegram.org/apps."
)
```

**Description**: Same implicit string concatenation pattern.

**Severity**: LOW
**Category**: Style

---

### 5. MEDIUM - Unannotated Class Attribute (reportUnannotatedClassAttribute)
**Line 177:5** - `model_config` in `TelethonConfig`

**Description**: Same as warning 1 - missing type annotation for `model_config`.

**Severity**: MEDIUM
**Category**: Type Safety

---

### 6. MEDIUM - Implicit String Concatenation (reportImplicitStringConcatenation)
**Line 194:17** - Multi-line string in `validate_phone_or_token`

**Issue**:
```python
raise ValueError(
    "phone_or_token appears to be a placeholder value. "
    "Replace with your phone number or bot token."
)
```

**Description**: Same implicit string concatenation pattern.

**Severity**: LOW
**Category**: Style

---

## Recommendations

1. **MEDIUM**: Add type annotation for `model_config` in all Pydantic model classes:
   ```python
   model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
   ```
   Also import `ClassVar` from `typing`.

2. **LOW**: Consider using explicit line continuation or triple-quoted strings for multi-line error messages:
   ```python
   raise ValueError(
       f"{v} appears to be a placeholder value. Replace with your actual value."
   )
   ```
   Or:
   ```python
   raise ValueError(
       f"{v} appears to be a placeholder value. "
       "Replace with your actual value."
   )
   ```

3. Consider adding `from __future__ import annotations` if not already present to ensure consistent type annotation behavior.