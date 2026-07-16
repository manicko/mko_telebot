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
| Service | `monitor.py` | Core monitoring logic: client management, staggered scan loop, task orchestration |
| Task | `core/task.py` | Per-channel state management and entity resolution |
| Config | `core/config.py` | YAML loading, validation, and merging |
| Models | `core/channels.py`, `core/telethon.py` | Pydantic models for configuration |
| Parser | `core/parser.py` | Keyword pattern parsing and matching |
| Forwarding | `monitor_forward.py` | Message processing, album grouping, retry logic for forwarding |

### Configuration Sources

Configuration is loaded from:

1. **User config directory** (platform-specific):
    - `config.yaml` — Channel definitions and monitoring settings
    - `telethon_config.yaml` — Telegram API credentials (api_id, api_hash, phone/token)
    - `log_config.yaml` — Logging configuration
    - `keyw_config_example_keep.yaml` — Keyword configuration examples (reference)
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
│    - Resolve target entities atomically (all-or-nothing) │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Staggered scan loop (main_loop)                      │
│    - Fetch messages since last seen                     │
│    - Group albums by grouped_id                         │
│    - Check each message against keywords                │
│    - Forward matches with retry logic                    │
│    - Save state (last_msg_id)                          │
│    - Reschedule channel with staggered delay             │
└─────────────────────────────────────────────────────────┘
```

### Forwarding Behavior

Keyword matching is evaluated against **both the message body and the media caption**. For messages carrying photo or video attachments, the caption text is scanned alongside the body, so a post whose caption contains a matching keyword is forwarded even when the body text is empty.

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
- **WorkerBusyTooLongRetryError** — Telegram worker busy state; retries with exponential backoff
- **RPCError** — Transient Telegram API errors; retries with exponential backoff and jitter
- **Retry logic** — Uses `max_retries` from config with exponential backoff and random jitter
- **State errors** — File I/O failures are logged gracefully without crashing the monitor loop

### Startup Resilience

Two safeguards protect the monitor before the scan loop starts, and a third handles resolution-time rate limits:

- **No-channel validation** — If the configuration defines zero channels, the application logs a clear error and raises `ConfigError` instead of entering an empty processing queue that would block indefinitely. This fails fast with actionable feedback rather than hanging silently.
- **Per-channel init isolation** — During startup, each channel's entity and target resolution is wrapped in error handling. If one channel fails to resolve (e.g. wrong identifier, deleted channel, or Telegram rate limit), the failure is logged and that channel is skipped while the remaining channels continue to initialize and are monitored normally.
- **Resolution rate-limit handling** — `FloodWaitError` raised while resolving channels or targets is handled by waiting the required duration plus jitter before failing, so transient rate-limit windows do not immediately abort channel setup.

### Runtime Channel Resilience

Beyond startup safeguards, the monitor guarantees that channels survive errors raised *during* a scan. Each channel's processing is wrapped so that `reschedule_task` always runs in a `finally` block, regardless of whether the scan raises. A transient failure (Telegram RPC error, network blip, malformed message) is logged and the channel is re-enqueued for its next interval — it is never permanently dropped from the monitoring queue. This keeps the long-running monitor self-healing instead of silently losing channels after the first error.

---

## Key Features

| Feature | Description |
|---------|-------------|
| Keyword filtering | Pattern syntax with OR (`|`), exclusion (`-`), wildcards (`*`), grouping |
| Media caption matching | Keyword patterns also match media captions, so photo/video posts with keyword-bearing captions are forwarded even when the body is empty |
| Album support | Messages with same `grouped_id` are forwarded together |
| Source attribution | Forwarded messages include t.me link to original |
| Sender identification | Original sender's username or display name included |
| Per-channel configuration | Separate scan intervals, keywords, and targets per channel |
| Persistent state | Last message ID stored per channel to prevent duplicates |
| Exponential backoff | Retry logic with jitter for transient Telegram errors |
| Configuration validation | Pydantic models validate all config fields at load time |
| Path security | Channel names and session names validated against path traversal attacks |
| Credential protection | Proxy and Telegram credentials use SecretStr to prevent exposure |
| Atomic entity resolution | Target entities resolved atomically to prevent partial state on error |
| Graceful state save | State save failures logged without interrupting monitoring |
| Startup channel validation | Fails fast with a clear `ConfigError` when no channels are configured, preventing an infinite hang |
| Per-channel init isolation | A channel that fails to resolve at startup is skipped and logged so the remaining channels keep being monitored |
| Runtime channel resilience | A channel that errors during a scan is logged and rescheduled; it is never permanently dropped from monitoring |
| Config-load validation | Keyword syntax and `history_days` are validated at load time; invalid values raise `ConfigError` before the monitor starts |
| Credential file protection | `init --force` preserves an existing `telethon_config.yaml` so credentials are never overwritten by templates |
| Credential file permissions | On POSIX, credential files are set to `0600` and the config directory to `0700` to limit exposure on multi-user systems |
| History day filtering | `history_days` limits scanning to recent messages only |

---

## Related Docs

- [Configuration Guide](../11-guides/configuration.md) — Detailed field-by-field configuration reference
- [CLI Reference](../99-reference/cli-reference.md) — Command usage and options