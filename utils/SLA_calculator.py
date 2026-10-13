"""
5:30 PM IST SLA Cutoff Calculator.
"""
from datetime import datetime, time, timedelta
from config.settings import IST, SLA_CUTOFF_HOUR, SLA_CUTOFF_MINUTE

def evaluate_sla(request_dt: datetime = None) -> tuple[bool, datetime, str]:
    if not request_dt:
        request_dt = datetime.now(IST)

    cutoff_time = time(SLA_CUTOFF_HOUR, SLA_CUTOFF_MINUTE)
    is_after_cutoff = request_dt.time() >= cutoff_time

    if is_after_cutoff:
        target_date = (request_dt + timedelta(days=1)).date()
        queue_label = "Overnight Queue (Next Day Target)"
    else:
        target_date = request_dt.date()
        queue_label = "Same Day SLA Target"

    return is_after_cutoff, target_date, queue_label