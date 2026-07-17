### STR-003: `core/task.py` is the only file approaching the file-length budget (380 lines)

| Field | Value |
|-------|-------|
| **ID** | STR-003 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/task.py` |
| **Classification** | advisory |

**Description:** `core/task.py` is 380 lines — the largest source file in the project and well above the 300-line industry reference budget. radon raw reports 206 blank lines out of 380 (54% blank), so the logical content is smaller, but the file still aggregates many responsibilities: entity resolution (`resolve_targets_entities`, `resolve_channel_entity`, `resolve_state_file`), state persistence (`load_state`, `save_state`, `set_offset_date`), and config/offset math. This is the only file where a future reader must scroll extensively to understand one cohesive unit.

**Evidence:**
```
radon raw src/mko_telebot/core/task.py
    LOC: 380   LLOC: 122   SLOC: 138   Blank: 206
Longest functions (all within budget):
    resolve_targets_entities  len=63  (depth 4)
    load_state                len=39  (depth 4)
```

**Recommendation:** No urgent action required (functions are small and MI rank is A at 60.93). If the `Task` class keeps growing, prefer splitting state-persistence helpers (`load_state`/`save_state`/`resolve_state_file`) into a `core/state.py` module rather than letting `task.py` cross 400+ lines. This keeps module responsibilities single-purpose per the project's "small modules" rule. Effort: small (if/when needed). Priority: recommended.

---

### STR-004: Depth-4 nesting in parser `PatternParser` helpers is acceptable but worth noting

| Field | Value |
|-------|-------|
| **ID** | STR-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/core/parser.py` |
| **Classification** | advisory |

**Description:** `PatternParser._tokenize` (lines 55–93) and `PatternParser.parse` (lines 112–138) both reach nesting depth 4. In `_tokenize` the deepest level is the inner `while` at column 16 (reading a TERM until a special char). In `parse` the depth comes from the `while` → `if EXCLUDE` → nested `if excl` chain. Neither is arrow code — both use early structure and are readable — but they are the deepest nesting points in the codebase and the parser already carries several B-rank complexity methods (`_tokenize`=9, `_parse_and_expr`=7, `_parse_term`=7, `parse`=6).

**Evidence:**
```
src/mko_telebot/core/parser.py:55  _tokenize   depth=4  cc=9 (B)
src/mko_telebot/core/parser.py:112 parse       depth=4  cc=6 (B)
radon cc src/mko_telebot/core/parser.py  => PatternParser MI rank A (58.20)
```

**Recommendation:** No change required now. If parser complexity keeps rising, consider extracting the TERM-reading inner loop in `_tokenize` into a `_read_term(q, i)` helper returning `(term, new_i)` to flatten the nesting to depth 3 and make the scanner trivially testable. Effort: small. Priority: recommended (monitor only).

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 2 |

## Mandatory Fixes

None. No security, data-loss, or correctness defects were identified in this phase.

## Advisory Recommendations

- **STR-003** — Monitor `core/task.py` size (380 lines); split state-persistence helpers if it grows further.
- **STR-004** — Flatten `_tokenize` inner TERM loop if parser complexity rises further.

## Doc Updates Needed

None required. The code conforms to the documented "small modules and functions" rule; no spec divergence found.