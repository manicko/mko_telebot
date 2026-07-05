# RESEARCH.md — Two-Level Chat Settings (Global Defaults + Per-Chat Overrides)

## Phase

Implement two-level chat settings: global defaults for all chats + per-chat overrides.
Per-chat settings override global defaults. Only `chat_id` is required per chat.

---

## 1. Problem Statement

**Current state:** `chats` is a flat `list[ChatConfig]` where every chat must specify
all fields (delay_minutes, delay_jitter_percent, max_photos, etc.) even when just
accepting defaults. There is no way to set global defaults once and only override
per-chat where needed.

**Desired state:**
1. **Global chat defaults** — one set of default values applied to all chats.
2. **Per-chat settings** — each chat can override any subset of fields.
   Only `chat_id` is required. Unspecified fields inherit from global defaults.

---

## 2. Current Architecture (Evidence)

### Config YAML (`app_config.yaml`)
```yaml
chats:
  - chat_id: -1001234567890
    topic_id: 0
    range_names:
      - "Sheet1!A1:Z100"
    delay_minutes: 10
    delay_jitter_percent: 30
    max_photos: 5
```

Every field in each chat entry is required even when the user just wants the default.

### `TelepostSettings` (root model)
```
chats: list[ChatConfig] = Field(default_factory=list, min_length=1)
```

### `ChatConfig` fields
| Field | Type | Default | Required? |
|-------|------|---------|-----------|
| `chat_id` | `int` | — | **Yes** (no default) |
| `chat_name` | `str \| None` | `None` | No |
| `topic_id` | `int` | `0` | No |
| `range_names` | `list[str]` | `[]` | No |
| `delay_minutes` | `float` | `10.0` | No |
| `delay_jitter_percent` | `int` | `30` | No |
| `max_photos` | `int` | `5` | No |
| `max_width` | `int` | `800` | No (TASK_025 adds this) |
| `max_height` | `int` | `800` | No (TASK_025 adds this) |

Note: After TASK_021, `delay_minutes` is renamed to `min_delay_minutes`.

### Key consumers of `ChatConfig`
- **`TelegramService.__init__`** — builds `_chat_configs: dict[int, ChatConfig]` lookup
- **`TelegramService._push_posts_to_queue`** — reads `chat.max_photos`, `chat.topic_id`, `chat.range_names`
- **`TelegramService._send_posts`** — reads delay settings via `DelayEngine.get_effective_delay(chat_config)`
- **`DelayEngine.get_per_chat_delay`** — reads `chat.min_delay_minutes` and `chat.delay_jitter_percent`
- **`PostProcessor.get_posts`** — passes `chat.max_width`/`chat.max_height` to `resize_image()` (TASK_025)
- **`app.py._show_config_summary`** — displays per-chat settings in CLI table
- **`config_reader.py`** — no post-processing of chats; validates and returns as-is

### Data flow
```
YAML file → yaml.safe_load → TelepostSettings(**raw_dict) → TelepostSettings.chats: list[ChatConfig]
```
There is **no merging step** today. Each `ChatConfig` is validated independently.

---

## 3. Existing Tasks That Modify ChatConfig (Dependency Constraints)

These tasks are `status: pending` in `.ai/tasks/todo/` and **must** be accounted for:

| Task | Change | Dependency |
|------|--------|------------|
| **TASK_021** | Rename `delay_minutes` → `min_delay_minutes` in `ChatConfig` | None (root) |
| **TASK_022** | Fix jitter to positive-only `uniform(0, +jitter)`, update `delay_jitter_percent` to `le=100` | TASK_021 |
| **TASK_023** | Update all docs/tests for the rename | TASK_021, TASK_022 |
| **TASK_025** | Add `max_width`/`max_height` fields to `ChatConfig` (defaults 800, ge=100, le=4096) | None (root) |

