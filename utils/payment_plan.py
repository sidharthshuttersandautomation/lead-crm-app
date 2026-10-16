"""
utils/payment_plan.py - The 50 / 40 / 10 payment plan for every order.

Milestones are calculated, not stored: the total received on an order is
allocated in order to Advance -> Dispatch -> Installation. So any payment,
recorded anywhere, moves the tracker forward correctly.
"""
import datetime
import json

import pandas as pd

from config.settings import DELIVERY_ALERT_DAYS, PAYMENT_PLAN
from utils.time_utils import parse_ts, today_ist

TRACKER_STEPS = ["PO received", "PO verified", "Advance received", "Dispatched", "Dispatch payment received",
                 "Installed", "Final payment received"]


def _d(value):
    ts = parse_ts(value)
    return ts.date() if ts else None


def milestones(order) -> list:
    """[{name, percent, amount, received, balance, due, due_note, status}] for one order row."""
    value = float(order.get("order_value") or 0)
    left = float(order.get("received") or 0)
    verified = _d(order.get("po_verified_at"))
    expected = _d(order.get("expected_delivery_date"))
    dispatched = _d(order.get("dispatched_at"))
    installed = _d(order.get("installed_at"))
    today = today_ist()
    out = []
    plan = plan_of(order)
    for (name, _default, trigger), pct in zip(PAYMENT_PLAN, plan):
        amount = round(value * pct / 100, 2)
        got = min(left, amount)
        left -= got
        if trigger == "po":
            due, note = verified, ("on PO verification" if verified else "after PO is verified")
        elif trigger == "dispatch":
            due = dispatched or expected
            note = "dispatched" if dispatched else ("expected delivery" if expected else "after PO is verified")
        else:
            due = installed or ((expected + datetime.timedelta(days=7)) if expected else None)
            note = "installed" if installed else ("estimated, after installation" if expected else "after installation")
        balance = round(amount - got, 2)
        if pct == 0:
            status = "Not part of the terms"
        elif balance <= 0.5:
            status = "Received"
        elif due is None or due > today:
            status = "Partly received" if got > 0 else "Not due yet"
        else:
            status = "Overdue" if due < today else "Due today"
            if got > 0:
                status = f"Partly received · {status.lower()}"
        out.append({"name": name, "percent": pct, "amount": amount, "received": round(got, 2), "balance": balance,
                    "due": due, "due_note": note, "status": status, "trigger": trigger})
    return out


def plan_of(order) -> tuple:
    """(advance %, before-dispatch %, after-installation %) for this order; standard 50/40/10 if not set."""
    vals = []
    for key, (_, default, _) in zip(("plan_advance", "plan_dispatch", "plan_install"), PAYMENT_PLAN):
        v = order.get(key)
        try:
            v = float(v)
            vals.append(default if v != v else v)      # NaN -> default
        except (TypeError, ValueError):
            vals.append(default)
    return tuple(vals)


def plan_label(order) -> str:
    return " / ".join(f"{p:g}%" for p in plan_of(order))


def current_milestone(order):
    """The first milestone that still has a balance (None when fully paid)."""
    return next((m for m in milestones(order) if m["balance"] > 0.5 and m["percent"] > 0), None)


def tracker(order) -> tuple:
    """(list of (step, done), percent complete). Payment steps not in the client's terms are left out."""
    ms = milestones(order)
    pct = [m["percent"] for m in ms]
    all_steps = [("PO received", True, True), ("PO verified", bool(order.get("po_verified_at")), True),
                 (f"Advance {pct[0]:g}% received", ms[0]["balance"] <= 0.5, pct[0] > 0),
                 ("Dispatched", bool(order.get("dispatched_at")), True),
                 (f"Dispatch {pct[1]:g}% received", ms[1]["balance"] <= 0.5, pct[1] > 0),
                 ("Installed", bool(order.get("installed_at")), True),
                 (f"Final {pct[2]:g}% received", ms[2]["balance"] <= 0.5, pct[2] > 0)]
    steps = [(name, ok) for name, ok, used in all_steps if used]
    return steps, round(sum(ok for _, ok in steps) / len(steps) * 100)


def stage_label(order) -> str:
    if not order.get("po_verified_at"):
        return "PO to verify"
    m = current_milestone(order)
    if m is None:
        return "Fully paid"
    if m["trigger"] == "po":
        return "Collect advance"
    if m["trigger"] == "dispatch":
        return "Collect before dispatch" if not order.get("dispatched_at") else "Collect dispatch payment"
    return "Awaiting installation" if not order.get("installed_at") else "Collect final payment"


def checks(order) -> dict:
    try:
        return json.loads(order.get("po_checks") or "{}")
    except Exception:
        return {}


def tracker_html(order, compact=False) -> str:
    steps, pct = tracker(order)
    dots = "".join(
        f"<div style='flex:1; text-align:center; min-width:0;'>"
        f"<div style='width:{18 if compact else 26}px; height:{18 if compact else 26}px; margin:0 auto; border-radius:50%;"
        f" background:{'#00A859' if ok else '#E2E8F0'}; color:#FFFFFF; font-size:{11 if compact else 13}px; font-weight:800;"
        f" display:flex; align-items:center; justify-content:center;'>{'✓' if ok else i + 1}</div>"
        + ("" if compact else f"<div style='font-size:11.5px; color:{'#0E2C68' if ok else '#94A3B8'}; margin-top:4px;"
                              f" font-weight:{700 if ok else 500}; line-height:1.2;'>{step}</div>")
        + "</div>" for i, (step, ok) in enumerate(steps))
    bar = (f"<div style='background:#E2E8F0; height:6px; border-radius:6px; margin:{'6px' if compact else '10px'} 0 2px;'>"
           f"<div style='width:{pct}%; background:linear-gradient(90deg,#00A859,#184B9C); height:100%; border-radius:6px;'></div></div>")
    return (f"<div style='display:flex; gap:4px; align-items:flex-start;'>{dots}</div>{bar}"
            f"<div style='font-size:12px; color:#64748B; text-align:right;'>{pct}% complete</div>")


def payment_alerts(orders: pd.DataFrame, owner: str = None) -> dict:
    """Things the PO / payment team should act on today."""
    empty = orders.iloc[0:0] if not orders.empty else orders
    out = {"verify": empty, "calls_overdue": empty, "calls_today": empty, "deliveries": empty}
    if orders.empty:
        return out
    df = orders if owner is None else orders[(orders["po_owner_id"] == owner) | orders["po_owner_id"].isna()]
    today = str(today_ist())
    open_ = df[df["balance"] > 0.5]
    out["verify"] = df[df["po_verified_at"].isna()]
    nxt = open_["next_collection_date"].astype(str).str[:10]
    has = open_["next_collection_date"].notna() & (nxt != "None") & (nxt != "nan")
    out["calls_overdue"] = open_[has & (nxt < today)]
    out["calls_today"] = open_[has & (nxt == today)]
    soon = str(today_ist() + datetime.timedelta(days=DELIVERY_ALERT_DAYS))
    exp = open_["expected_delivery_date"].astype(str).str[:10]
    not_dispatched = open_["dispatched_at"].isna()
    out["deliveries"] = open_[not_dispatched & open_["expected_delivery_date"].notna() & (exp <= soon)]
    return out
