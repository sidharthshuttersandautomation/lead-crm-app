"""
components/call_reminder.py - On-screen reminder that appears 2 minutes before a
scheduled call and stays until the call is logged or the reminder is snoozed.
Checks every 30 seconds without reloading the rest of the page.
"""
import datetime
import html

import pandas as pd
import streamlit as st

from components.contact import contact_links
from components.desktop_notify import notify
from utils.metrics import open_leads
from utils.queues import call_queue
from utils.time_utils import now_ist, parse_ts

LEAD_MINUTES = 2
LATE_REPEAT_MINUTES = 10   # a second desktop alert if the call is still not logged this long after its time
SNOOZE_CHOICES = [5, 15, 30]
MAX_SHOWN = 3
FOLLOWUP_PAGE = "📞 Follow-up calls"

CSS = """
<style>
.rem { position: relative; display: grid; grid-template-columns: 56px 1fr auto; gap: 16px; align-items: center;
  background: linear-gradient(120deg, #184B9C 0%, #0E2C68 100%); color: #FFFFFF; border-radius: 16px;
  padding: 16px 20px; margin: 0 0 6px; box-shadow: 0 10px 28px rgba(14,44,104,0.25); overflow: hidden; }
.rem::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 6px; background: #00A859; }
.rem.late::before { background: #F43F5E; }
.rem .ic { width: 52px; height: 52px; border-radius: 50%; background: rgba(255,255,255,0.12); display: flex;
  align-items: center; justify-content: center; font-size: 24px; animation: rem-ring 1.6s ease-in-out infinite; }
.rem .nm { font-size: 18px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.01em; }
.rem .chips { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; }
.rem .chip { background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.18); color: #E3ECFA;
  padding: 2px 10px; border-radius: 20px; font-size: 12.5px; font-weight: 600; }
.rem .chip.id { background: #FFFFFF; color: #0E2C68; font-weight: 800; }
.rem .when { text-align: right; }
.rem .when .tm { font-size: 22px; font-weight: 800; color: #FFFFFF; font-variant-numeric: tabular-nums; }
.rem .when .st { display: inline-block; margin-top: 4px; padding: 3px 12px; border-radius: 20px; font-size: 12.5px;
  font-weight: 800; background: #00A859; color: #FFFFFF; }
.rem.late .when .st { background: #F43F5E; }
.rem .links { grid-column: 2 / 4; }
.rem .links .call-btn.phone { background: #00A859; }
.rem .links .call-btn.wa { background: rgba(255,255,255,0.95); }
[class*="st-key-remact_"] [data-testid="stBaseButton-secondary"] { background: #FFFFFF !important; color: #184B9C !important;
  border: 1.5px solid #C9D6EE !important; box-shadow: none !important; }
[class*="st-key-remact_"] [data-testid="stBaseButton-secondary"]:hover { border-color: #184B9C !important; }
[class*="st-key-remact_"] { margin-bottom: 14px; }
@keyframes rem-ring { 0%, 100% { transform: rotate(0); } 10% { transform: rotate(-14deg); } 20% { transform: rotate(14deg); }
  30% { transform: rotate(-10deg); } 40% { transform: rotate(10deg); } 50% { transform: rotate(0); } }
@media (max-width: 760px) { .rem { grid-template-columns: 44px 1fr; } .rem .when { grid-column: 2; text-align: left; }
  .rem .links { grid-column: 1 / 3; } }
@media (prefers-reduced-motion: reduce) { .rem .ic { animation: none; } }
</style>
"""


def _due_calls(db, user, now):
    leads = db.fetch_all("leads_master")
    if leads.empty:
        return leads
    if user["role"] == "ADMIN":
        queue = open_leads(leads)
        queue = queue[queue["followup_owner_id"] == user["employee_id"]]
    else:
        queue = call_queue(leads, user)
    if queue.empty:
        return queue
    ts = queue["next_followup_at"].map(parse_ts)
    window_end = now + datetime.timedelta(minutes=LEAD_MINUTES)
    mask = ts.map(lambda t: t is not None and t.date() == now.date() and t <= window_end)
    due = queue[mask].copy()
    if due.empty:
        return due
    due["_ts"] = ts[mask]

    sn = db.fetch_all("call_snoozes")
    if not sn.empty:
        sn = sn[(sn["employee_id"] == user["employee_id"]) & (sn["snoozed_until"].astype(str) > now.strftime("%Y-%m-%d %H:%M:%S"))]
        snoozed = set(zip(sn["lead_id"], sn["scheduled_for"].astype(str)))
        due = due[[(lid, str(nf)) not in snoozed for lid, nf in zip(due["lead_id"], due["next_followup_at"])]]
    return due.sort_values("_ts")


