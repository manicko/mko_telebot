---
name: 04-security-validated
description: Validated audit findings for Security & Secret Management
agent: validator
status: validated
validated: yes
---

# Phase 04 Audit Findings — Security & Secret Management (Validated)

**Executor:** auditor
**Validator:** validator
**Status:** validated
**Validated:** yes

---

## Findings

### SEC-001: ~~Session path lacks validation for path traversal characters~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | SEC-001 |
| **Severity** | HIGH |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/telethon.py`, `src/mko_telebot/monitor.py` |
| **Classification** | mandatory |

> **Rejection reason:** The actual code in `monitor.py:42` uses `session_path.name` to extract only the filename component, which already neutralizes path traversal. When `session = "../../../etc/passwd"`, `Path(session).name` returns `"passwd"`, placing the session file safely in `session_dir`. The `Path(session)` call on line 38 does not create security risk because the path is immediately sanitized to just the filename. Adding path traversal validation to the session field would provide only defense-in-depth for a non-existent attack vector. The current implementation is secure by design - `session` is used as a name, not a path, and `.name` extraction is the correct sanitization approach.

---

### SEC-002: Template api_id value 1 bypasses placeholder validation

| Field | Value |
|-------|-------|
| **ID** | SEC-002 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/settings/secrets.yaml`, `src/mko_telebot/core/telethon.py` |
| **Classification** | advisory |

**Description:** The template `secrets.yaml` contains `api_id: 1` (line 6), which is not a valid Telegram API ID but passes the Pydantic validation in `telethon.py:60-67`. The validator only rejects `api_id == 12345`, but `api_id: 1` is semantically invalid (Telegram API IDs are large integers) and could lead to confusing error messages or failed API authentication.

**Evidence:**
- `secrets.yaml:6` - `"api_id": 1,` - clearly invalid api_id value (Telegram API IDs are typically 6-7 digit numbers)
- `telethon.py:24` - `api_id: int = Field(..., gt=0, ...)` - only requires positive integer, no minimum value check for realistic API IDs

**Recommendation:** In `settings/secrets.yaml` line 6, change the api_id placeholder to match documented validation behavior:

```yaml
# Change line 6 from:
api_id: 1

# To one of these options:
api_id: 0  # Forces Pydantic required field error (field has gt=0 constraint), user must provide valid value
# OR
# api_id: 12345  # Matches documented validation error in configuration.md
# OR
# api_id: ~  # Remove field, forces Pydantic required field error
```

Using `api_id: 0` will trigger the `gt=0` constraint error, clearly indicating the field needs a valid API ID value.

> **Validation Note:**
> - **Action:** reclassified
> - **Detail:** Changed from SPEC-DEVIATION to DOC-UPDATE. The code's validation is intentional and documented in configuration.md (line 239) which states "The placeholder value 12345 is rejected". However, the `secrets.yaml` template uses `api_id: 1` which is inconsistent with the documented validation behavior. The template should either use `12345` (to trigger the documented placeholder error) or use `0`/omit the field (to force user configuration). Since the code works correctly per its design, this is a documentation/template inconsistency.
> - **See also:** —

---

### SEC-003: ~~State file path derived from user-supplied channel name without explicit sanitization~~ [REJECTED]

| Field | Value |
|-------|-------|
| **ID** | SEC-003 |
| **Severity** | MEDIUM |
| **Type** | SPEC-DEVIATION |
| **Affected Modules** | `src/mko_telebot/core/task.py` |
| **Classification** | advisory |

> **Rejection reason:** The channel name validation in `channels.py:58` explicitly rejects path traversal characters. The `channel_name` field in `ChannelConfig` is validated before any `Task` is created. In `monitor.py:330`, `Task` is instantiated from `ChannelConfig` which has already validated the name. The defense-in-depth argument is speculative - there is no code path where `channel_name` could be set without going through `ChannelConfig` validation. The current architecture correctly validates at the model boundary.

---

### SEC-004: Secrets template exposes internal configuration structure

