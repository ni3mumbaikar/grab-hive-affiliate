# GrabHive Affiliate Automation Platform

GrabHive Affiliate is a highly robust, modular, and containerized Python platform designed to automate deals posting to Instagram and WhatsApp. It integrates with Google Sheets as a primary collaborative data store, generates custom promotional image creatives using Pillow, and manages E2E transaction states with duplicate protection.

---

## 🚀 Key Features
* **Decoupled Client Interfaces**: Built using strict interfaces (`SheetClient`, `ImageGenerator`, `InstagramPublisher`, `WhatsAppPublisher`) allowing easy replacement of platform integrations.
* **Idempotent Transaction Pipeline**: The Google Sheet status flags are only updated after **both** Instagram and WhatsApp publications succeed.
* **Duplicate Protection**: Leverages a local transaction tracker state (`logs/publish_progress.json`) to skip successfully posted channels on retry.
* **Visual Creative Generator**: Automatically downloads product images and designs a 1080x1080 social media post with overlays (GrabHive logo, price, rating, discount badge).
* **Single Execution Safety**: Employs cross-platform file locking (`app.lock`) to prevent concurrent cron runs.
* **Admin Notifications**: Sends instant email alerts on pipeline failure and stores detailed, structured activity logs in CSV format.

---

## 🛠️ Project Structure
```
grab-hive-affiliate/
├── config/
│   └── settings.py          # Configuration loading & Rotating file logging
├── docs/
│   ├── api_configuration_guide.md # Setup guide for Google Sheets, IG, WA API
│   └── instagram_posting_options.md # JIRA-15 research document
├── src/
│   ├── content/
│   │   ├── caption.py       # Instagram Caption generation
│   │   └── whatsapp_msg.py  # WhatsApp Message formatting
│   ├── image/
│   │   └── generator.py     # Image downloader & PIL graphic synthesis
│   ├── instagram/
│   │   └── publisher.py     # Instagram publisher implementation
│   ├── whatsapp/
│   │   └── publisher.py     # WhatsApp publisher implementation
│   ├── sheets/
│   │   └── client.py        # Google Sheets gspread wrapper
│   ├── interfaces.py        # Abstract Base Classes (Interfaces)
│   ├── models.py            # Dataclasses (Product)
│   ├── monitoring.py        # Activity logs, reports, email notifications
│   ├── pipeline.py          # Transactional pipeline orchestrator
│   └── scheduler.py         # Entry point (Daemon / single-run locking scheduler)
├── tests/
│   └── test_pipeline.py     # Python test suite
├── Dockerfile               # Container builder
├── requirements.txt         # Package dependencies
└── .env.example             # Configuration template
```

---

## ⚙️ Installation & Setup

### Prerequisites
* Python 3.10+
* Google Sheets Service Account Credentials ([API Setup Guide](file:///docs/api_configuration_guide.md))

### 1. Clone & Setup Virtual Environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your secrets:
```bash
copy .env.example .env
```
Refer to the [API Configuration Guide](file:///docs/api_configuration_guide.md) for acquiring Google Service Account credentials, Instagram API tokens, and WhatsApp Business API configurations.

---

## 🏃 Running the Application

### Running the Test Suite
Verify that everything is configured correctly:
```bash
pytest
```

### Single Execution Run (Cron Mode)
Runs the pipeline to process a single pending product, updates flags, and exits immediately. Secured by file locking:
```bash
python src/scheduler.py
```

### Continuous Daemon Run (Process Manager Mode)
Runs continuously, triggering the pipeline execution loop every 4.5 hours (or defined `CRON_INTERVAL_HOURS`):
```bash
python src/scheduler.py --daemon
```

### Docker Deployment
Build and run the container:
```bash
docker build -t grabhive-affiliate .
docker run -d --name grabhive-bot --env-file .env -v "$(pwd)/logs:/app/logs" grabhive-affiliate
```

---

## 📊 Monitoring and Logs
* **App Logs**: Standard process logs are written to `logs/app.log` (with automatic rotating backup).
* **Activity Ledger**: Successful and failed posts are logged in structured format to `logs/activity_log.csv`.
* **Transaction States**: Current items in progress are written to `logs/publish_progress.json` for idempotency protection.
