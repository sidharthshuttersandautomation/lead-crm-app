"""
components/follow_up_cards.py - Follow-up call queue and the reusable call card
(used on the Follow-up calls page and on Alerts).
"""
import datetime
import html

import pandas as pd
import streamlit as st

from components.cards import CSS as CARD_CSS, card_html, clean
from components.contact import contact_links
from components.time_picker import fmt_12h, time_12h
from config.settings import CANCEL_CATEGORY_OPTIONS, CLOSED_STAGES, FOLLOWUP_OUTCOMES, TIME_SLOTS
from utils.metrics import call_bucket, inr
from utils.time_utils import now_ist, now_str, parse_ts, today_ist

MAX_CARDS = 50
DATE_FILTERS = {"Today": "today", "Overdue": "overdue", "Upcoming": "upcoming",
                "Not scheduled": "unscheduled", "All open": None}


def slot_label(t: datetime.time) -> str:
    for label, start, end in TIME_SLOTS:
        if start <= t.hour < end:
            return label
    return TIME_SLOTS[-1][0]


def call_counts(queue: pd.DataFrame) -> dict:
    if queue is None or queue.empty:
        return {"today": 0, "overdue": 0, "upcoming": 0, "unscheduled": 0}
    vc = queue["next_followup_at"].map(call_bucket).value_counts()
    return {k: int(vc.get(k, 0)) for k in ("today", "overdue", "upcoming", "unscheduled")}


def render_time_slot_workday_queue(db_adapter, queue: pd.DataFrame, df_latest_quotes: pd.DataFrame,
                                   df_logs: pd.DataFrame, current_user: dict, ist_now: datetime.datetime,
                                   show_owner: bool = False):
    from components.kpi_cards import render_kpi_cards
    today = ist_now.date()
    counts = call_counts(queue)
    done_today = 0
    if not df_logs.empty:
        mine = df_logs if show_owner else df_logs[df_logs["employee_id"] == current_user["employee_id"]]
        done_today = int((mine["logged_at"].astype(str).str[:10] == str(today)).sum())
    render_kpi_cards([
        {"label": "Overdue calls", "value": counts["overdue"], "icon": "⏰", "tone": "red",
         "sub": "clear these first"},
        {"label": "Due today", "value": counts["today"], "icon": "📅", "tone": "amber"},
        {"label": "Calls logged today", "value": done_today, "icon": "✅", "tone": "green"},
        {"label": "Upcoming", "value": counts["upcoming"], "icon": "🗓️", "tone": "blue"},
        {"label": "Not scheduled", "value": counts["unscheduled"], "icon": "❔", "tone": "navy",
         "help": "Open leads with no next call date"},
    ])
    st.caption(f"Now {ist_now.strftime('%d %b %Y, %I:%M %p')} IST · current slot: {slot_label(ist_now.time())}")

    c_search, c_date = st.columns([1.3, 2])
    with c_search:
        search = st.text_input("Search", placeholder="Client ID, name, company or phone",
                               key="fol_queue_search").strip().lower()
    with c_date:
        default = None if "fol_queue_date" in st.session_state else ("Overdue" if counts["overdue"] else "Today")
        date_choice = st.segmented_control("Show calls", list(DATE_FILTERS.keys()), default=default,
                                           key="fol_queue_date")
    slot_choice = st.segmented_control("Time slot", ["All slots"] + [s[0] for s in TIME_SLOTS],
                                       default="All slots", key="fol_queue_slot")

    if queue.empty:
        st.info("No open leads in your follow-up queue.")
        return
    df = queue.copy()
    df["_bucket"] = df["next_followup_at"].map(lambda v: call_bucket(v, today))
    df["_slot"] = df["next_followup_at"].map(lambda v: slot_label(parse_ts(v).time()) if parse_ts(v) else "")
    if search:
        hay = (df["client_id"].astype(str) + " " + df["client_name"].astype(str) + " "
               + df["company_name"].fillna("").astype(str) + " " + df["phone_number"].astype(str)).str.lower()
        df = df[hay.str.contains(search, regex=False)]
    wanted = DATE_FILTERS.get(date_choice or "All open")
    if wanted:
        df = df[df["_bucket"] == wanted]
    if slot_choice and slot_choice != "All slots":
        df = df[df["_slot"] == slot_choice]
    if df.empty:
        st.success("Nothing matches these filters.")
        return

    df = sort_calls(df)
    if len(df) > MAX_CARDS:
        st.warning(f"Showing the first {MAX_CARDS} of {len(df)} calls. Narrow the filters to see the rest.")
    for _, row in df.head(MAX_CARDS).iterrows():
        render_follow_up_card(db_adapter, row, df_logs, df_latest_quotes, current_user, show_owner, "q")


