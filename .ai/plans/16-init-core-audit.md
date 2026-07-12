# basedpyright Audit Report: core/__init__.py

## Summary
- **File**: `src/mko_telebot/core/__init__.py`
- **Total Issues**: 1 (1 error, 0 warnings)

---

## Errors

### 1. CRITICAL - Import Cycle Detected (reportImportCycles)
**Line 1-29** - Circular dependency in import chain

**Issue**: The type checker detected an import cycle:
```
src/mko_telebot/core/__init__.py
→ src/mko_telebot/core/task.py (for Task import)
→ back to core/__init__.py
```

**Description**: The `core/__init__.py` imports `Task` from `task.py`, but `task.py` imports from `core/__init__.py` via:
- `from mko_telebot.core import utils` (line 12)
- `from mko_telebot.core.paths import APP_PATHS` (line 13)
- `from mko_telebot.core.channels import ChannelConfig` (line 15)

When `core/__init__.py` is imported, it tries to import `Task`, which triggers `task.py` to import from `mko_telebot.core`, which starts the cycle.

**Severity**: CRITICAL
**Category**: Architecture

**Impact**: This can cause:
- Runtime import errors in some scenarios
- Incomplete type information
- Difficult-to-debug initialization order issues

---

## Recommendations

1. **CRITICAL**: Refactor to break the import cycle. Options:

   **Option A - Direct imports in task.py** (preferred):
   ```python
   # In task.py, change:
   from mko_telebot.core import utils
   from mko_telebot.core.paths import APP_PATHS
   from mko_telebot.core.channels import ChannelConfig
   # To direct module imports:
   from mko_telebot.core.utils import ensure_path_exists
   from mko_telebot.core.paths import PathResolver, state_dir
   from mko_telebot.core.channels import ChannelConfig, state_dir
   ```

   **Option B - Move shared imports to separate module**:
   Create a `_shared.py` or `types.py` module that contains only type definitions and constants that both `__init__.py` and `task.py` can import without cycles.

   **Option C - Use lazy imports**:
   Defer the `Task` import in `__init__.py` to function-level imports where needed, or use `TYPE_CHECKING` imports.

2. The current structure mixes:
   - Public exports (`__all__`)
   - Internal imports
   This makes the package's public API unclear and creates coupling.