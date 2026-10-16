"""
utils/analytics.py - Calculations behind the management modules.
Pure pandas functions: no Streamlit, so they are easy to test.
"""
import datetime

import pandas as pd

from config.settings import (HIGH_REVISION_ALERT, QS_OVERLOAD_FACTOR, STAGE_PROBABILITY,
                             STALE_FOLLOWUP_DAYS, UNCLAIMED_ALERT_WORK_HOURS,
                             UNDER_REVIEW_ALERT_HOURS, WORKDAY_END, WORKDAY_START)
from utils.metrics import latest_quotes, open_leads
from utils.time_utils import parse_ts


# ---------------------------------------------------------------- time
def working_hours_between(start: datetime.datetime, end: datetime.datetime) -> float:
    """Hours between two moments that fall inside working hours (Mon–Sat)."""
    if start is None or end is None or end <= start:
        return 0.0
    total = 0.0
    day = start.date()
    while day <= end.date():
        if day.weekday() != 6:
            open_at = datetime.datetime.combine(day, datetime.time(*WORKDAY_START))
            close_at = datetime.datetime.combine(day, datetime.time(*WORKDAY_END))
            lo, hi = max(start, open_at), min(end, close_at)
            if hi > lo:
                total += (hi - lo).total_seconds() / 3600
        day += datetime.timedelta(days=1)
    return total


def _hours(start, end):
    return (end - start).total_seconds() / 3600 if start and end else None


# ---------------------------------------------------------------- module 1
def funnel(df_leads: pd.DataFrame) -> pd.DataFrame:
    if df_leads.empty:
        return pd.DataFrame(columns=["Stage", "Leads"])
    return pd.DataFrame({
        "Stage": ["Received", "Claimed by QS", "Quotation sent", "Done"],
        "Leads": [len(df_leads), int(df_leads["claimed_at"].notna().sum()),
                  int(df_leads["quote_sent_at"].notna().sum()),
                  int((df_leads["final_status"] == "Done").sum())],
    })


def dispatch_sla(df_leads: pd.DataFrame) -> dict:
    """On-time = quotation sent on or before the SLA date set by the 5:30 PM cutoff."""
    sent = df_leads[df_leads["quote_sent_at"].notna()] if not df_leads.empty else df_leads
    if sent.empty:
        return {"sent": 0, "on_time": 0, "rate": None}
    on_time = int((sent["quote_sent_at"].astype(str).str[:10] <= sent["sla_due_date"].astype(str)).sum())
    return {"sent": len(sent), "on_time": on_time, "rate": on_time / len(sent)}


def revenue_summary(df_leads: pd.DataFrame, df_quotes: pd.DataFrame) -> dict:
    lq = latest_quotes(df_quotes)
    if df_leads.empty or lq.empty:
        return {"active_value": 0.0, "approved_value": 0.0, "won_value": 0.0, "expected_value": 0.0}
    merged = lq.merge(df_leads[["lead_id", "final_status"]], on="lead_id", suffixes=("_q", ""))
    merged["qut_amount"] = pd.to_numeric(merged["qut_amount"], errors="coerce").fillna(0)
    active = merged[~merged["final_status"].isin(["Done", "Cancled"]) & (merged["quotation_status"] != "Rejected")]
    approved_open = active[active["quotation_status"] == "Approved"]
    won = merged[merged["final_status"] == "Done"]
    expected = (active["qut_amount"] * active["final_status"].map(STAGE_PROBABILITY).fillna(0)).sum()
    return {
        "active_value": float(active["qut_amount"].sum()),
        "approved_value": float(approved_open["qut_amount"].sum()),
        "won_value": float(won["qut_amount"].sum()),
        "expected_value": float(expected),
    }


