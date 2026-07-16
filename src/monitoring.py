import os
import csv
import time
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional
from config.settings import ADMIN_EMAIL, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD

logger = logging.getLogger(__name__)

ACTIVITY_LOG_FILE = Path("logs/activity_log.csv")

def log_activity(product_name: str, link: str, status: str, error_message: str = ""):
    """Logs pipeline activity to a structured CSV file (JIRA-28)."""
    try:
        ACTIVITY_LOG_FILE.parent.mkdir(exist_ok=True, parents=True)
        file_exists = ACTIVITY_LOG_FILE.exists()
        
        with open(ACTIVITY_LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "product_name", "affiliate_link", "status", "error_message"])
            
            writer.writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                product_name,
                link,
                status,
                error_message
            ])
            logger.info("Activity logged successfully in %s", ACTIVITY_LOG_FILE.name)
    except Exception as e:
        logger.error("Failed to write to activity log CSV: %s", e)


def notify_admin_email(subject: str, message_body: str) -> bool:
    """Sends an email alert to the system administrator on pipeline errors (JIRA-29)."""
    if not SMTP_SERVER or not SMTP_USERNAME or not SMTP_PASSWORD or not ADMIN_EMAIL:
        logger.warning("SMTP configuration is incomplete. Skipping email notification.")
        return False
        
    try:
        logger.info("Sending error email notification to admin: %s", ADMIN_EMAIL)
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = ADMIN_EMAIL
        msg["Subject"] = f"[GrabHive Alert] {subject}"
        
        msg.attach(MIMEText(message_body, "plain"))
        
        # Connect to SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info("Admin email notification sent successfully.")
        return True
    except Exception as e:
        logger.error("Failed to send admin email notification: %s", e)
        return False


def get_daily_statistics() -> dict:
    """Reads the activity CSV and returns summary statistics for the last 24 hours."""
    stats = {
        "posted_today": 0,
        "failed_today": 0
    }
    
    if not ACTIVITY_LOG_FILE.exists():
        return stats
        
    one_day_ago = time.time() - (24 * 3600)
    
    try:
        with open(ACTIVITY_LOG_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row_time = time.mktime(time.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S"))
                    if row_time >= one_day_ago:
                        if row["status"].upper() == "SUCCESS":
                            stats["posted_today"] += 1
                        else:
                            stats["failed_today"] += 1
                except Exception:
                    continue
    except Exception as e:
        logger.error("Error reading activity log for stats: %s", e)
        
    return stats


def generate_daily_summary_report(total_pending: int) -> str:
    """Compiles and returns a summary report string (JIRA-30)."""
    stats = get_daily_statistics()
    
    report = (
        "=====================================\n"
        "       GRABHIVE DAILY REPORT         \n"
        "=====================================\n"
        f"Timestamp:      {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Products Posted (Last 24h): {stats['posted_today']}\n"
        f"Failed Posts (Last 24h):    {stats['failed_today']}\n"
        f"Pending Products in Sheet:  {total_pending}\n"
        "====================================="
    )
    return report
