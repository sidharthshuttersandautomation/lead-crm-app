"""
utils/targets.py - Monthly targets set by admins, and how far each person has got.
"""
import calendar
import datetime

import pandas as pd
import plotly.graph_objects as go

from config.settings import STAGE_WON, TARGET_METRICS
from utils.metrics import inr, latest_quotes
from utils.time_utils import now_str, today_ist


def metrics_for(role):
    return [k for k, (_, roles, _) in TARGET_METRICS.items() if role in roles or role == "ADMIN"]


def month_key(d=None):
    return (d or today_ist()).strftime("%Y-%m")


def load_data(db):
    return {"leads": db.fetch_all("leads_master"), "quotes": db.fetch_all("quotations_master"),
            "logs": db.fetch_all("followup_logs"), "payments": db.fetch_all("payments"), "orders": db.fetch_all("orders"),
            "payfu": db.fetch_all("payment_followups")}


def _in_month(series, month):
    return series.astype(str).str[:7] == month


def actual(metric, emp_id, month, data) -> float:
    L, Q, G, P, O = data["leads"], data["quotes"], data["logs"], data["payments"], data["orders"]
    if metric == "leads_added":
        return float(len(L[(L["handled_by_lge_id"] == emp_id) & _in_month(L["ingested_at"], month)])) if not L.empty else 0.0
    if metric == "quotations_sent":
        return float(len(L[(L["claimed_qs_id"] == emp_id) & _in_month(L["quote_sent_at"], month)])) if not L.empty else 0.0
    if metric == "calls_logged":
        return float(len(G[(G["employee_id"] == emp_id) & _in_month(G["logged_at"], month)])) if not G.empty else 0.0
    if metric in ("leads_converted", "sales_value"):
        if L.empty:
            return 0.0
        done = L[(L["assigned_sam_id"] == emp_id) & (L["final_status"] == STAGE_WON) & _in_month(L["closed_at"], month)]
        if metric == "leads_converted":
            return float(len(done))
        lq = latest_quotes(Q)
        return float(lq[lq["lead_id"].isin(done["lead_id"])]["qut_amount"].sum()) if not lq.empty else 0.0
    if metric == "collections":
        if P.empty:
            return 0.0
        pm = P[_in_month(P["paid_on"], month)]
        if O.empty:
            return float(pm[pm["recorded_by"] == emp_id]["amount"].sum())
        linked = O[(O["assigned_sam_id"] == emp_id) | (O["po_owner_id"] == emp_id)]["order_id"]
        mine = pm[(pm["recorded_by"] == emp_id) | pm["order_id"].isin(linked)]
        return float(mine["amount"].sum())
    if metric == "pos_verified":
        return float(len(O[(O["po_verified_by"] == emp_id) & _in_month(O["po_verified_at"], month)])) if not O.empty else 0.0
    if metric == "payment_calls":
        F = data.get("payfu")
        if F is None or F.empty:
            return 0.0
        return float(len(F[(F["logged_by"] == emp_id) & _in_month(F["logged_at"], month) & (F["outcome"] != "Payment received")]))
    return 0.0


def get_targets(db, emp_id, month) -> dict:
    t = db.fetch_all("targets")
    if t.empty:
        return {}
    t = t[(t["employee_id"] == emp_id) & (t["month"] == month)]
    return dict(zip(t["metric"], t["value"]))


def save_targets(db, emp_id, month, values: dict, by) -> int:
    existing = db.fetch_all("targets")
    saved = 0
    for metric, value in values.items():
        row = existing[(existing["employee_id"] == emp_id) & (existing["month"] == month) & (existing["metric"] == metric)] \
            if not existing.empty else existing
        if not row.empty:
            if float(row.iloc[0]["value"]) != float(value):
                saved += db.update_row("targets", "target_id", int(row.iloc[0]["target_id"]),
                                       {"value": float(value), "set_by": by, "set_at": now_str()})
        elif value and float(value) > 0:
            saved += db.insert_row("targets", {"employee_id": emp_id, "month": month, "metric": metric,
                                               "value": float(value), "set_by": by, "set_at": now_str()}) is not None
    return saved


def pace_fraction(month) -> float:
    """Share of the month elapsed (1.0 for past months)."""
    today = today_ist()
    y, m = int(month[:4]), int(month[5:7])
    if (y, m) < (today.year, today.month):
        return 1.0
    if (y, m) > (today.year, today.month):
        return 0.0
    return today.day / calendar.monthrange(y, m)[1]


def gauge(metric, value, target, month, height=230):
    label, _, unit = TARGET_METRICS[metric]
    pct = (value / target * 100) if target else 0
    pace = target * pace_fraction(month) if target else None
    color = "#00A859" if pct >= 90 else ("#F2B84B" if pct >= 50 else "#E05A6E")
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta" if target else "number",
        value=value,
        number={"prefix": "₹" if unit == "money" else "", "valueformat": ",.0f", "font": {"size": 30, "color": "#0E2C68"}},
        delta={"reference": target, "valueformat": ",.0f", "increasing": {"color": "#00A859"},
               "decreasing": {"color": "#BE123C"}} if target else None,
        title={"text": f"<b>{label}</b><br><span style='font-size:12px;color:#64748B'>"
                       + (f"target {inr(target) if unit == 'money' else f'{target:,.0f}'} · {pct:.0f}% done" if target else "no target set")
                       + "</span>", "font": {"size": 14, "color": "#0E2C68"}},
        gauge={"axis": {"range": [0, max(target or 1, value) * 1.1], "tickfont": {"size": 10}},
               "bar": {"color": color, "thickness": 0.75},
               "bgcolor": "#F1F5F9", "borderwidth": 0,
               "steps": [{"range": [0, (target or 0) * 0.5], "color": "#FDECEF"},
                         {"range": [(target or 0) * 0.5, (target or 0) * 0.9], "color": "#FEF6E4"},
                         {"range": [(target or 0) * 0.9, (target or 0) * 1.1], "color": "#E6F6EE"}] if target else [],
               "threshold": {"line": {"color": "#0E2C68", "width": 3}, "thickness": 0.85, "value": pace} if pace else None},
    ))
    fig.update_layout(height=height, margin=dict(t=70, b=10, l=25, r=25), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def target_table(db, employees: pd.DataFrame, month, data) -> pd.DataFrame:
    rows = []
    for _, e in employees.iterrows():
        t = get_targets(db, e["employee_id"], month)
        for metric in metrics_for(e["role"]):
            if metric not in t:
                continue
            label, _, unit = TARGET_METRICS[metric]
            a = actual(metric, e["employee_id"], month, data)
            rows.append({"Employee": e["full_name"], "Role": e["role"], "Target": label,
                         "Goal": inr(t[metric]) if unit == "money" else f"{t[metric]:,.0f}",
                         "Achieved": inr(a) if unit == "money" else f"{a:,.0f}",
                         "Progress %": round(a / t[metric] * 100) if t[metric] else 0,
                         "Expected by today %": round(pace_fraction(month) * 100)})
    return pd.DataFrame(rows)
