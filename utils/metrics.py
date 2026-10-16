"""utils/metrics.py - Shared calculations so every screen counts the same way."""
import datetime

import pandas as pd

from config.settings import CLOSED_STAGES
from utils.time_utils import parse_ts, today_ist


def latest_quotes(df_quotes: pd.DataFrame) -> pd.DataFrame:
    """One row per lead: its most recent revision. Prevents double counting."""
    if df_quotes.empty:
        return df_quotes
    ordered = df_quotes.sort_values(["lead_id", "revision_no", "created_at"])
    return ordered.groupby("lead_id", as_index=False).tail(1)


def amount(series) -> float:
    return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())


def open_leads(df_leads: pd.DataFrame) -> pd.DataFrame:
    if df_leads.empty:
        return df_leads
    return df_leads[~df_leads["final_status"].isin(CLOSED_STAGES)]


def filter_by_window(df: pd.DataFrame, column: str, start_date):
    """Keep rows whose `column` timestamp/date is on or after start_date."""
    if df.empty or start_date is None or column not in df.columns:
        return df
    dates = df[column].map(lambda v: (parse_ts(v).date() if parse_ts(v) else None))
    return df[dates.map(lambda d: d is not None and d >= start_date)]


def followup_date(value):
    ts = parse_ts(value)
    return ts.date() if ts else None


def call_bucket(next_followup_at, today: datetime.date = None) -> str:
    """'today', 'overdue', 'upcoming' or 'unscheduled'."""
    today = today or today_ist()
    d = followup_date(next_followup_at)
    if d is None:
        return "unscheduled"
    if d < today:
        return "overdue"
    if d == today:
        return "today"
    return "upcoming"


def inr(value) -> str:
    """Indian-style grouping: 12,34,567."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return "₹0"
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"{sign}₹{s}"


def period_compare(df: pd.DataFrame, column: str, days):
    """(count in the last `days`, count in the `days` before that). days=None -> (all, None)."""
    if df is None or df.empty or column not in df.columns:
        return 0, (None if days is None else 0)
    if days is None:
        return len(df), None
    today = today_ist()
    dates = df[column].map(followup_date)
    if days == "month":
        first = today.replace(day=1)
        prev_first = (first - datetime.timedelta(days=1)).replace(day=1)
        prev_end = prev_first + (today - first)            # same number of days into last month
        cur = int(dates.map(lambda d: d is not None and d >= first).sum())
        prev = int(dates.map(lambda d: d is not None and prev_first <= d <= prev_end).sum())
        return cur, prev
    cur_start = today - datetime.timedelta(days=days)
    prev_start = cur_start - datetime.timedelta(days=days)
    cur = int(dates.map(lambda d: d is not None and d > cur_start).sum())
    prev = int(dates.map(lambda d: d is not None and prev_start < d <= cur_start).sum())
    return cur, prev


def delta_kpi(label, df, column, days, icon=None, tone="blue", unit="", good="up"):
    """KPI tile dict with change vs. the previous period of the same length."""
    cur, prev = period_compare(df, column, days)
    item = {"label": label, "value": f"{cur}{unit}", "icon": icon, "tone": tone, "delta_good": good}
    if prev is not None:
        item["delta"] = cur - prev
        item["sub"] = (f"vs same days last month ({prev})" if days == "month" else f"vs previous {days} days ({prev})")
    return item