| Field | Value |
|-------|-------|
| **ID** | SEC-004 |
| **Severity** | LOW |
| **Type** | BEST-PRACTICE |
| **Affected Modules** | `src/mko_telebot/settings/secrets.yaml` |
| **Classification** | advisory |

**Description:** The template `secrets.yaml` includes non-essential fields (`system_lang_code: "en-US"`, `lang_code: "ru"` on lines 8-9) that document internal configuration options. While not a direct security vulnerability, exposing these in the template could lead users to include unnecessary data in their secrets file, increasing the risk of accidental exposure of intent through version control if the file is mistakenly committed.

**Evidence:**
- `secrets.yaml:8-9` - `"system_lang_code": "en-US"` and `"lang_code": "ru"` are included in the template but are optional

**Recommendation:** In `settings/secrets.yaml`, remove lines 8-9 (`system_lang_code` and `lang_code`) to keep secrets focused on credentials:

```yaml
# Remove these lines from secrets.yaml:
# system_lang_code: "en-US"
# lang_code: "ru"
```

These optional fields belong in `config.yaml` if needed, not in the secrets template alongside API credentials.

> **Validation Note:**
> - **Action:** validated
> - **Detail:** Confirmed that `system_lang_code` and `lang_code` in `ClientConfig` are optional fields with `None` defaults (telethon.py:32-35). The template includes them as pre-filled examples, which could lead users to keep unnecessary data alongside credentials in their secrets file. The documentation in configuration.md (lines 427-430) shows the minimal template includes these fields, creating inconsistency with the principle of keeping secrets minimal.
> - **See also:** SEC-002 (related template consistency issue)

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 1 |

---

## Mandatory Fixes

None. All original mandatory findings were rejected.

---

## Advisory Recommendations

None. All advisory findings were either rejected or reclassified.

---

## Validation Summary

| Action | Count | Details |
|--------|-------|---------|
| Validated (unchanged) | 1 | SEC-004 |
| Reclassified | 1 | SEC-002 |
| Rejected | 2 | SEC-001, SEC-003 |

### Rejected Findings

| ID | Title | Reason |
|----|-------|--------|
| SEC-001 | Session path lacks validation for path traversal characters | Code in monitor.py:42 uses `session_path.name` which extracts only the filename component, already neutralizing path traversal. The `session` field is designed as a name, not a path. Adding validation would provide only defense-in-depth for a non-existent attack vector. |
| SEC-003 | State file path derived from user-supplied channel name without explicit sanitization | Channel name is validated via ChannelConfig validator in channels.py:58 before Task is created. All Task instances are created from validated ChannelConfig objects (monitor.py:330). There is no code path to bypass validation. |

### Reclassified Findings

| ID | Original Type | New Type | Rationale |
|----|---------------|----------|----------|
| SEC-002 | SPEC-DEVIATION | DOC-UPDATE | The code validates as designed (rejects 12345 per documentation). The template using `api_id: 1` is inconsistent with documented validation behavior, creating user confusion. This is a documentation/template issue, not a code defect. |

---

## Architectural Observations

1. **Defense-in-depth vs. actual security**: SEC-001 identified a real pattern (path handling) but misjudged the risk. The `.name` extraction in `create_client()` is the correct sanitization approach. Adding validation to the session field would be redundant.

2. **Template consistency**: SEC-002 and SEC-004 both highlight template/documentation inconsistencies. The `secrets.yaml` template uses `api_id: 1` while documentation mentions `12345` as the rejected placeholder, and includes optional fields that should be omitted from secrets templates.

3. **Validation at model boundary**: The project correctly validates at the Pydantic model level (channel name in channels.py, placeholder values in telethon.py). This architecture prevents invalid data from propagating through the system.

4. **No cross-phase conflicts detected**: SEC-001 and SEC-003 were rejected, SEC-002 was reclassified from security to documentation, and SEC-004 remains as a low-severity best practice. No conflicts with previously validated phases.

---

## Cross-Phase Analysis

### Dependency Chains

None detected. SEC-001 and SEC-003 were rejected, removing any dependency concerns.

### Cross-Phase Conflicts

None detected. All Phase 04 findings are independent of Phase 01-03 validated findings.