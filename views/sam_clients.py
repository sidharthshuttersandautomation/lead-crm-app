"""views/sam_clients.py - Client inspector for salespeople: only their own clients."""
import datetime
import html

import pandas as pd
import streamlit as st

from components.contact import contact_links
from components.kpi_cards import page_title, render_kpi_cards
from components.time_picker import fmt_12h
from utils.metrics import call_bucket, inr, latest_quotes, open_leads
from utils.queues import my_clients
from utils.quote_review import request_revision
from utils.time_utils import today_ist


def render_sam_clients(db_adapter, current_user):
    page_title("My clients", f"Only clients assigned to {current_user['name']}.")
    leads = my_clients(db_adapter.fetch_all("leads_master"), current_user)
    if leads.empty:
        st.info("No clients are assigned to you yet.")
        return
    quotes = db_adapter.fetch_all("quotations_master")
    quotes = quotes[quotes["lead_id"].isin(leads["lead_id"])] if not quotes.empty else quotes
    logs = db_adapter.fetch_all("followup_logs")
    logs = logs[logs["lead_id"].isin(leads["lead_id"])] if not logs.empty else logs
    lq = latest_quotes(quotes)

    active = open_leads(leads)
    won = leads[leads["final_status"] == "Done"]
    amt = dict(zip(lq["lead_id"], lq["qut_amount"])) if not lq.empty else {}
    buckets = active["next_followup_at"].map(call_bucket) if not active.empty else pd.Series(dtype=str)
    render_kpi_cards([
        {"label": "My clients", "value": len(leads), "icon": "🏢", "tone": "blue", "sub": f"{len(active)} open"},
        {"label": "Open quotation value", "value": inr(sum(amt.get(i, 0) for i in active["lead_id"])),
         "icon": "📄", "tone": "teal", "help": "Latest final price of every open client"},
        {"label": "Done", "value": len(won), "icon": "🏆", "tone": "green",
         "sub": inr(sum(amt.get(i, 0) for i in won["lead_id"]))},
        {"label": "Calls overdue / today", "value": f"{int((buckets == 'overdue').sum())} / {int((buckets == 'today').sum())}",
         "icon": "📞", "tone": "red"},
    ])

    f1, f2, f3 = st.columns([1.6, 1, 1])
    with f1:
        q = st.text_input("Search my clients", placeholder="Client ID, name, company or phone", key="sc_q").strip().lower()
    with f2:
        stage = st.selectbox("Stage", ["All"] + sorted(leads["final_status"].dropna().unique()), key="sc_stage")
    with f3:
        qstat = st.selectbox("Quotation", ["All", "No quotation", "Under Review", "Approved", "Rejected", "Revision requested"],
                             key="sc_q_stat")
    view = leads.copy()
    view["quotation_ref"] = view["lead_id"].map(dict(zip(lq["lead_id"], lq["quotation_ref"])) if not lq.empty else {})
    view["final_price"] = view["lead_id"].map(amt)
    view["quote_status"] = view["lead_id"].map(dict(zip(lq["lead_id"], lq["quotation_status"])) if not lq.empty else {})
    view["revision_requested"] = view["lead_id"].map(dict(zip(lq["lead_id"], lq["revision_requested"])) if not lq.empty else {})
    last_note = logs.sort_values("logged_at").groupby("lead_id")["notes"].last() if not logs.empty else pd.Series(dtype=str)
    view["last_call_note"] = view["lead_id"].map(last_note)
    if q:
        hay = (view["client_id"].astype(str) + " " + view["client_name"].astype(str) + " "
               + view["company_name"].fillna("").astype(str) + " " + view["phone_number"].astype(str)).str.lower()
        view = view[hay.str.contains(q, regex=False)]
    if stage != "All":
        view = view[view["final_status"] == stage]
    if qstat == "No quotation":
        view = view[view["quotation_ref"].isna()]
    elif qstat == "Revision requested":
        view = view[view["revision_requested"] == 1]
    elif qstat != "All":
        view = view[view["quote_status"] == qstat]

    table = pd.DataFrame({
        "Client ID": view["client_id"], "Client": view["client_name"], "Company": view["company_name"],
        "Phone": view["phone_number"], "Product": view["product"] + " × " + view["qty"].astype(str),
        "Stage": view["final_status"], "Quotation": view["quotation_ref"].fillna("—"),
        "Final price": view["final_price"].map(lambda v: inr(v) if pd.notna(v) else "—"),
        "Quote status": view["quote_status"].fillna("—"),
        "Next call": view["next_followup_at"].map(fmt_12h), "Last call note": view["last_call_note"].fillna("—"),
    })
    st.markdown(f"###### {len(table)} client(s)")
    st.dataframe(table, width="stretch", hide_index=True)

    st.markdown("##### Client details")
    d1, d2 = st.columns([1, 1.6])
    with d1:
        scope = st.segmented_control("Show in the list", ["This month", "All time"], default="This month",
                                     key="sc_scope") or "This month"
    with d2:
        find = st.text_input("Find any of my clients", placeholder="Type a client ID, name, company or phone",
                             key="sc_find").strip().lower()
    pool = leads.copy()
    if find:
        hay = (pool["client_id"].astype(str) + " " + pool["client_name"].astype(str) + " "
               + pool["company_name"].fillna("").astype(str) + " " + pool["phone_number"].astype(str)).str.lower()
        pool = pool[hay.str.contains(find, regex=False)]
    elif scope == "This month":
        month = str(today_ist())[:7]
        active_month = (pool["ingestion_date"].astype(str).str[:7] == month) | \
                       (pool["next_followup_at"].astype(str).str[:7] == month) | \
                       (pool["updated_at"].astype(str).str[:7] == month)
        pool = pool[active_month]
    if pool.empty:
        st.info("No clients match. Switch to All time or search by name, ID or phone.")
        return
    pool = pool.sort_values("ingested_at", ascending=False)
    st.caption(f"{len(pool)} client(s) in the list" + ("" if find or scope == "All time" else
               " — received, updated or due for a call this month"))
    labels = dict(zip(pool["client_id"] + " · " + pool["client_name"].astype(str) + " · "
                      + pool["company_name"].fillna("").astype(str), pool["lead_id"]))
    pick = st.selectbox("Client", list(labels.keys()), key="sc_pick")
    view = pool
    row = view[view["lead_id"] == labels[pick]].iloc[0]
    _client_panel(db_adapter, row, quotes[quotes["lead_id"] == row["lead_id"]], logs[logs["lead_id"] == row["lead_id"]]
                  if not logs.empty else logs, current_user)