def sort_calls(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_prio"] = (df["priority"] != "High").astype(int)
    df["_sort_ts"] = df["next_followup_at"].fillna("9999-12-31").astype(str)
    return df.sort_values(["_prio", "_sort_ts"])


def _badge(text, bg, fg):
    return f"<span class='pill' style='background:{bg}; color:{fg};'>{html.escape(text)}</span>"


def render_follow_up_card(db_adapter, row, df_logs: pd.DataFrame, df_latest_quotes: pd.DataFrame,
                          current_user: dict, show_owner: bool = False, key_prefix: str = "q",
                          expanded: bool = False):
    lead_id = int(row["lead_id"])
    logs = df_logs[df_logs["lead_id"] == lead_id] if not df_logs.empty else pd.DataFrame()
    qrows = df_latest_quotes[df_latest_quotes["lead_id"] == lead_id] if not df_latest_quotes.empty else pd.DataFrame()
    quote = qrows.iloc[0] if not qrows.empty else None

    ts = parse_ts(row.get("next_followup_at"))
    bucket = call_bucket(row.get("next_followup_at"))
    if ts is None:
        call_text, colors = "Not scheduled", ("#F1F5F9", "#475569")
    else:
        when = "Today" if bucket == "today" else ts.strftime("%d %b")
        call_text = f"{when} @ {ts.strftime('%I:%M %p')}"
        colors = ("#FDE7EA", "#BE123C") if bucket == "overdue" else ("#FEF3C7", "#B45309")

    pills = [("High priority", "red")] if row.get("priority") == "High" else []
    pills += [(f"📞 {call_text}", "red" if bucket == "overdue" else ("grey" if ts is None else "amber")),
              (f"Follow-up #{len(logs) + 1}", "blue")]
    last_note = (f"<b>Last note:</b> {html.escape(str(logs.iloc[-1]['notes']))} "
                 f"<span style='color:#94A3B8;'>· {html.escape(str(logs.iloc[-1].get('employee_name') or ''))}, "
                 f"{fmt_12h(logs.iloc[-1]['logged_at'])}</span>") if not logs.empty else "No calls logged yet."
    fields = [("Stage", html.escape(str(row["final_status"]))),
              ("Product", f"{html.escape(str(row['product']))} × {row['qty']}"),
              ("Quotation", html.escape(str(quote["quotation_ref"])) if quote is not None else "Not sent yet"),
              ("Final price", inr(quote["qut_amount"]) if quote is not None else "—"),
              ("City", html.escape(clean(row.get("city"))))]
    if show_owner:
        fields.append(("Call owner", html.escape(clean(row.get("followup_owner_name"), "Unassigned"))))
    st.markdown(CARD_CSS + card_html(
        row["client_id"], row["client_name"], row.get("company_name"), pills=pills, fields=fields,
        links=contact_links(row.get("phone_number"), row.get("email"), str(row.get("client_name") or "")),
        note=last_note, accent="red" if bucket == "overdue" else "blue"), unsafe_allow_html=True)

    k = f"{key_prefix}_{lead_id}"
    with st.expander(f"✍️ Log this call — {row['client_name']}", expanded=expanded):
        with st.form(key=f"fol_form_{k}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                outcome = st.selectbox("Call outcome *", ["Choose..."] + FOLLOWUP_OUTCOMES, key=f"fo_{k}")
            with c2:
                reason = st.selectbox("Cancel reason (required if Cancled)", ["—"] + CANCEL_CATEGORY_OPTIONS, key=f"fr_{k}")
            notes = st.text_area("What did the client say? *", key=f"fn_{k}",
                                 placeholder="e.g. Wants revised price for 4 shutters, call back Friday 5 PM")
            d1, d2 = st.columns(2)
            with d1:
                next_date = st.date_input("Next call date", value=today_ist() + datetime.timedelta(days=1),
                                          key=f"fd_{k}", format="DD/MM/YYYY")
            with d2:
                next_time = time_12h("Next call time", key=f"ft_{k}", default=datetime.time(11, 0))
            st.caption("The next call must be in the future. It is ignored when the outcome is Done or Cancled.")

            if st.form_submit_button("Save call log"):
                if outcome == "Choose...":
                    st.error("Choose the call outcome.")
                    return
                if not notes.strip():
                    st.error("Add a short note about the call.")
                    return
                if outcome == "Cancled" and reason == "—":
                    st.error("Choose a cancel reason for a cancelled deal.")
                    return
                closed = outcome in CLOSED_STAGES
                next_dt = datetime.datetime.combine(next_date, next_time)
                if not closed and next_dt <= now_ist().replace(tzinfo=None):
                    st.error("Pick a next call date and time later than now, so this call leaves your overdue list.")
                    return
                sched = None if closed else next_dt.strftime("%Y-%m-%d %H:%M:%S")
                stamp = now_str()
                if db_adapter.insert_row("followup_logs", {
                    "lead_id": lead_id, "quotation_id": quote["quotation_id"] if quote is not None else None,
                    "employee_id": current_user["employee_id"], "followup_sequence_no": len(logs) + 1,
                    "followup_status": outcome, "cancel_category": reason if outcome == "Cancled" else None,
                    "scheduled_call_time": sched, "notes": notes.strip(), "logged_at": stamp,
                }) is None:
                    st.error(db_adapter.last_error)
                    return
                if not db_adapter.update_row("leads_master", "lead_id", lead_id, {
                    "final_status": outcome, "next_followup_at": sched,
                    "lost_reason": reason if outcome == "Cancled" else None,
                    "closed_at": stamp if closed else None, "updated_at": stamp,
                }):
                    st.error(db_adapter.last_error)
                    return
                st.toast(f"Call saved for {row['client_name']}." +
                         (f" Next call {next_dt.strftime('%d %b, %I:%M %p')}." if sched else f" Lead marked {outcome}."),
                         icon="✅")
                st.rerun(scope="app")
