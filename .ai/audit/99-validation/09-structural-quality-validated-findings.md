# Phase 09 Audit Findings — Structural Code Quality (Validated)

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** yes
**Validator:** validator

---

## Findings

### STR-001: Critical Nesting Depth in _tokenize

| Field | Value |
|-------|-------|
| **ID** | STR-001 |
| **Severity** | CRITICAL |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `_tokenize` method in PatternParser class has a maximum nesting depth of 7, far exceeding the recommended limit of 3. This method contains deeply nested conditionals for character classification and token building.

**Evidence:**
```
src\mko_telebot\core\parser.py:105 _tokenize - nesting depth 7
```

**Validation Note:**
> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** Nesting depth claim is inaccurate. The `_tokenize` method has max nesting depth of 4 (outer while + inner while in else branch = 2 levels; if/elif chain adds conditional branches but not nesting). The radon output shows complexity=9, not nesting depth 7. However, the nesting is still moderate and refactoring with early returns would improve readability.
> - **See also:** None

**Recommendation:** In `parser.py`, refactor `_tokenize` (lines ~105-180) using early returns and extraction:

```python
# Extract character classification to helper:
def _classify_char(self, char: str) -> str:
    """Return 'SPACE', 'SPECIAL', or 'LITERAL' for character type."""
    if char.isspace():
        return "SPACE"
    if char in "*?.[](){}|":
        return "SPECIAL"
    return "LITERAL"

# In _tokenize, use dispatch on classification:
classification = self._classify_char(char)
if classification == "SPACE":
    # handle space - no nesting
    continue  # or early return logic
if classification == "SPECIAL":
    # handle special - extract to _handle_special()
    return self._handle_special(char)
# LITERAL case continues inline
```

This reduces nesting by extracting logic into separate methods.

---

### STR-002: High Cyclomatic Complexity in search_match

| Field | Value |
|-------|-------|
| **ID** | STR-002 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `search_match` function has cyclomatic complexity of 15 (rank C), exceeding threshold of 10. Spanning 77 lines with nesting depth 4 and 7 return statements, this function handles parsing, exclusion checking, inclusion evaluation, and error handling together.

**Evidence:**
```
src\mko_telebot\core\parser.py
    F 325:0 search_match - C (15)
```

**Recommendation:** In `parser.py` lines ~325-402, split `search_match` into focused functions:

```python
# extract parse_query():
def parse_query(query: str) -> tuple[list[str], list[str]]:
    """Parse query into inclusion and exclusion keyword lists."""
    # Extract lines handling -i flag parsing (lines ~325-350)

# extract evaluate_query():
def evaluate_query(text: str, inclusion: list[str], exclusion: list[str]) -> bool:
    """Check if text matches inclusion keywords and no exclusions."""
    # Extract matching logic (lines ~350-402)
    
# Each function has single responsibility and single return
```

This separates parsing from evaluation, reducing complexity from 15 to ~8 per function.

---

### STR-003: High Cyclomatic Complexity in forward_to_users

| Field | Value |
|-------|-------|
| **ID** | STR-003 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `forward_to_users` function has cyclomatic complexity of 12 (rank C), exceeding threshold of 10. It has 6 parameters, 65 lines, nesting depth 4, and uses `for...else` anti-pattern.

**Evidence:**
```
src\mko_telebot\monitor.py
    F 120:0 forward_to_users - C (12)
    nesting depth 4, 65 lines, 6 parameters
```

**Recommendation:** In `monitor.py` lines ~120-185, extract helpers to reduce complexity:

```python
# Extract build_caption (lines 138-146):
def build_caption(msg_text: str, sender_tag: str, link: str) -> str:
    """Build forward caption with author and source link."""
    lines = []
    if msg_text:
        lines.append(msg_text)
    if sender_tag:
        lines.append(f"Author: {sender_tag}")
    if link:
        lines.append(f"Source: {link}")
    return "\n\n".join(lines).strip()

# Extract send_with_retry (lines 149-182):
async def send_with_retry(client: TelegramClient, target: Any, caption: str, msg_media: list) -> bool:
    """Send message with exponential backoff retry. Returns True on success."""
    # Replace for...else with explicit success flag
    for attempt in range(max_tries):
        try:
            if msg_media:
                await client.send_file(target, msg_media, caption=caption, link_preview=False)
            else:
                await client.send_message(target, caption, link_preview=False)
            return True  # success - early return replaces break
        except FloodWaitError as e:
            # existing retry logic
            ...
    return False  # failure - replaces else clause

# In forward_to_users:
caption = build_caption(msg_text, sender_tag, link)
success = await send_with_retry(client, target, caption, msg_media)
if not success:
    logger.error(f"Failed to send to {target} after {max_tries} attempts")
```

---

### STR-004: High Cyclomatic Complexity in process_messages

