---
name: parser-dead-code
description: Unreachable code in PatternParser._parse_and_expr
---

# Bug Report: Unreachable Code in PatternParser._parse_and_expr

**Status:** FOUND
**Severity:** LOW
**Type:** RUNTIME-ERROR (unreachable code)

## Description

In `src/mko_telebot/core/parser.py`, line 150 contains unreachable code. The condition `if nxt is None: break` inside `_parse_and_expr` can never be reached due to the logic in `_parse_term`.

## Evidence

File: `src/mko_telebot/core/parser.py`, lines 139-154

```python
def _parse_and_expr(self) -> ASTNode:
    first = self._parse_term()
    elems = [first] if first is not None else []
    while True:
        tok = self._peek()
        # Stop if next token ends the sequence context
        if not tok or tok[0] in ("OR", "GROUP_END", "EXCLUDE"):  # line 146
            break
        nxt = self._parse_term()
        if nxt is None:  # line 150 - UNREACHABLE
            break
        elems.append(nxt)
```

The `_parse_term` method returns `None` only when:
1. No token exists (line 163-164) - caught by `if not tok` on line 145
2. For unexpected tokens (line 179-181) - but these are all GROUP_END tokens, which are already in the stop set

For GROUP_START tokens, `_parse_term` always returns a valid ASTNode (either the inner expression or Sequence([])). For TERM tokens, it always returns ExactMatch or Wildcard.

## Impact

No functional impact - the code is never executed. However, this represents:
- Unnecessary code complexity
- Potential confusion for maintainers
- Missed opportunity to validate input structure

## Recommendation

Remove the unreachable code block on lines 149-150, or refactor to make the None check meaningful:

```python
# Option 1: Remove dead code
while True:
    tok = self._peek()
    if not tok or tok[0] in ("OR", "GROUP_END", "EXCLUDE"):
        break
    nxt = self._parse_term()  # Always returns non-None
    elems.append(nxt)

# Option 2: Add validation for empty groups
# Return None for empty groups instead of Sequence([])
```

## Test Coverage

Coverage report shows line 150 is never executed:
```
src\mko_telebot\core\parser.py        100      1    99%   150
```