**Critical implication:** Any changes to `ChatConfig` field names/types/defaults must consider
the rename (TASK_021) and the new fields (TASK_025). The optimal sequencing is:
- Make the two-level architecture changes **after** TASK_021/TASK_025 so the defaults
  model can use the final field names and complete field set.
- Alternatively, slot the two-level architecture **before** TASK_021/TASK_025 so those
  tasks operate on the new structure.

**Recommendation:** Place the two-level architecture change as a prerequisite before
TASK_021 and TASK_025, so the `ChatDefaults` model and `ChatConfig` use the final
design from the start. This avoids double-modification of ChatConfig.

---

## 4. Modern Practice (Research Findings)

### 4.1 Pattern: "Defaults + Overrides" in Pydantic

The standard approach across the Python ecosystem (Confuse, Hydra/OmegaConf,
pydantic-settings) is:

1. **Define a defaults model** with all fields optional and sensible defaults
2. **Define per-item model** where identifier is required, other fields are `Optional[T]` with `default=None`
3. **Merge at the root level** using a `model_validator(mode='before')` or `mode='after'`) that fills `None` values from defaults

**Pydantic's `model_validator(mode='before')`** runs on raw dict input before
validation, making it perfect for injecting defaults from a sibling config block.

**Confidence: HIGH** — verified from Pydantic v2 docs and test examples.

### 4.2 Pattern: Confuse Library's View-Based Override

Confuse (used by beets) implements transparent layered configuration:
- Default config (`config_default.yaml`) provides baseline
- User config overrides at the same granularity
- Resolution: user value wins if present, otherwise default

This is the same semantic we need: global chat defaults = Confuse defaults,
per-chat = user overrides.

**Confidence: HIGH** — verified from Confuse 2.2 docs.

### 4.3 Pattern: YAML Structure Options for Two-Level Config

Three common YAML patterns:

**Option A: Separate `defaults` key (RECOMMENDED)**
```yaml
chats:
  defaults:
    min_delay_minutes: 10
    delay_jitter_percent: 30
    max_photos: 5
  list:
    - chat_id: -1001234567890
      range_names: ["Sheet1!A1:Z100"]
    - chat_id: -1009876543210
      min_delay_minutes: 20
      range_names: ["Sheet2!A1:Z50"]
```
Pros: Clean separation, defaults are self-documenting, easy to add/remove defaults
Cons: Changes YAML structure (breaking change)

**Option B: Keep `chats` as list of dicts + add `chat_defaults` sibling**
```yaml
chat_defaults:
  min_delay_minutes: 10
  delay_jitter_percent: 30
  max_photos: 5

chats:
  - chat_id: -1001234567890
    range_names: ["Sheet1!A1:Z100"]
```
Pros: Non-breaking for existing configs (defaults section is optional)
Cons: Splits chat config across two top-level keys

**Option C: Keep flat list, first chat is "template" (anti-pattern)**
Pros: No structure change
Cons: Implicit, error-prone, confusing semantics

**Recommendation: Option A** — the project already requires a config migration for
the rename (TASK_021), so combining the structure change with the rename minimizes
total migration effort. Users already need to update their YAML.

### 4.4 Merge Strategy

**Approach: `model_validator(mode='after')` on `TelepostSettings`**

After Pydantic validates the raw dict into `TelepostSettings`, the validator
resolves each chat's `None` fields from `chats.defaults`:

```python
@model_validator(mode='after')
def resolve_chat_defaults(self) -> "TelepostSettings":
    defaults = self.chats.defaults
    for chat in self.chats.list:
        if chat.min_delay_minutes is None:
            chat.min_delay_minutes = defaults.min_delay_minutes
        if chat.delay_jitter_percent is None:
            chat.delay_jitter_percent = defaults.delay_jitter_percent
        # ... etc for each overridable field
    return self
```

This approach:
- Keeps the merge logic testable and explicit
- Happens after Pydantic validation, so defaults model is already validated
- Does not require custom YAML loading or post-processing
- Works with Pydantic's `validate_assignment=True` on `TelepostSettings`