def monthly_revenue(df_leads: pd.DataFrame, df_quotes: pd.DataFrame, months: int = 6) -> pd.DataFrame:
    """Approved quotation value (by approval month) and won value (by close month)."""
    rows = []
    approved = df_quotes[df_quotes["quotation_status"] == "Approved"] if not df_quotes.empty else df_quotes
    if not approved.empty:
        last_approved = approved.sort_values("revision_no").groupby("lead_id").tail(1)
        for _, r in last_approved.iterrows():
            if r.get("approved_date"):
                rows.append((str(r["approved_date"])[:7], "Approved quotations", float(r["qut_amount"] or 0)))
    lq = latest_quotes(df_quotes)
    if not df_leads.empty and not lq.empty:
        won = df_leads[(df_leads["final_status"] == "Done") & df_leads["closed_at"].notna()]
        amounts = dict(zip(lq["lead_id"], pd.to_numeric(lq["qut_amount"], errors="coerce").fillna(0)))
        for _, r in won.iterrows():
            rows.append((str(r["closed_at"])[:7], "Done deals", float(amounts.get(r["lead_id"], 0))))
    df = pd.DataFrame(rows, columns=["Month", "Series", "Value"])
    if df.empty:
        return df
    df = df.groupby(["Month", "Series"], as_index=False)["Value"].sum()
    keep = sorted(df["Month"].unique())[-months:]
    return df[df["Month"].isin(keep)].sort_values("Month")


def unclaimed_bottlenecks(df_leads: pd.DataFrame, now: datetime.datetime) -> pd.DataFrame:
    active = open_leads(df_leads)
    if active.empty:
        return active
    q = active[active["claimed_qs_id"].isna() & (active["quotation_status"] != "Sent")].copy()
    if q.empty:
        return q
    q["waiting_work_hours"] = q["ingested_at"].map(lambda v: round(working_hours_between(parse_ts(v), now), 1))
    return q[q["waiting_work_hours"] >= UNCLAIMED_ALERT_WORK_HOURS].sort_values("waiting_work_hours", ascending=False)


def last_activity(df_leads: pd.DataFrame, df_logs: pd.DataFrame) -> pd.Series:
    """Latest of: last call logged, quotation sent, lead received."""
    last_call = df_logs.groupby("lead_id")["logged_at"].max() if not df_logs.empty else pd.Series(dtype=object)
    def pick(row):
        candidates = [row.get("ingested_at"), row.get("quote_sent_at"), last_call.get(row["lead_id"])]
        stamps = [parse_ts(c) for c in candidates if c is not None and str(c) not in ("nan", "None")]
        stamps = [s for s in stamps if s]
        return max(stamps) if stamps else None
    return df_leads.apply(pick, axis=1) if not df_leads.empty else pd.Series(dtype=object)


def stale_followups(df_leads: pd.DataFrame, df_logs: pd.DataFrame, now: datetime.datetime) -> pd.DataFrame:
    active = open_leads(df_leads)
    if active.empty:
        return active
    q = active[active["quotation_status"] == "Sent"].copy()
    if q.empty:
        return q
    q["last_activity"] = last_activity(q, df_logs)
    q["days_silent"] = q["last_activity"].map(lambda t: (now - t).days if t else None)
    q = q[q["days_silent"].fillna(0) > STALE_FOLLOWUP_DAYS]
    q["last_activity"] = q["last_activity"].map(lambda t: t.strftime("%Y-%m-%d %H:%M") if t else "")
    return q.sort_values("days_silent", ascending=False)


def pending_dispatches(df_quotes: pd.DataFrame, now: datetime.datetime) -> pd.DataFrame:
    lq = latest_quotes(df_quotes)
    if lq.empty:
        return lq
    q = lq[(lq["quotation_status"] == "Under Review") & ~lq["final_status"].isin(["Done", "Cancled"])].copy()
    if q.empty:
        return q
    q["hours_waiting"] = q["created_at"].map(lambda v: round(_hours(parse_ts(v), now) or 0, 1))
    q["overdue"] = q["hours_waiting"] > UNDER_REVIEW_ALERT_HOURS
    return q.sort_values("hours_waiting", ascending=False)


# ---------------------------------------------------------------- module 2
def qs_load(df_leads: pd.DataFrame, df_quotes: pd.DataFrame, df_emp: pd.DataFrame, today: datetime.date) -> pd.DataFrame:
    qs = df_emp[(df_emp["role"] == "QS") & (df_emp["is_active"] == 1)]
    if qs.empty:
        return pd.DataFrame()
    active = open_leads(df_leads)
    lq = latest_quotes(df_quotes)
    rows = []
    for _, e in qs.iterrows():
        mine = active[active["claimed_qs_id"] == e["employee_id"]] if not active.empty else active
        in_progress = mine[mine["quotation_status"] != "Sent"] if not mine.empty else mine
        late = in_progress[in_progress["sla_due_date"].astype(str) < str(today)] if not in_progress.empty else in_progress
        review = lq[(lq["claimed_qs_id"] == e["employee_id"]) & (lq["quotation_status"] == "Under Review")] if not lq.empty else lq
        sent_today = df_leads[(df_leads["claimed_qs_id"] == e["employee_id"]) &
                              (df_leads["quote_sent_at"].astype(str).str[:10] == str(today))] if not df_leads.empty else df_leads
        calls_owned = active[active["followup_owner_id"] == e["employee_id"]] if not active.empty else active
        rows.append({"employee_id": e["employee_id"], "Specialist": e["full_name"],
                     "Open tickets": len(in_progress), "Past SLA": len(late),
                     "Under review": len(review), "Sent today": len(sent_today),
                     "Follow-ups owned": len(calls_owned)})
    df = pd.DataFrame(rows)
    avg = df["Open tickets"].mean()
    df["Load"] = df["Open tickets"].map(
        lambda n: "Overloaded" if avg and n > avg * QS_OVERLOAD_FACTOR else ("Light" if n < avg * 0.5 else "Balanced"))
    return df