def _due_payment_calls(db, user, now):
    """Payment calls (PO & payments) due within the reminder window, shaped like call rows."""
    from views.po_portal import can_use_po
    if not can_use_po(user):
        return pd.DataFrame()
    from utils.payment_plan import current_milestone, stage_label
    orders = db.fetch_all("orders")
    if orders.empty:
        return orders
    me = user["employee_id"]
    mine = orders[(orders["po_owner_id"] == me) | (orders["po_owner_id"].isna() & (user["role"] == "PO"))]
    mine = mine[mine["balance"] > 0.5]
    rows = []
    window_end = now + datetime.timedelta(minutes=LEAD_MINUTES)
    for _, o in mine.iterrows():
        ts = parse_ts(o.get("next_collection_date"))
        if not ts or len(str(o.get("next_collection_date"))) <= 10 or ts.date() != now.date() or ts > window_end:
            continue
        m = current_milestone(o)
        rows.append({"lead_id": int(o["lead_id"]), "client_id": o["client_id"], "client_name": o["client_name"],
                     "company_name": o.get("company_name"), "phone_number": o.get("phone_number"),
                     "product": f"{m['name']} · {m['balance']:,.0f} due" if m else "Payment",
                     "final_status": stage_label(o), "next_followup_at": str(o["next_collection_date"]),
                     "_ts": ts, "_kind": "pay", "_order": o["order_id"]})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    sn = db.fetch_all("call_snoozes")
    if not sn.empty:
        sn = sn[(sn["employee_id"] == me) & (sn["snoozed_until"].astype(str) > now.strftime("%Y-%m-%d %H:%M:%S"))]
        snoozed = set(zip(sn["lead_id"], sn["scheduled_for"].astype(str)))
        df = df[[(l, str(n)) not in snoozed for l, n in zip(df["lead_id"], df["next_followup_at"])]]
    return df


@st.fragment(run_every="30s")
def render_call_reminders(db, user):
    now = now_ist().replace(tzinfo=None)
    try:
        due = _due_calls(db, user, now)
        pay = _due_payment_calls(db, user, now)
        if due is not None and not due.empty:
            due = due.assign(_kind="call", _order=None)
        due = pd.concat([d for d in (due, pay) if d is not None and not d.empty]) if \
            ((due is not None and not due.empty) or not pay.empty) else pd.DataFrame()
    except Exception as exc:  # a reminder must never break the page
        print("Call reminder failed:", exc)
        return
    if due is None or due.empty:
        return

    st.markdown(CSS, unsafe_allow_html=True)
    desktop = []
    for _, row in due.iterrows():
        mins_left = (row["_ts"] - now).total_seconds() / 60
        tag = f"{row.get('_kind', 'call')}|{int(row['lead_id'])}|{row['next_followup_at']}"
        body = f"{row['client_id']} · {row.get('company_name') or ''} · {row.get('phone_number') or ''}"
        if mins_left >= -LATE_REPEAT_MINUTES:
            desktop.append({"tag": tag, "title": (f"💰 Payment call: {row['client_name']}" if row.get("_kind") == "pay"
                                                  else f"📞 Call {row['client_name']}") + f" at {row['_ts'].strftime('%I:%M %p')}",
                            "body": body})
        else:
            desktop.append({"tag": tag + "|late", "body": body,
                            "title": f"⏰ Still pending: call {row['client_name']} ({row['_ts'].strftime('%I:%M %p')})"})
    notify(desktop)
    seen = st.session_state.setdefault("reminded_calls", set())
    due = due.assign(_gap=(due["_ts"] - now).map(lambda d: abs(d.total_seconds()))).sort_values("_gap")
    rows = list(due.head(MAX_SHOWN + 5).iterrows())
    for i, (_, row) in enumerate(rows):
        lead_id, sched = int(row["lead_id"]), str(row["next_followup_at"])
        if (lead_id, sched) not in seen:
            seen.add((lead_id, sched))
            st.toast(f"📞 Call {row['client_name']} at {row['_ts'].strftime('%I:%M %p')}", icon="⏰")
        if i == 1:
            more = st.expander(f"⏰ {len(due) - 1} more call(s) due now", expanded=False)
        if i == 0:
            _reminder(db, user, row, now, compact=False)
        else:
            with more:
                _reminder(db, user, row, now, compact=True)
    if len(due) > len(rows):
        st.caption(f"+ {len(due) - len(rows)} more — see Follow-up calls.")


