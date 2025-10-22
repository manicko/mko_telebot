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
  * The sender’s username (`@username`), if public.

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

> “Find messages that mention *Barcelona* and *bicycle* (in English or Russian),
> but exclude posts about rentals, repairs, services, tours, hotels, apartments, jobs, or deliveries.”

✅ **Example matches:**

* “Selling my mountain bike in Barcelona”
* “Used велосипед for sale in Барселона”

🚫 **Ignored:**

* “Bike rental service in Barcelona”
* “Room available near bike shop in Барселона”

---

## ⚙️ Setup Instructions

### 1️⃣ Install Dependencies

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

### 2️⃣ Configuration

1. Copy configuration files to your working directory:

   ```
   config.yaml
   secrets.yaml
   log_config.yaml
   ```

   > Default path: `~/.mko_telebot/mko_telebot/settings/`

2. Edit configuration files:
   * Set up Telegram API credentials.
   * Configure monitoring channels, keywords, and intervals.

### 3️⃣ Launch the Monitor

```bash
python3 -m mko_telebot.monitor launcher
```

### 4️⃣ Stop the Monitor

```bash
pkill -f mko_telebot.monitor
```
---
## Notes & Recommendations

* The bot **must run continuously** to detect new posts.
* Ensure your **Telegram API credentials** are valid and not expired.
> ⚠️ **Important:**
> Do **not** use your personal Telegram account for automation.
> Violating Telegram’s rules or wrong configuration may result in a permanent account ban.
> Use a dedicated account or bot API credentials.
* Avoid aggressive scanning intervals — Telegram may block you for spam-like activity.
* Logs are stored according to your configuration in `log_config.yaml`.

---
