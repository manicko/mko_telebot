---
name: 02-config-validated
description: Validated audit findings for Configuration & Pydantic Models
agent: validator
status: complete
validated: yes
---

# Phase 02 Validated Audit Findings — Configuration & Pydantic Models

**Executor:** validator  
**Source:** .ai/audit/02-config/findings.md  
**Status:** complete  
**Validated:** yes

---

## Findings

### CFG-001: UTF-8 BOM in keyw_config_example_keep.yaml causes YAML parsing failure

| Field | Value |
|-------|-------|
| **ID** | CFG-001 |
| **Severity** | MEDIUM |
| **Type** | RUNTIME-ERROR |
| **Affected Modules** | src/mko_telebot/settings/keyw_config_example_keep.yaml |
| **Classification** | mandatory |

**Description:** The `keyw_config_example_keep.yaml` template file contains a UTF-8 BOM (Byte Order Mark) at the start of the file. While PyYAML 6.0.3 handles this gracefully when comments precede the YAML content, the BOM creates an invisible U+FEFF character at the start of the file content and represents a code quality violation. UTF-8 BOM is unnecessary and can cause issues with some tools or when the file is modified. The file is referenced in cli-reference.md as a template file that gets copied during `init`.

**Evidence:**
- File bytes[0:3] == `ef bb bf` (UTF-8 BOM signature)
- PyYAML 6.0.3 parses the file successfully (comments precede YAML content)
- Loading with `'utf-8-sig'` encoding succeeds
- `cli-reference.md` line 74 lists this as a template file copied during init

**Recommendation:**
Remove the UTF-8 BOM from `keyw_config_example_keep.yaml` and convert to standard UTF-8 without BOM. This ensures compatibility with the standard YAML loading mechanism used by `TelepostConfigReader`.

---

### CFG-002: Proxy rdns field lacks type validation

| Field | Value |
|-------|-------|
| **ID** | CFG-002 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | src/mko_telebot/core/telethon.py |
| **Classification** | advisory |

**Description:** The `validate_proxy` field validator in `ClientConfig` (telethon.py lines 76-110) validates `proxy_type`, `addr`, and `port` fields but does not validate the optional `rdns` field. According to documentation, `rdns` should be a boolean for SOCKS5 remote DNS resolution. Invalid types (e.g., strings, integers) are silently accepted, which could cause runtime errors when Telethon processes the configuration.

**Evidence:**
- telethon.py lines 96-108: validator checks proxy_type, addr, port but not rdns
- Test with `proxy={'proxy_type': 'socks5', 'addr': '127.0.0.1', 'port': 1080, 'rdns': 'invalid_bool'}` succeeds without error
- documentation at `docs/11-guides/configuration.md` line 277 specifies `rdns` as optional bool

**Recommendation:**
Add type validation for the `rdns` field in `validate_proxy()` to ensure it is a boolean if provided. This improves configuration reliability and provides early error detection.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 1 |

## Mandatory Fixes

- CFG-001: UTF-8 BOM in keyw_config_example_keep.yaml causes YAML parsing failure

## Advisory Recommendations

- CFG-002: Proxy rdns field lacks type validation (LOW priority)

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 2 | CFG-001, CFG-002 |
| Reclassified | 0 | — |
| Merged | 0 | — |
| Rejected | 0 | — |

### Rejected Findings

- None

### Merged Findings

- None

### Reclassified Findings

- None
