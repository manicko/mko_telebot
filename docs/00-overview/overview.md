---
id: overview
domain: overview
tags:
  - architecture
  - concepts
  - overview
related:
  - configuration-guide
  - cli-reference
---

# mko-telebot Overview

**Version:** 0.1+

A Telegram classified monitor that tracks messages with customizable keyword filters, automatically forwards relevant posts, and includes source links and sender usernames.

---

## Purpose

mko-telebot is a command-line application that monitors Telegram channels for new messages matching user-defined keyword patterns and automatically forwards qualifying messages to configured target destinations.

---

## Main Concepts

### Architecture

The application follows a layered architecture:

| Layer | Component | Description |
|-------|-----------|-------------|
| CLI | `cli.py` | Typer-based command interface (init, validate, run, config, version) |
| Service | `monitor.py` | Core monitoring logic: client management, message processing, forwarding |
| Task | `core/task.py` | Per-channel state management and entity resolution |
| Config | `core/config.py` | YAML loading, validation, and merging |
| Models | `core/channels.py`, `core/telethon.py` | Pydantic models for configuration |
| Parser | `core/parser.py` | Keyword pattern parsing and matching |

### Configuration Sources

Configuration is loaded from:

1. **User config directory** (platform-specific):
   - `config.yaml` — Channel definitions and monitoring settings
   - `secrets.yaml` — Telegram API credentials (SecretStr protected)
   - `log_config.yaml` — Logging configuration
2. **Built-in templates** — Copied to user directory via `mko-telebot init`

### Message Processing Pipeline

```
┌─────────────────────────────────────────────────────────┐
│ 1. Load configuration and authenticate to Telegram      │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Initialize tasks for each configured channel         │
│    - Resolve channel entity                             │
│    - Restore last_msg_id from state file                │
│    - Resolve target entities for forwarding             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Staggered scan loop (main_loop)                      │
│    - Fetch messages since last seen                     │
│    - Group albums by grouped_id                         │
│    - Check each message against keywords                │
│    - Forward matches with retry logic                    │
│    - Save state (last_msg_id)                          │
└─────────────────────────────────────────────────────────┘
```

### Forwarding Behavior

When a message matches keywords:

1. **Source link** — A t.me URL to the original message is constructed
2. **Sender tag** — The sender's username (`@username`) or display name is retrieved
3. **Caption assembly** — Original text, sender tag, and source link are combined
4. **Media handling** — Messages with media (including albums) are forwarded intact
5. **Target delivery** — Message is sent to each configured target with retry logic

### State Persistence

Each channel maintains a state file in the `state/` directory:

- Path: `<state_dir>/<channel_name>.json`
- Contents: `{"last_id": <int>}` — last processed message ID
- Prevents duplicate forwarding on restart
- Automatically created on first run

### Error Handling

The application implements robust error handling:

- **FloodWaitError** — Telegram rate limiting; waits required duration plus jitter, then retries
- **RPCError** — Transient Telegram API errors; retries with exponential backoff
- **Retry logic** — Uses `max_retries` from config with exponential backoff and random jitter
- **State errors** — File I/O failures raise `StateError` with descriptive messages

---

## Key Features

| Feature | Description |
|---------|-------------|
| Keyword filtering | Pattern syntax with OR (`|`), exclusion (`-`), wildcards (`*`), grouping |
| Album support | Messages with same `grouped_id` are forwarded together |
| Source attribution | Forwarded messages include t.me link to original |
| Sender identification | Original sender's username or display name included |
| Per-channel configuration | Separate scan intervals, keywords, and targets per channel |
| Persistent state | Last message ID stored per channel to prevent duplicates |
| Exponential backoff | Retry logic with jitter for transient Telegram errors |
| Configuration validation | Pydantic models validate all config fields at load time |
| Path security | Channel names validated against path traversal attacks |

---

## Related Docs

- [Configuration Guide](../11-guides/configuration.md) — Detailed field-by-field configuration reference
- [CLI Reference](../99-reference/cli-reference.md) — Command usage and options