| Field | Value |
|-------|-------|
| **ID** | STR-004 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `process_messages` function has cyclomatic complexity of 13 (rank C), exceeding threshold of 10. With nesting depth 4, it combines message grouping, keyword matching, and forwarding concerns.

**Evidence:**
```
src\mko_telebot\monitor.py
    F 187:0 process_messages - C (13)
```

**Recommendation:** In `monitor.py` lines ~187-230, extract `group_album_messages`:

```python
# Extract at top of file (no imports needed):
def group_album_messages(messages: list[Message]) -> dict[int, dict]:
    """Group messages by grouped_id (album) or message id (single).
    
    Returns dict mapping album_id -> {'msg': Message, 'text': [str], 'media': [Media]}
    """
    msg_content: dict[int, dict] = {}
    for msg in messages:
        group_id = msg.grouped_id if getattr(msg, "grouped_id", None) else msg.id
        if group_id not in msg_content:
            msg_content[group_id] = {"msg": msg, "text": [], "media": []}
        if getattr(msg, "message", None):
            msg_content[group_id]["text"].append(msg.message)
        if getattr(msg, "media", None):
            if getattr(msg.media, "caption", None):
                msg_content[group_id]["text"].append(msg.media.caption)
            msg_content[group_id]["media"].append(msg.media)
    return msg_content

# In process_messages (line 199):
msg_content = group_album_messages(messages)
# Remove lines 201-214 (current grouping logic)
```

This separates grouping logic from keyword matching, reducing function complexity.

---

### STR-005: File Exceeds Maximum Length (parser.py)

| Field | Value |
|-------|-------|
| **ID** | STR-005 |
| **Severity** | HIGH |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `parser.py` file spans 401 lines, exceeding the 300-line threshold for god modules. Contains AST nodes, PatternParser class, and matcher functions.

**Evidence:**
```
src\mko_telebot\core\parser.py - 401 lines total
```

**Recommendation:** Split `parser.py` into three modules:

```
core/parser.py    # PatternParser class with _tokenize method (~150 lines)
core/matcher.py   # search_match and helper functions (~100 lines)  
core/ast_nodes.py # AST node constants and types (~50 lines)

# Extract:
# - Lines 1-50: AST node constants -> ast_nodes.py
# - Lines 52-200: PatternParser._tokenize -> parser.py (already there)
# - Lines 201-401: search_match, patterns_for_node, ast_to_regex -> matcher.py
# Update imports in core/__init__.py to re-export from new modules
# Update imports in monitor.py to point to matcher.search_match
```

This follows the project's "small modules and functions" principle.

---

### STR-006: File Exceeds Maximum Length (monitor.py)

| Field | Value |
|-------|-------|
| **ID** | STR-006 |
| **Severity** | MEDIUM |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `monitor.py` file spans 356 lines, exceeding the 300-line threshold. Contains client creation, message processing, forwarding, scheduling, and main loop.

**Evidence:**
```
src\mko_telebot\monitor.py - 356 lines total
```

**Recommendation:** Split `monitor.py` into focused modules:

```
monitor.py       # main_loop, run_monitor entry point (~100 lines)
monitor_forward.py # forward_to_users, process_messages, process_task (~150 lines)
monitor_client.py  # create_client, start_client (~50 lines)

# Extract:
# - Lines 24-68: client creation functions -> monitor_client.py
# - Lines 120-228: forwarding functions -> monitor_forward.py  
# - Lines 231-356: task processing and loop -> monitor_forward.py + monitor.py
# Update imports in core/__init__.py to: from .monitor_forward import forward_to_users, process_messages, process_task
```

This aligns with the "small modules and functions" architecture principle.

---

### STR-007: Multiple Issues in patterns_for_node

| Field | Value |
|-------|-------|
| **ID** | STR-007 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `patterns_for_node` function has 6 return statements and nesting depth 4, making control flow harder to follow.

**Evidence:**
```
src\mko_telebot\core\parser.py:290 patterns_for_node - 6 return statements, nesting depth 4
```

**Validation Note:**
> **Validation Note:**
> - **Action:** rejected
> - **Detail:** Nesting depth claim is inaccurate. The function has max nesting depth of 2 (single if/return chain inside function body). Return statement count (6) is technically correct but this pattern is idiomatic for type-dispatch functions and does not impede maintainability. Multiple early returns in a dispatch function of 14 lines provides cleaner control flow than accumulating and returning at the end.
> - **See also:** None
 
**Recommendation:** No action required - STR-007 is rejected as early returns in type-dispatch functions are idiomatic and maintainable.

---

### STR-008: Multiple Issues in ast_to_regex

| Field | Value |
|-------|-------|
| **ID** | STR-008 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/parser.py |
| **Classification** | advisory |

**Description:** The `ast_to_regex` function has 5 return statements, exceeding the recommended limit of 3.

**Evidence:**
```
src\mko_telebot\core\parser.py:249 ast_to_regex - 5 return statements
```