**Confidence: HIGH** — follows Pydantic's documented `model_validator(mode='after')` pattern.

---

## 5. Recommended Design

### 5.1 New Model: `ChatDefaults`

```python
class ChatDefaults(BaseModel):
    """Default settings applied to all chats.

    Each field is optional. When a per-chat config has None for a field,
    the value from this model is used instead.
    """
    model_config = ConfigDict(extra="forbid")

    min_delay_minutes: float = Field(
        default=10.0, ge=0.1, le=1440,
        description="Default delay between posts (minutes)",
    )
    delay_jitter_percent: int = Field(
        default=30, ge=0, le=100,
        description="Default % positive jitter on delay",
    )
    max_photos: int = Field(
        default=5, ge=1, le=20,
        description="Default max photos per post",
    )
    max_width: int = Field(
        default=800, ge=100, le=4096,
        description="Default maximum photo width (pixels)",
    )
    max_height: int = Field(
        default=800, ge=100, le=4096,
        description="Default maximum photo height (pixels)",
    )
```

### 5.2 Modified `ChatConfig` — make overridable fields Optional

```python
class ChatConfig(BaseModel):
    # ... (chat_id, chat_name, topic_id, range_names unchanged)

    # Overridable fields — None means "use global default"
    min_delay_minutes: float | None = Field(
        default=None, description="Delay between posts (minutes); None = use global default"
    )
    delay_jitter_percent: int | None = Field(
        default=None, description="% positive jitter; None = use global default"
    )
    max_photos: int | None = Field(
        default=None, description="Max photos per post; None = use global default"
    )
    max_width: int | None = Field(
        default=None, description="Max photo width; None = use global default"
    )
    max_height: int | None = Field(
        default=None, description="Max photo height; None = use global default"
    )
```

### 5.3 New Container: `ChatsConfig`

```python
class ChatsConfig(BaseModel):
    """Container for global chat defaults and per-chat list."""
    model_config = ConfigDict(extra="forbid")

    defaults: ChatDefaults = Field(default_factory=ChatDefaults)
    list: list[ChatConfig] = Field(..., min_length=1)
```

### 5.4 Modified `TelepostSettings`

```python
class TelepostSettings(BaseModel):
    # ... other fields unchanged
    chats: ChatsConfig  # was: list[ChatConfig]

    @model_validator(mode='after')
    def resolve_chat_defaults(self) -> "TelepostSettings":
        """Fill None fields in each chat from global chat defaults."""
        defaults = self.chats.defaults
        for chat in self.chats.list:
            if chat.min_delay_minutes is None:
                chat.min_delay_minutes = defaults.min_delay_minutes
            if chat.delay_jitter_percent is None:
                chat.delay_jitter_percent = defaults.delay_jitter_percent
            if chat.max_photos is None:
                chat.max_photos = defaults.max_photos
            if chat.max_width is None:
                chat.max_width = defaults.max_width
            if chat.max_height is None:
                chat.max_height = defaults.max_height
        return self
```

### 5.5 YAML Structure (New)

```yaml
chats:
  defaults:
    min_delay_minutes: 10
    delay_jitter_percent: 30
    max_photos: 5
    max_width: 800
    max_height: 800
  list:
    - chat_id: -1001234567890
      range_names:
        - "Sheet1!A1:Z100"
    - chat_id: -1009876543210
      min_delay_minutes: 20
      range_names:
        - "Sheet2!A1:Z50"
    - chat_id: -100111222333
      chat_name: "Promo Channel"
      topic_id: 5
      range_names:
        - "Promo!A1:Z100"
      max_photos: 3
```

### 5.6 Backward Compatibility

Options for users with old-style config (`chats` as flat list):

**Option A (recommended): Migration-on-load with deprecation warning**
In `TelepostConfigReader.load()`, detect the old format (chats is a list of dicts
with `chat_id` at top level) and auto-migrate:
```python
if isinstance(config_data.get("chats"), list):
    # Old format: wrap into new structure
    config_data["chats"] = {
        "defaults": {},
        "list": config_data["chats"],
    }
    logger.warning(
        "Deprecated chats format detected (flat list). "
        "Please migrate to the new format with 'defaults' and 'list' keys."
    )
```

