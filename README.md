# MONITOR CLASSIFIED IN TELEGRAM

A simple yet powerful **Telegram classified monitor** designed to track messages with customizable **keyword filters**, automatically **forward** relevant posts, and include **source links** and **sender usernames** when available.

---

## Key Features

*  **Automated Monitoring**
  Scans Telegram channels for new messages matching your keywords and forwards them automatically.

* **Smart Forwarding**
  Each forwarded message includes:

  * A link to the original channel post.
  * A link to the channel itself.
  * The sender's username (`@username`), if public.

* **Flexible Keyword Logic**
  Supports complex search expressions.

* **Media Support**
  Forwards messages **with images, videos, or albums** intact.

* **Per-Channel Configuration**
  Each channel can have its own:

  * Scan frequency
  * Message history depth
  * Keyword set

* **Persistent State**
  Keeps track of the last scanned message for each channel — no duplicates on restart.

---

### Example of Complex Keyword Expression

```text
    (barcelona | барселона) (bicycle | bike | велосипед) -rent* -repair* -service* -tour* -hotel -room -apartment -job -delivery
```

Meaning:

> "Find messages that mention *Barcelona* and *bicycle* (in English or Russian),
> but exclude posts about rentals, repairs, services, tours, hotels, apartments, jobs, or deliveries."

✅ **Example matches:**

* "Selling my mountain bike in Barcelona"
* "Used велосипед for sale in Барселона"

🚫 **Ignored:**

* "Bike rental service in Barcelona"
* "Room available near bike shop in Барселона"

---

## ⚙️ Setup Instructions

### 1️⃣ Install

**Using pip** (from PyPI):

```bash
pip install mko-telebot
```

**Using uv** (recommended — faster):

```bash
uv pip install mko-telebot
```

**Install from source** (for development):

