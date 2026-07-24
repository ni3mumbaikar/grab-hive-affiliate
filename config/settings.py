import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

class ConfigError(ValueError):
    """Raised when environment configuration is invalid or missing required variables."""
    pass

# Retrieve and validate configurations
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
CRON_INTERVAL_HOURS = float(os.getenv("CRON_INTERVAL_HOURS", "4.5"))

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
INSTAGRAM_SESSION_ID = os.getenv("INSTAGRAM_SESSION_ID")

WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "http://localhost:3000/send-message")
WHATSAPP_SIMULATE = os.getenv("WHATSAPP_SIMULATE", "False").lower() in ("true", "1", "yes")


ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Simple validation method for required variables
def validate_config():
    missing = []
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        missing.append("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not SPREADSHEET_ID:
        missing.append("SPREADSHEET_ID")
    
    if missing:
        raise ConfigError(f"Missing required configuration variables: {', '.join(missing)}")

# Setup Logging
def setup_logging():
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "app.log"
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    
    # Remove existing handlers if any
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        
    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler (Rotating)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    logger.info("Logging configured successfully. Level: %s", LOG_LEVEL)

# Auto-configure logging when settings are loaded
setup_logging()