def lge_scorecard(df_leads: pd.DataFrame) -> pd.DataFrame:
    if df_leads.empty:
        return pd.DataFrame()
    g = df_leads.groupby(["leads_handled_by", "source"])
    out = pd.DataFrame({
        "Leads": g.size(),
        "Quoted": g["quote_sent_at"].apply(lambda s: s.notna().sum()),
        "Done": g["final_status"].apply(lambda s: (s == "Done").sum()),
        "Cancled": g["final_status"].apply(lambda s: (s == "Cancled").sum()),
    }).reset_index().rename(columns={"leads_handled_by": "Added by", "source": "Source"})
    out["Lead→quote %"] = (out["Quoted"] / out["Leads"] * 100).round(0)
    out["Lead→won %"] = (out["Done"] / out["Leads"] * 100).round(0)
    return out.sort_values(["Added by", "Leads"], ascending=[True, False])


def sam_matrix(df_leads: pd.DataFrame, df_quotes: pd.DataFrame) -> pd.DataFrame:
    if df_leads.empty:
        return pd.DataFrame()
    lq = latest_quotes(df_quotes)
    amounts = dict(zip(lq["lead_id"], pd.to_numeric(lq["qut_amount"], errors="coerce").fillna(0))) if not lq.empty else {}
    rows = []
    for sam, grp in df_leads.groupby("assigned_salesperson"):
        won = grp[grp["final_status"] == "Done"]
        lost = grp[grp["final_status"] == "Cancled"]
        won_vals = [amounts.get(i, 0) for i in won["lead_id"]]
        closed = len(won) + len(lost)
        top = lost["lost_reason"].dropna().value_counts()
        rows.append({"Salesperson": sam, "Leads": len(grp), "Open": len(grp) - closed,
                     "Done": len(won), "Cancled": len(lost),
                     "Win rate %": round(len(won) / closed * 100) if closed else None,
                     "Won value": sum(won_vals),
                     "Avg deal": (sum(won_vals) / len(won_vals)) if won_vals else 0,
                     "Biggest deal": max(won_vals) if won_vals else 0,
                     "Top loss reason": f"{top.index[0]} ({top.iloc[0]})" if not top.empty else "—"})
    return pd.DataFrame(rows).sort_values("Won value", ascending=False)


# ---------------------------------------------------------------- module 3
def revision_governance(df_quotes: pd.DataFrame) -> pd.DataFrame:
    if df_quotes.empty:
        return pd.DataFrame()
    rows = []
    for (lead_id, number), grp in df_quotes.sort_values("revision_no").groupby(["lead_id", "quotation_number"]):
        first, last = grp.iloc[0], grp.iloc[-1]
        a0, a1 = float(first["qut_amount"] or 0), float(last["qut_amount"] or 0)
        rows.append({"lead_id": lead_id, "Quotation": number, "Client": f"{last['client_name']} ({last['client_id']})",
                     "Revisions": int(last["revision_no"]), "Latest": last["quotation_ref"],
                     "R0 amount": a0, "Latest amount": a1,
                     "Change %": round((a1 - a0) / a0 * 100, 1) if a0 else None,
                     "Latest status": last["quotation_status"], "Lead stage": last["final_status"],
                     "Last reason": last.get("revision_reason") or "—",
                     "Flag": "High negotiation" if int(last["revision_no"]) >= HIGH_REVISION_ALERT else ""})
    return pd.DataFrame(rows).sort_values(["Revisions", "Change %"], ascending=[False, True])
