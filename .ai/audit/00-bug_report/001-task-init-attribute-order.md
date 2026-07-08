---
report_id: BUG-001
title: Task.__init__() calls set_offset_date() before state_file attribute is assigned
severity: LOW
type: RUNTIME-ERROR
affected_module: src/mko_telebot/core/task.py
detected_by: test_task.py::TestSetOffsetDate::test_returns_none_on_invalid_days
---

# Bug: `Task.__init__()` calls `set_offset_date()` before `state_file` is assigned

**Description:**
In `core/task.py`, `Task.__init__()` calls `self.set_offset_date()` at line 55, but `self.state_file` is not assigned until line 59. If `history_days` has an invalid (non-int) value, `set_offset_date()` enters the `except` handler and logs an error referencing `self.state_file` (line 115), which triggers an `AttributeError` because `state_file` hasn't been assigned yet.

**Trace:**
```
  self.offset_date = self.set_offset_date()       # line 55
                     → set_offset_date()           # line 106
                     → except (TypeError, ValueError)
                     → logger.error(f"...{self.state_file}")  # line 115, AttributeError!
```

**Impact:**
- LOW severity — only manifests when `history_days` has an invalid value.
- The invalid `history_days` case is already guarded by Pydantic validation on `ChannelConfig`, so this path is unreachable through normal config loading.
- However, the error message is misleading — instead of a clean log about invalid history_days, the user gets an AttributeError traceback.

**Fix:**
Move `self.state_file: Path | None = None` to before `self.offset_date = self.set_offset_date()` in `__init__()`, or guard the log line in `set_offset_date()` against `state_file` being `None`.

**File location:** `src/mko_telebot/core/task.py`, lines 55–59:
```python
# Current order (buggy):
self.offset_date = self.set_offset_date()    # line 55 — before state_file!
...
self.state_file: Path | None = None          # line 59

# Correct order:
self.state_file: Path | None = None          # assign first
self.offset_date = self.set_offset_date()    # safe to reference state_file
```