**Validation Note:**
> **Validation Note:**
> - **Action:** rejected
> - **Detail:** Similar to STR-007, this is a type-dispatch function where early returns are idiomatic. The function is 25 lines with clear pattern matching. Multiple return statements are appropriate here for readability; consolidating would unnecessarily complicate the logic.
> - **See also:** STR-007 (related pattern)
> - **Cross-phase note:** QLT-005 (Phase 08) correctly identifies broad Exception catches as a separate concern.

---

### STR-009: for...else Anti-pattern

| Field | Value |
|-------|-------|
| **ID** | STR-009 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/monitor.py |
| **Classification** | advisory |

**Description:** The `forward_to_users` function uses `for...else` at lines 151-182. The `else` clause executes when the loop completes without hitting `break`, which is confusing and error-prone.

**Evidence:**
```python
for attempt in range(max_tries):
    try:
        await client.send_file(...) or await client.send_message(...)
        break
    except FloodWaitError as e:
        wait_time = e.seconds + random.uniform(5, 10) + (2 ** attempt)
        await asyncio.sleep(wait_time)
    except RPCError as e:
        wait_time = (2 ** attempt) + random.uniform(0, 3)
        await asyncio.sleep(wait_time)
else:
    logger.error("Failed to send...")
```

**Recommendation:** Part of STR-003 refactoring. Replace the `for...else` with explicit success flag in the extracted `send_with_retry` function:

```python
success = False
for attempt in range(max_tries):
    try:
        if msg_media:
            await client.send_file(target, msg_media, caption=caption, link_preview=False)
        else:
            await client.send_message(target, caption, link_preview=False)
        success = True
        break
    except (FloodWaitError, RPCError) as e:
        # existing retry logic
        ...
if not success:
    logger.error(f"Failed to send to {target} after {max_tries} attempts")
```

This is addressed by the STR-003 `send_with_retry` helper extraction.

---

### STR-010: UTF-8 BOM in File

| Field | Value |
|-------|-------|
| **ID** | STR-010 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/__init__.py |
| **Classification** | advisory |

**Description:** The `core/__init__.py` file contains a UTF-8 BOM character (U+FEFF), causing radon analysis to fail with "invalid non-printable character" error.

**Evidence:**
```
src\mko_telebot\core\__init__.py
    ERROR: invalid non-printable character U+FEFF (<unknown>, line 1)
```

**Recommendation:** Remove UTF-8 BOM from `core/__init__.py`:

```bash
# Unix/Linux command:
sed -i '1s/^xEFxBBxBF//' src/mko_telebot/core/__init__.py

# Or in Python:
with open("src/mko_telebot/core/__init__.py", "rb") as f:
    content = f.read()
if content.startswith(b'\xef\xbb\xbf'):
    with open("src/mko_telebot/core/__init__.py", "wb") as f:
        f.write(content[3:])
```

This ensures radon and other tools can parse the file correctly.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 1 |
| LOW | 2 |

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 7 | STR-002, STR-003, STR-004, STR-005, STR-006, STR-009, STR-010 |
| Reclassified | 1 | STR-001 |
| Merged | 0 | — |
| Rejected | 2 | STR-007, STR-008 |

---

## Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| STR-007 | Multiple Issues in patterns_for_node | Nesting depth claim (4) is inaccurate; function has max depth of 2. Early returns are idiomatic for type-dispatch functions and improve readability. |
| STR-008 | Multiple Issues in ast_to_regex | Early returns are idiomatic for type-dispatch functions (5 return statements across 25 lines). Consolidating would add unnecessary complexity. |

---

## Merged Findings

None.

---

## Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|-----------|
| STR-001 | BEST-PRACTICE | BEST-PRACTICE | Nesting depth claim was inaccurate (actually ~4, not 7), but complexity concern remains valid. |

---

## Architectural Assessment

### Potential Risks

1. **STR-005/STR-006 (file length)**: Medium risk. Splitting `parser.py` and `monitor.py` requires careful consideration of module boundaries. The project follows "small modules and functions" principle, but changes must preserve the clean separation between parser logic and monitor orchestration.

2. **STR-002 (search_match complexity)**: Medium risk. Refactoring this core matching function requires ensuring tests continue to pass and behavior remains unchanged.

### Cross-Phase Conflict Detection

No cross-phase conflicts detected with these structural findings. Phase 08 quality findings (QLT-005) correctly identifies broad Exception catches as a separate concern in `parser.py`.

### Dependency Analysis

Module splitting would create new import dependencies but follow existing patterns (e.g., existing `core/__init__.py` re-exports from submodules). Risk is low with proper incremental changes.

### Rollout Safety

File splits and refactoring are isolated code quality improvements:
- No runtime behavior changes
- Type hint additions are backward compatible
- BOM removal is safe
- Refactoring should maintain full test coverage