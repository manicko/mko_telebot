---
name: 02-config-audit-findings
description: Audit findings for configuration and Pydantic models phase
agent: auditor
status: complete
validated: no
---

# Phase 02 Audit Findings — Configuration & Pydantic Models

**Executor:** auditor
**Template:** .ai/audit/templates/audit-findings.md
**Status:** complete
**Validated:** no

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

**Description:** The `keyw_config_example_keep.yaml` template file contains a UTF-8 BOM (Byte Order Mark) at the start of the file. When this file is copied to the user config directory and loaded via `yaml.safe_load()` in `_load_yaml()` (config.py line 66), it raises `yaml.parser.ParserError: expected '<document start>', but found '<block mapping start>'`. This prevents users from using this file as a configuration template. The file is referenced in cli-reference.md as a template file that gets copied during `init`.

**Evidence:**
- File `src/mko_telebot/settings/keyw_config_example_keep.yaml` bytes[0:3] == `b'\xef\xbb\xbf'` (UTF-8 BOM)
- Attempting `yaml.safe_load(open(..., 'r'))` fails with parser error: "expected '<document start>', but found '<block mapping start>'"
- Loading with `'utf-8-sig'` encoding succeeds
- docs/99-reference/cli-reference.md line 74 lists this as a template file copied during init

**Recommendation:** Remove the UTF-8 BOM from `keyw_config_example_keep.yaml` and convert to standard UTF-8 without BOM. This ensures compatibility with the standard YAML loading mechanism used by `TelepostConfigReader`.

**Effort:** trivial
**Priority:** recommended

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
- `telethon.py` lines 96-108: validator checks proxy_type, addr, port but not rdns
- Test with `proxy={'proxy_type': 'socks5', 'addr': '127.0.0.1', 'port': 1080, 'rdns': 'invalid_bool'}` succeeds without error
- Documentation at `docs/11-guides/configuration.md` line 277 specifies `rdns` as optional bool

**Recommendation:** Add type validation for the `rdns` field in `validate_proxy()` to ensure it is a boolean if provided. This improves configuration reliability and provides early error detection.

**Effort:** small
**Priority:** recommended

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

- CFG-002: Proxy rdns field lacks type validation