```bash
git clone https://github.com/<your-repo>/mko_telebot.git
cd mko_telebot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Alternatively, install from **TestPyPI**:

```bash
pip install --upgrade --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple mko-telebot
```

### 2️⃣ Initialize Configuration

Copy the default configuration templates to your user config directory:

```bash
mko-telebot init
```

This creates the following files in `~/.config/mko_telebot/settings/`:

* `config.yaml` — main configuration (channels, keywords, intervals)
* `secrets.yaml` — Telegram API credentials (API ID, API hash, phone/token)
* `log_config.yaml` — logging level and output settings

Use `--force` (or `-f`) to overwrite existing files if you need a fresh copy:

```bash
mko-telebot init --force
```

### 3️⃣ Edit Configuration

Edit the three configuration files in `~/.config/mko_telebot/settings/`:

* Set your **Telegram API credentials** (`api_id`, `api_hash`, `phone` or `bot_token`) in `secrets.yaml`.
* Define **channels to monitor**, **keywords**, and **scan intervals** in `config.yaml`.
* Adjust **logging preferences** in `log_config.yaml`.

### 4️⃣ Validate Configuration (Optional)

Run a dry check to ensure all settings are correct before starting:

```bash
mko-telebot validate
```

### 5️⃣ Launch the Monitor

```bash
mko-telebot run
```

### 6️⃣ Stop the Monitor

```bash
pkill -f mko-telebot
```
or press `Ctrl+C` in the terminal where the monitor is running.

---

## 📋 CLI Commands Reference

| Command | Description |
|---------|-------------|
| `mko-telebot init` | Copy default template files to the user config directory. |
| `mko-telebot validate` | Validate configuration files without starting the monitor. |
| `mko-telebot run` | Start the Telegram monitoring service. |
| `mko-telebot config` | Display all application path locations (config, secrets, logs, sessions, state). |
| `mko-telebot version` | Show the installed version of mko-telebot. |

**Global options:**

* `--help` — Show help message and exit.
* `--install-completion` — Install shell completion for your shell.
* `--show-completion` — Show completion for your shell.

### Command Details

**`mko-telebot init`**

Copies default `config.yaml`, `secrets.yaml`, and `log_config.yaml` templates from the package installation directory to the user config directory. Skips files that already exist unless `--force` is used.

**`mko-telebot validate`**

Parses all configuration files, validates every field (including Telegram credentials), and reports any errors without connecting to Telegram. Useful for catching typos or missing values before going live.

**`mko-telebot run`**

Loads the configuration, initializes a Telethon client using your credentials, connects to Telegram, and begins scanning the configured channels for keyword matches. Runs until interrupted.

**`mko-telebot config`**

Prints a table of all important paths used by the application:

* Config, secrets, and log config file paths
* State and session directories
* Log output directory

**`mko-telebot version`**

Prints the installed package version number from PyPI metadata.

---

## 🔧 Configuration Files

All configuration files live under `~/.config/mko_telebot/settings/` (the exact path varies by platform — run `mko-telebot config` to see your system paths).

| File | Purpose | Required |
|------|---------|----------|
| `config.yaml` | Channel definitions, keywords, scan intervals | Yes |
| `secrets.yaml` | Telegram API credentials (`api_id`, `api_hash`, `phone` or `bot_token`) | Yes |
| `log_config.yaml` | Logging level, format, output file | Yes (defaults provided) |
| `state/` | Tracks the last-scanned message per channel (auto-managed) | Auto |
| `sessions/` | Telethon session files for authentication (auto-managed) | Auto |

### config.yaml

The main configuration file where you define:

* **Channels** — Telegram channels or groups to monitor (by username or ID).
* **Keywords** — Per-channel keyword expressions supporting `(word1 | word2)`, `-exclude`, and `*` wildcards.
* **Intervals** — How often to scan each channel (in seconds).
* **History depth** — How many past messages to scan on first run.

### secrets.yaml

Stores sensitive credentials:

* `api_id` — Your Telegram API ID (from [my.telegram.org](https://my.telegram.org)).
* `api_hash` — Your Telegram API hash.
* `phone` or `bot_token` — The phone number or bot token used for authentication.

> ⚠️ Treat this file like a password — never commit it to version control.

### log_config.yaml

Controls:

* **Log level** — `DEBUG`, `INFO`, `WARNING`, `ERROR`.
* **Log format** — Timestamp, level, module, message.
* **Output** — Console and/or file logging.

---

## ❓ Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| `ConfigError` on start | Missing or malformed config files | Run `mko-telebot validate` to see what is wrong. Check YAML syntax. |
| `mko-telebot: command not found` | Package not installed or not on `PATH` | Verify installation with `pip list \| grep mko-telebot` or reinstall. |
| `AUTH_KEY_UNREGISTERED` or `API_ID_INVALID` | Invalid Telegram credentials | Double-check `api_id` and `api_hash` in `secrets.yaml`. Generate new ones at [my.telegram.org](https://my.telegram.org) if needed. |
| No messages forwarded | Keywords too restrictive, channel not scanned yet, or wrong channel ID | Start with a broad keyword expression. Check logs at your configured log level. Use `mko-telebot validate` first. |
| Duplicate messages on restart | State file corrupted or deleted | The state directory is auto-managed; ensure it is not inside a temporary or cleaned directory. |
| Telegram blocks the account | Too-frequent scanning | Increase scan intervals. Use a dedicated account or bot token. Never use your primary personal account. |
| Permission / access errors | Config directory not readable/writable | Ensure `~/.config/mko_telebot/settings/` exists and is writable. Run with the correct user. |

### Logs

Logs are stored according to your `log_config.yaml` settings. By default they go to `~/.config/mko_telebot/logs/`. See actual paths with:

```bash
mko-telebot config
```

---

## Notes & Recommendations

* The bot **must run continuously** to detect new posts.
* Ensure your **Telegram API credentials** are valid and not expired.
> ⚠️ **Important:**
> Do **not** use your personal Telegram account for automation.
> Violating Telegram's rules or wrong configuration may result in a permanent account ban.
> Use a dedicated account or bot API credentials.
* Avoid aggressive scanning intervals — Telegram may block you for spam-like activity.
* Logs are stored according to your configuration in `log_config.yaml`.

---