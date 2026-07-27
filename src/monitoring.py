"""Re-export monitoring functions for backward compatibility."""
from src.core.monitoring import (
    log_activity,
    notify_admin_email,
    get_daily_statistics,
    generate_daily_summary_report,
)

__all__ = [
    "log_activity",
    "notify_admin_email",
    "get_daily_statistics",
    "generate_daily_summary_report",
]
