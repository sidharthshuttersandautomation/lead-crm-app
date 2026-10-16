"""
utils/sla_calculator.py - 5:30 PM IST quotation SLA.

A lead received before the cutoff is due the same day; after the cutoff it is
due the next day. Sundays are skipped. PENDING DECISION: holiday calendar.
"""
import datetime
from config.settings import IST, SLA_CUTOFF_HOUR, SLA_CUTOFF_MINUTE


def _next_working_day(day: datetime.date) -> datetime.date:
    nxt = day + datetime.timedelta(days=1)
    while nxt.weekday() == 6:  # Sunday
        nxt += datetime.timedelta(days=1)
    return nxt


def evaluate_sla(request_dt: datetime.datetime = None):
    """Returns (is_after_cutoff, target_date, queue_label)."""
    if request_dt is None:
        request_dt = datetime.datetime.now(IST)

    cutoff = datetime.time(SLA_CUTOFF_HOUR, SLA_CUTOFF_MINUTE)
    is_after_cutoff = request_dt.time() >= cutoff or request_dt.weekday() == 6

    if is_after_cutoff:
        return True, _next_working_day(request_dt.date()), "Overnight queue (next working day)"
    return False, request_dt.date(), "Same-day target"
