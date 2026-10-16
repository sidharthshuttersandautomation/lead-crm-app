"""utils/time_utils.py - IST helpers. Every stored timestamp is IST text."""
import datetime
from config.settings import IST, TIMESTAMP_FMT


def now_ist() -> datetime.datetime:
    return datetime.datetime.now(IST)


def now_str() -> str:
    return now_ist().strftime(TIMESTAMP_FMT)


def today_ist() -> datetime.date:
    return now_ist().date()


def parse_ts(value):
    """Parse a stored timestamp string into a naive datetime, or None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "nat"):
        return None
    for fmt in (TIMESTAMP_FMT, "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def financial_year(date_obj: datetime.date) -> str:
    """Indian financial year label, e.g. 2026-27 for Oct 2026."""
    start = date_obj.year if date_obj.month >= 4 else date_obj.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def window_start(days):
    """Start date for a reporting window: number of days, "month" (1st of this month) or None (all time)."""
    if days is None:
        return None
    if days == "month":
        return today_ist().replace(day=1)
    return today_ist() - datetime.timedelta(days=days)
