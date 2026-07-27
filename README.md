# GrabHive Affiliate Automation Platform

GrabHive Affiliate is a highly robust, modular, and containerized Python platform designed to automate deal discovery from **Amazon India (`amazon.in`)**, populate Google Sheets, and publish automated deal posts to Instagram and WhatsApp. It integrates with Google Sheets as a primary collaborative data store, generates custom promotional image creatives using Pillow, and manages E2E transaction states with duplicate protection.

---

## 🚀 Key Features
* **Amazon.in Deals Scraper & Auto-Populator**: Automatically scrapes live deals from Amazon India, enriches candidate deals with rating & review metadata from product pages, filters by quality thresholds ($\ge 30\%$ discount, $\ge 4.3$ rating, $\ge 500$ reviews), scores/ranks deals, appends affiliate tags, and batch-populates the Google Sheet.
* **Decoupled Client Interfaces**: Built using strict interfaces (`SheetClient`, `ImageGenerator`, `InstagramPublisher`, `WhatsAppPublisher`) allowing easy replacement of platform integrations.
* **Idempotent Transaction Pipeline**: Google Sheet status flags are only updated after **both** Instagram and WhatsApp publications succeed.
* **Duplicate Protection**: Deduplicates scraped items against existing sheet entries, and uses a transaction tracker (`logs/publish_progress.json`) to skip already-posted channels on retry.
* **Visual Creative Generator**: Automatically downloads product images and designs 1080x1080 social media post creatives with overlays (GrabHive logo, price, rating, badges).
* **Single Execution Safety**: Employs cross-platform file locking (`app.lock` and `scraper.lock`) to prevent concurrent cron/daemon runs.
* **Admin Notifications**: Sends instant email alerts on pipeline failure and stores structured activity logs in CSV format.

---

## 🛠️ Project Structure

```
grab-hive-affiliate/
├── config/
│   └── settings.py                  # Configuration loading & Rotating file logging
├── docs/
│   ├── api_configuration_guide.md     # Setup guide for Google Sheets, IG, WA API
│   └── instagram_posting_options.md   # Instagram research document
├── src/
│   ├── core/                        # Domain models, interfaces & monitoring
│   │   ├── models.py                # Product & ScrapedDeal dataclasses
│   │   ├── interfaces.py            # Abstract Base Classes (SheetClient, Publisher, etc.)
│   │   └── monitoring.py            # Activity logger, reporting & email alerting
│   ├── sheets/
│   │   └── client.py                # Google Sheets gspread wrapper & batch appender
│   ├── publishers/                  # Content generation & publication engines
│   │   ├── content/
│   │   │   ├── caption.py           # Instagram caption generator
│   │   │   └── whatsapp_msg.py      # WhatsApp message generator
│   │   ├── image/
│   │   │   └── generator.py         # PIL Graphic creative synthesis
│   │   ├── instagram/
│   │   │   ├── publisher.py         # Unofficial Instagrapi publisher
│   │   │   └── official_publisher.py # Official Meta Graph API publisher
│   │   └── whatsapp/
│   │       └── publisher.py         # WhatsApp Webhook/Cloud API publisher
│   ├── scraper/                     # Amazon India Deals Scraper Engine
│   │   ├── amazon.py                # amazon.in HTML & detail page scraper
│   │   ├── processor.py             # Filters, scoring formula & affiliate tagger
│   │   └── daemon.py                # Scraper daemon orchestrator
│   ├── pipeline.py                  # Transactional posting orchestrator
│   ├── scheduler.py                 # Posting bot entry point
│   ├── scraper_daemon.py            # Deal scraper entry point
│   ├── content/                     # Re-export wrappers for backward compatibility
│   ├── image/                       # Re-export wrappers for backward compatibility
│   ├── instagram/                   # Re-export wrappers for backward compatibility
│   ├── whatsapp/                    # Re-export wrappers for backward compatibility
│   ├── interfaces.py                # Re-export for backward compatibility
│   ├── models.py                    # Re-export for backward compatibility
│   └── monitoring.py                # Re-export for backward compatibility
├── tests/                           # Pytest test suite
│   ├── test_pipeline.py             # End-to-end posting pipeline tests
│   ├── test_instagram_publisher.py  # Instagrapi publisher tests
│   ├── test_instagram_graph_publisher.py # Meta Graph API publisher tests
│   ├── test_scraper.py              # Amazon India scraper & filter tests
│   └── test_sheets.py               # Google Sheets client & append tests
├── docker-compose.yml               # Multi-container orchestration (bot & deal-scraper)
├── Dockerfile                       # Container builder
├── requirements.txt                 # Package dependencies
└── .env.example                     # Configuration template
```

---

## ⚙️ Installation & Setup

### Prerequisites
* Python 3.10+
* Google Sheets Service Account Credentials ([API Setup Guide](file:///docs/api_configuration_guide.md))
* Amazon Associates Affiliate Tag (e.g. `yourtag-21`)

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
Key scraper environment options:
```env
AMAZON_AFFILIATE_TAG=grabhive-21
AMAZON_BASE_URL=https://www.amazon.in
SCRAPER_INTERVAL_HOURS=12.0
MIN_DISCOUNT_PERCENT=30.0
MIN_RATING=4.3
MIN_REVIEWS=500
MAX_DEALS_PER_RUN=50
```

---

## 🏃 Running the Application

### Running the Test Suite
Verify everything is configured correctly:
```bash
pytest
```

### 1. Amazon.in Deals Scraper / Auto-Populator Service
- **Single Execution Run**: Scrapes Amazon India, filters, and appends top deals to Google Sheet once:
  ```bash
  python src/scraper_daemon.py
  ```
- **Continuous Daemon Mode**: Runs on a schedule every 12 hours (`SCRAPER_INTERVAL_HOURS`):
  ```bash
  python src/scraper_daemon.py --daemon
  ```

### 2. Posting Bot Service
- **Single Execution Run**: Processes one pending item from Google Sheet and posts to IG & WhatsApp:
  ```bash
  python src/scheduler.py
  ```
- **Continuous Daemon Mode**: Runs execution loop every 4.5 hours (`CRON_INTERVAL_HOURS`):
  ```bash
  python src/scheduler.py --daemon
  ```

### Docker Compose Deployment
Launch both the posting bot and Amazon scraper services:
```bash
docker-compose up -d --build
```

---

## 📊 Monitoring and Logs
* **App Logs**: Standard process logs written to `logs/app.log` (with automatic rotating backup).
* **Activity Ledger**: Successful and failed operations logged in structured format to `logs/activity_log.csv`.
* **Transaction Locks**: Cross-platform lock files (`logs/app.lock` and `logs/scraper.lock`) ensure execution safety.
