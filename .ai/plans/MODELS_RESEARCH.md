# Models Organization Research Report

## Current State Analysis

### File Locations (mko_telebot)

| File | Lines | Contains |
|------|-------|----------|
| `core/telethon_models.py` | 87 | `ClientConfig`, `TelethonConfig` classes |
| `core/chats_config.py` | 93 | `LogLevel` (StrEnum), `ChannelConfig`, `ChannelDefaults`, `ChatsConfig` |
| `core/models.py` | 36 | `TelepostSettings` (root model) |
| `core/errors.py` | 27 | Exception classes |
| `core/__init__.py` | 28 | Re-exports |

### Critical Naming Issue Identified

**Telegram terminology clarification**: In Telegram API, "chat" and "channel" are **synonyms**. A Telegram channel IS a chat entity.

**Current misleading naming**:
- File `chats_config.py` - should be `channels_config.py` (content is about monitoring channels)
- Class `ChatsConfig` - should be `ChannelsConfig` (holds channel monitoring configuration)
- The alias `MONITORING` in `models.py` maps to `ChatsConfig` - semantically incorrect

**Correct naming pattern** (based on actual functionality):
- `ChannelConfig` - configures a monitored Telegram channel (CORRECT)
- `ChannelDefaults` - defaults for channel configuration (CORRECT)
- `ChatsConfig` → `ChannelsConfig` - holds dictionary of channels to monitor (NEEDS RENAME)

---

## Modern Best Practices Research (2024-2025)

### File Naming Conventions

**Recommended Pattern**: One file per domain concept

- `user.py` for `User` model
- `channel.py` for channel-related models
- `_enums.py` for shared enum types

### Model Naming Conventions

1. **Use domain-specific terminology**: Align names with the actual domain (Telegram channels, not "chats")
2. **Suffix for purpose**: `-Config`, `-Settings`, `-Defaults` clearly indicate purpose
3. **Container class naming**: `ChannelsConfig` for collections, `ChannelConfig` for individual entities

### File Size Guidelines

- **Small modules (<100 lines)**: Preferred for single responsibility
- **Current files**: Both model files are under 100 lines - acceptable

---

## Recommendations (Priority-Ordered)

### Recommendation 1: Fix Naming Inconsistency (Priority: HIGH - REQUIRED)

**Action Required**: Rename `ChatsConfig` to `ChannelsConfig` and file to `channels_config.py`

**Changes needed**:
1. Rename file: `core/chats_config.py` → `core/channels_config.py`
2. Rename class: `ChatsConfig` → `ChannelsConfig`
3. Update imports in `core/models.py` (line 7)
4. Rename field: `monitoring` → `channels` in `TelepostSettings` (models.py line 29)
5. Update validation_alias: `MONITORING` → `CHANNELS` (models.py line 31)
6. Update imports in `core/__init__.py` (line 7, 19)
7. Update YAML config templates: `MONITORING` → `CHANNELS`

**Reasoning**: The application monitors Telegram channels. "Chats" is ambiguous and misleading. Telegram API uses "channel" terminology consistently.

### Recommendation 2: Extract LogLevel Enum (Priority: MEDIUM)

**Action Optional**: Extract `LogLevel` to `core/_enums.py`

**Reasoning**: Could be reused by other components (logging configuration, future modules). Not strictly required if only used in channel monitoring context.

### Recommendation 3: Keep Root Model Pattern (Priority: LOW)

**Current**: `models.py` contains only `TelepostSettings`

**Keep as-is**: The root model aggregates child models correctly without business logic.

---

## Final Verdict

### Required Action (Single Priority)

**Rename `ChatsConfig` to `ChannelsConfig`** for semantic correctness:

1. Rename `chats_config.py` → `channels_config.py`
2. Rename `ChatsConfig` class → `ChannelsConfig`
3. Update all imports and references in codebase
4. Update YAML validation_alias: `MONITORING` → `CHANNELS`

### Files to Modify

```
src/mko_telebot/core/chats_config.py → channels_config.py
src/mko_telebot/core/models.py (import + field + alias)
src/mko_telebot/core/__init__.py (import + __all__ reference)
src/mko_telebot/settings/config.yaml (MONITORING → CHANNELS)
```

---

## References

- Pydantic documentation: https://pydantic.dev/docs/
- Telegram API: Channels and Chats are synonymous entity types
- Project standards: `.ai/context/python-code-standards.md`