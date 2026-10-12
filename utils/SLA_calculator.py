from datetime import datetime, timedelta
import pytz
from config.settings import IST_TZ, SLA_CUTOFF_HOUR, SLA_CUTOFF_MINUTE

def evaluate_sla_cutoff(request_dt: datetime):
    if request_dt.tzinfo is None:
        request_dt = IST_TZ.localize(request_dt)
        
    cutoff = request_dt.replace(hour=SLA_CUTOFF_HOUR, minute=SLA_CUTOFF_MINUTE, second=0, microsecond=0)
    is_after = request_dt >= cutoff
    
    if is_after:
        target_date = (request_dt + timedelta(days=1)).date()
    else:
        target_date = request_dt.date()
        
    return is_after, target_date.strftime("%Y-%m-%d")

def calculate_turnaround_time_mins(request_str: str, completion_str: str) -> int:
    try:
        req = datetime.strptime(request_str, "%Y-%m-%d %H:%M:%S")
        comp = datetime.strptime(completion_str, "%Y-%m-%d %H:%M:%S")
        delta = comp - req
        return int(delta.total_seconds() / 60)
    except Exception:
        return 0