**Option B: Strict — require new format, error on old**
Raise `ConfigError` with migration instructions.

**Recommendation: Option A** — provides smooth migration path. The auto-detection
is unambiguous: if `chats` is a `list`, it's old format; if it's a `dict` with
`defaults`/`list` keys, it's new format.

---

## 6. Files to Modify

| File | Change |
|------|--------|
| `src/mko_telepost/core/models.py` | Add `ChatDefaults`, `ChatsConfig`; modify `ChatConfig` fields to Optional; modify `TelepostSettings` |
| `src/mko_telepost/settings/app_config.yaml` | Restructure `chats` section to new format |
| `src/mko_telepost/core/config_reader.py` | Add backward-compatible format detection in `TelepostConfigReader.load()` |
| `src/mko_telepost/core/telegram_service.py` | Update `TelegramService.__init__` to iterate `settings.chats.list` instead of `settings.chats` |
| `src/mko_telepost/app.py` | Update `_show_config_summary` to iterate `settings.chats.list`; display defaults section |
| `src/mko_telepost/core/delay_engine.py` | No changes — `ChatConfig` fields still resolve to non-None after merge |
| `tests/conftest.py` | Update fixtures to use `ChatsConfig` wrapper |
| `tests/test_models.py` | Add tests for new models and merge logic |
| `tests/test_telegram_service.py` | Update fixtures to use new structure |
| `docs/SPEC.md` | Update config model section and YAML examples |
| All other test files referencing `chats` | Update to use `chats.list` or `ChatsConfig` |

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Flattening the chats list changes the public API of `TelepostSettings` | MEDIUM | The `telegram_service.py` consumer needs update. Backward-compat wrapper in config_reader.py handles YAML migration. |
| Existing test fixtures break due to model changes | MEDIUM | Fixtures in `conftest.py` need updating. Add `ChatsConfig` wrapper. |
| TASK_021/TASK_025 conflict with this change | HIGH | **Sequence this task before TASK_021 and TASK_025**, so those tasks operate on the already-finalized `ChatConfig` with Optional fields. |
| `model_validator(mode='after')` mutable assignment | LOW | `TelepostSettings` already has `validate_assignment=True`; the merge runs once during validation. Post-validation assignment of resolved fields is safe. |
| Users with old YAML format get confusing errors | LOW | Auto-detection + deprecation warning in config_reader.py. |

---

## 8. Execution DAG

```
TASK_030_cfg_two_level_chat_settings      (core model + config changes)
    │
    ├── TASK_031_tst_two_level_chat_settings   (tests for merge logic)
    │
    ├── TASK_032_cfg_backward_compat_yaml      (migration warning in config_reader.py)
    │
    └── TASK_033_cfg_update_template_yaml      (update app_config.yaml template)
    │
    └── TASK_034_tst_verify_two_level_settings (verification)

Then re-sequence existing tasks:
    TASK_021 (rename delay_minutes) — depends on TASK_030 (uses final field names)
    TASK_025 (add max_dimensions) — depends on TASK_030 (adds to final ChatDefaults)
```

---

## 9. Confidence Levels

| Finding | Confidence | Source |
|---------|------------|--------|
| `model_validator(mode='after')` for merging is idiomatic Pydantic v2 | HIGH | Pydantic docs + test examples (verified) |
| Making fields `Optional[T]` with `None` = "use default" | HIGH | Standard Pydantic pattern |
| Confuse layer semantics match our use case | HIGH | Confuse 2.2 docs (verified) |
| YAML structure change to `defaults`/`list` under `chats` | MEDIUM | Cleanest option but adds migration cost; alternatives exist |
| Auto-detection of old format (list vs dict) | HIGH | Unambiguous type check |
