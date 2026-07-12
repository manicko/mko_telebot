# Type Checking Audit Report: src/mko_telebot/cli.py

**Tool:** basedpyright  
**Date:** 2026-07-12  
**File:** `src/mko_telebot/cli.py`

---

## Summary

| Severity | Count |
|----------|-------|
| Errors   | 0     |
| Warnings | 2     |
| Notes    | 0     |

---

## Findings

### [LOW] Warning: Function calls in parameter default value expression

**Location:** `init` function, parameter `force`  
**Code snippet:**
```python
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing user config files if they exist.",
    ),
) -> None:
```

**Description:**  
The `typer.Option()` call is used as a default value for the `force` parameter. The type checker warns that function calls and mutable objects are not allowed within parameter default value expressions. This pattern is commonly used in Typer CLI applications and is intentional, but static analysis tools flag it as potentially problematic because the default value is evaluated at import time.

**Impact:**  
This is a stylistic warning, not a functional issue. The code works correctly at runtime. However, for stricter type-checking workflows, this pattern can cause issues with some analyzers.

**Recommendation:**  
No immediate action required. Consider this pattern acceptable for Typer-based CLIs where this is idiomatic usage. If stricter compliance is needed, wrap in a lambda or use `typer.Option` with explicit type annotation.

---

### [LOW] Warning: Unused call result

**Location:** `init` function, line with `shutil.copy2(item, target)`  
**Code snippet:**
```python
shutil.copy2(item, target)
```

**Description:**  
The return value of `shutil.copy2()` is not being assigned to a variable. The function returns the path to the destination file (type `Path | str`), but the result is ignored. Basedpyright suggests assigning to `_` if this is intentional to make the code's intent clear.

**Impact:**  
This is a code quality warning. The copy operation still succeeds, but ignoring the return value may indicate missed error handling opportunities or unclear intent.

**Recommendation:**  
Change `shutil.copy2(item, target)` to `shutil.copy2(item, target)  # noqa: F841` or assign to `_` to explicitly indicate the return value is intentionally unused:
```python
_ = shutil.copy2(item, target)
```

---

## Appendix: Context

### Related symbols referenced in warnings

| Symbol | Module | Description |
|--------|--------|-------------|
| `init` | cli.py | CLI command for initializing user config directory |
| `force` | init parameter | Boolean flag for overwriting existing files |
| `item` | init loop variable | Path object iterating over source directory |
| `target` | init computed path | Destination path for config file copy |
| `typer.Option` | typer | CLI parameter option decorator |
| `shutil.copy2` | shutil | File copy function preserving metadata |