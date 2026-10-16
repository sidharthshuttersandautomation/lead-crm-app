"""utils/payments.py - Collection calculations."""
import datetime

import pandas as pd

from config.settings import AGEING_BUCKETS
from utils.time_utils import parse_ts, today_ist


def payment_status(order_value, received) -> str:
    value, got = float(order_value or 0), float(received or 0)
    if value > 0 and got >= value - 0.5:
        return "Received"
    return "Partial" if got > 0 else "Pending"


def ageing_label(days) -> str:
    for lo, hi, label in AGEING_BUCKETS:
        if lo <= days <= hi:
            return label
    return AGEING_BUCKETS[-1][2]


def enrich_orders(df_orders: pd.DataFrame) -> pd.DataFrame:
    """Adds days_outstanding, ageing bucket, status and collection-follow-up state."""
    if df_orders.empty:
        return df_orders
    df = df_orders.copy()
    today = today_ist()
    df["status"] = [payment_status(v, r) for v, r in zip(df["order_value"], df["received"])]
    df["days_outstanding"] = df["created_at"].map(lambda v: (today - parse_ts(v).date()).days if parse_ts(v) else 0)
    df["ageing"] = df["days_outstanding"].map(ageing_label)
    nxt = df["next_collection_date"].astype(str).str[:10]
    df["follow_up"] = [
        "—" if s == "Received" else ("Overdue" if n not in ("None", "nan", "") and n < str(today)
                                      else "Today" if n == str(today) else "Scheduled" if n not in ("None", "nan", "") else "Not set")
        for s, n in zip(df["status"], nxt)
    ]
    return df


def monthly_sales_vs_collections(df_orders: pd.DataFrame, df_payments: pd.DataFrame, months=6) -> pd.DataFrame:
    rows = []
    if not df_orders.empty:
        for _, r in df_orders.iterrows():
            rows.append((str(r["created_at"])[:7], "Sales booked", float(r["order_value"] or 0)))
    if not df_payments.empty:
        for _, r in df_payments.iterrows():
            rows.append((str(r["paid_on"])[:7], "Collected", float(r["amount"] or 0)))
    df = pd.DataFrame(rows, columns=["Month", "Series", "Value"])
    if df.empty:
        return df
    df = df.groupby(["Month", "Series"], as_index=False)["Value"].sum()
    keep = sorted(df["Month"].unique())[-months:]
    return df[df["Month"].isin(keep)].sort_values("Month")