def _reminder(db, user, row, now, compact):
    lead_id, sched = int(row["lead_id"]), str(row["next_followup_at"])
    kind = row.get("_kind") or "call"
    is_pay = kind == "pay"
    title = "Payment call:" if is_pay else "Call"
    mins = int((row["_ts"] - now).total_seconds() // 60)
    when = (f"in {mins + 1} min" if mins >= 0 else
            f"{-mins} min late" if -mins < 60 else f"{-mins // 60} h {-mins % 60} min late")
    late = mins < 0
    if compact:
        st.markdown(f"""<div class='saas-card' style='padding:10px 16px; margin-bottom:6px; display:flex;
            justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>
            <div><b style='color:#0E2C68;'>{'💰 ' if is_pay else ''}{html.escape(str(row['client_name']))}</b>
              <span style='color:#64748B;'> · {html.escape(str(row['client_id']))} · {row['_ts'].strftime('%I:%M %p')}</span>
              <span class='pill' style='background:{"#FDE7EA" if late else "#E3F6EC"}; color:{"#BE123C" if late else "#047857"};'>{when}</span></div>
            <div>{contact_links(row.get('phone_number'), None, str(row['client_name'])).replace("margin:10px 0 2px;", "margin:0;")}</div>
          </div>""", unsafe_allow_html=True)
    else:
        chips = "".join(f"<span class='chip{' id' if i == 0 else ''}'>{html.escape(str(v))}</span>"
                        for i, v in enumerate([row["client_id"], row.get("company_name"), row.get("product"),
                                               f"Stage: {row['final_status']}"]) if v and str(v) not in ("None", "nan"))
        st.markdown(f"""
        <div class='rem{' late' if late else ''}'>
          <div class='ic'>📞</div>
          <div><div class='nm'>{'💰 ' if is_pay else ''}{title} {html.escape(str(row['client_name']))}</div><div class='chips'>{chips}</div></div>
          <div class='when'><div class='tm'>{row['_ts'].strftime('%I:%M %p')}</div><div class='st'>{when}</div></div>
          <div class='links'>{contact_links(row.get('phone_number'), None, str(row['client_name']))}</div>
        </div>""", unsafe_allow_html=True)
    with st.container(key=f"remact_{kind}_{lead_id}"):
        cols = st.columns([1.3] + [1] * len(SNOOZE_CHOICES) + [1.6])
        with cols[0]:
            if st.button("✍️ Log payment call" if is_pay else "✍️ Log this call", key=f"rem_log_{kind}_{lead_id}",
                         type="primary", width="stretch"):
                if is_pay:
                    st.session_state["goto"] = {"page": "🧾 PO & payments"}
                    st.session_state["po_goto"] = row["_order"]
                else:
                    st.session_state["goto"] = {"page": FOLLOWUP_PAGE, "fol_queue_search": str(row["client_id"]),
                                                "fol_queue_date": "All open"}
                st.rerun(scope="app")
        for i, minutes in enumerate(SNOOZE_CHOICES):
            with cols[i + 1]:
                if st.button(f"😴 {minutes} min", key=f"rem_snz_{kind}_{lead_id}_{minutes}", width="stretch",
                             help=f"Snooze this reminder for {minutes} minutes"):
                    db.insert_row("call_snoozes", {
                        "lead_id": lead_id, "employee_id": user["employee_id"], "scheduled_for": sched,
                        "snoozed_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "snoozed_until": (now + datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S"),
                        "minutes": minutes})
                    st.rerun()
