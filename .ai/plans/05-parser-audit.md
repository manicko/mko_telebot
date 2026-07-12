# Type Check Audit Report: parser.py

## Summary
7 warnings identified. Primary concerns: unannotated class attributes and unused call results.

---

## Warnings

### 1. UNANNOTATED_CLASS_ATTRIBUTE - `PatternParser` class
**Location:** `__init__` method  
**Variable:** `query` attribute  
**Issue:** Type annotation required for attribute `query`  

### 2. UNANNOTATED_CLASS_ATTRIBUTE - `PatternParser` class
**Location:** `__init__` method  
**Variable:** `tokens` attribute  
**Issue:** Type annotation required for attribute `tokens`  

### 3. UNANNOTATED_CLASS_ATTRIBUTE - `PatternParser` class
**Location:** `__init__` method  
**Variable:** `token_pos` attribute  
**Issue:** Type annotation required for attribute `token_pos`  

### 4. UNKNOWN_MEMBER_TYPE - `_tokenize` method
**Location:** `_tokenize` method  
**Variable:** `tokens.append` calls  
**Issue:** Type of `append` is partially unknown when building token list  

### 5. UNKNOWN_VARIABLE_TYPE - `_tokenize` method
**Location:** `_tokenize` method  
**Variable:** Return statement for `tokens`  
**Issue:** Return type `list[Unknown]` is partially unknown  

### 6. UNUSED_CALL_RESULT - `parse` method
**Location:** `parse` method  
**Variable:** `self._consume("EXCLUDE")` call  
**Issue:** Result of call expression `tuple[str, str] | None` is not used  

### 7. UNUSED_CALL_RESULT - `parse` method
**Location:** `parse` method  
**Variable:** Multiple `_consume` calls  
**Issue:** Results from `_consume("EXCLUDE")`, `_consume("OR")`, `_consume("GROUP_START")`, `_consume()` are discarded without assignment  

---

## Note on DEAD_CODE warnings
**Location:** `parse` method, `_parse_term` method  
**Variable:** `if query is None` check and subsequent `clean == ""` check  
**Issue:** Condition will always evaluate to False since the parameter type `str` doesn't include `None`. The `query is None` check creates unreachable code because the type signature already enforces `query: str`. However, the function signature was changed to accept only `str`, making the None check dead code.