def _client_panel(db_adapter, row, hist, calls, current_user):
    from components.cards import CSS as CARD_CSS, card_html, esc
    st.markdown(CARD_CSS + card_html(
        row["client_id"], row["client_name"], row.get("company_name"),
        pills=[(f"Stage: {row['final_status']}", "blue"), ("High priority", "red") if row.get("priority") == "High" else ("", "grey")],
        fields=[("Product", f"{esc(row['product'])} × {row['qty']}"), ("City", esc(row.get("city"))),
                ("Next call", esc(fmt_12h(row.get("next_followup_at")))), ("Quotation specialist", esc(row.get("claimed_qs_name"))),
                ("Source", esc(row.get("source"))), ("Customer responded", esc(row.get("customer_responded")))],
        links=contact_links(row.get("phone_number"), row.get("email"), str(row["client_name"]))), unsafe_allow_html=True)

    O = db_adapter.fetch_all("orders")
    o = O[O["lead_id"] == row["lead_id"]] if not O.empty else O
    if not o.empty:
        from utils.payment_plan import current_milestone, stage_label, tracker_html
        o = o.iloc[0]
        m = current_milestone(o)
        st.markdown("###### Order & payments")
        st.markdown(f"<div class='saas-card'><div style='font-size:14px; color:#334155; margin-bottom:8px;'><b>{o['order_id']}</b> · "
                    f"received <b>{inr(o['received'])}</b> of {inr(o['order_value'])} · {stage_label(o)}"
                    + (f" · next: {m['name']} {inr(m['balance'])}" if m else " · fully paid 🎉") + "</div>"
                    + tracker_html(o) + "</div>", unsafe_allow_html=True)
    st.markdown("###### Quotations")
    if hist.empty:
        st.caption("No quotation yet.")
    else:
        from views.quotation_portal import revision_table
        st.dataframe(revision_table(hist), width="stretch", hide_index=True)
    st.markdown("###### Calls")
    if calls.empty:
        st.caption("No calls logged yet.")
    else:
        c = calls.sort_values("logged_at", ascending=False)
        st.dataframe(pd.DataFrame({"When": c["logged_at"].map(fmt_12h), "By": c["employee_name"],
                                   "Outcome": c["followup_status"], "Notes": c["notes"],
                                   "Next call": c["scheduled_call_time"].map(fmt_12h)}),
                     width="stretch", hide_index=True)

    if hist.empty or row["final_status"] in ("Done", "Cancled"):
        return
    latest = hist.sort_values("revision_no").iloc[-1]
    if latest["quotation_status"] == "Under Review":
        from views.notification_center import approval_card
        st.markdown("###### This quotation is waiting for your approval")
        approval_card(db_adapter, latest, row, current_user)
    elif int(latest.get("revision_requested") or 0) == 1:
        st.info(f"You asked for a revision on {str(latest.get('reviewed_at') or '')[:16]}: “{latest.get('review_note')}”. "
                "The quotation team is working on it.")
    else:
        with st.expander(f"↩️ Client wants changes? Ask the quotation team to revise {latest['quotation_ref']}"):
            with st.form(f"sc_rev_{latest['quotation_id']}", clear_on_submit=True):
                note = st.text_area("What should change? *", placeholder="e.g. Client wants 4 shutters instead of 3, and 5% less")
                if st.form_submit_button("Send back for revision"):
                    if not note.strip():
                        st.error("Write what needs to change.")
                    elif request_revision(db_adapter, latest, row, current_user, note.strip()):
                        st.toast(f"Sent to {row.get('claimed_qs_name') or 'the quotation team'} for revision.", icon="✅")
                        st.rerun()
                    else:
                        st.error(db_adapter.last_error)
