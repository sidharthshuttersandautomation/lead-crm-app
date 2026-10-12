from datetime import datetime, time, timedelta
from config.settings import IST, SLA_CUTOFF_HOUR, SLA_CUTOFF_MINUTE

def evaluate_sla(request_dt: datetime = None) -> tuple[bool, datetime, str]:
    """Calculates 5:30 PM cutoff rule and assigns target date.
    - Requested <= 17:29 IST: Same Day Task Queue
    - Requested >= 17:30 IST: Overnight Queue (Next Working Day Target)
    """
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


def calculate_tat_minutes(
    request_timestamp_str: str, completion_timestamp_str: str
) -> float:
    """Calculates quotation turn-around time in minutes."""
    try:
        req = datetime.fromisoformat(str(request_timestamp_str))
        comp = datetime.fromisoformat(str(completion_timestamp_str))
        delta = comp - req
        return round(delta.total_seconds() / 60.0, 1)
    except Exception:
        return 0.0