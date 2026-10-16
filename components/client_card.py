"""components/client_card.py - One client shown as a readable profile card (used by Client inspector search)."""
import pandas as pd
import streamlit as st

from components.cards import CSS as CARD_CSS, card_html, clean, esc
from components.contact import contact_links
from components.time_picker import fmt_12h
from utils.metrics import inr


def render_client_card(row, quotes: pd.DataFrame, logs: pd.DataFrame, orders: pd.DataFrame, key: str):
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    lid = row["lead_id"]
    q = quotes[quotes["lead_id"] == lid].sort_values("revision_no") if not quotes.empty else quotes
    c = logs[logs["lead_id"] == lid].sort_values("logged_at") if not logs.empty else logs
    o = orders[orders["lead_id"] == lid] if not orders.empty else orders
    latest = q.iloc[-1] if len(q) else None
    stage = str(row["final_status"])
    tone = {"Done": "green", "Cancled": "red"}.get(stage, "blue")
    pills = [(f"Stage: {stage}", tone), (f"Quotation: {row['quotation_status']}", "navy")]
    if row.get("priority") == "High":
        pills.append(("High priority", "red"))
    fields = [
        ("Product", f"{esc(row['product'])} × {row['qty']}"), ("City", esc(row.get("city"))),
        ("Source", esc(row.get("source"))), ("Received", esc(fmt_12h(row.get("ingested_at")))),
        ("Added by", esc(row.get("leads_handled_by"))), ("Salesperson", esc(row.get("assigned_salesperson"))),
        ("Quotation specialist", esc(row.get("claimed_qs_name"))), ("Next call", esc(fmt_12h(row.get("next_followup_at")))),
        ("Latest quotation", f"{esc(latest['quotation_ref'])} · {inr(latest['qut_amount'])}" if latest is not None else "Not sent yet"),
        ("Revisions", str(int(latest["revision_no"])) if latest is not None else "—"),
        ("Calls logged", str(len(c))), ("Customer responded", esc(row.get("customer_responded"))),
    ]
    if stage == "Cancled":
        fields.append(("Cancel reason", esc(row.get("lost_reason"))))
    note = None
    if len(c):
        last = c.iloc[-1]
        note = (f"<b>Last call</b> ({esc(fmt_12h(last['logged_at']))}, {esc(last.get('employee_name'))}): "
                f"{esc(last['followup_status'])} — {esc(last['notes'])}")
    elif clean(row.get("remarks"), ""):
        note = f"<b>Requirement:</b> {esc(row.get('remarks'))}"
    st.markdown(card_html(row["client_id"], row["client_name"], row.get("company_name"),
                          big=inr(latest["qut_amount"]) if latest is not None else None, pills=pills, fields=fields,
                          links=contact_links(row.get("phone_number"), row.get("email"), str(row["client_name"])),
                          note=note, accent=tone), unsafe_allow_html=True)
    if len(o):
        from utils.payment_plan import current_milestone, plan_label, stage_label, tracker_html
        oo = o.iloc[0]
        m = current_milestone(oo)
        st.markdown(f"<div class='saas-card' style='padding:12px 18px; margin-top:-4px;'>"
                    f"<div style='font-size:13.5px; color:#334155; margin-bottom:8px;'>🧾 <b>{esc(oo['order_id'])}</b> · "
                    f"received <b>{inr(oo['received'])}</b> of {inr(oo['order_value'])} · terms {plan_label(oo)} · "
                    f"{stage_label(oo)}" + (f" · next: {m['name']} {inr(m['balance'])}" if m else " · fully paid 🎉")
                    + f" · PO: {esc(oo.get('po_owner_name'), 'unclaimed')}</div>{tracker_html(oo, compact=True)}</div>",
                    unsafe_allow_html=True)
    with st.expander(f"Full history — {row['client_id']}"):
        if len(q):
            from views.quotation_portal import revision_table
            st.markdown("**Quotations**")
            st.dataframe(revision_table(q), width="stretch", hide_index=True)
        if len(c):
            st.markdown("**Calls**")
            cc = c.sort_values("logged_at", ascending=False)
            st.dataframe(pd.DataFrame({"When": cc["logged_at"].map(fmt_12h), "By": cc["employee_name"],
                                       "Outcome": cc["followup_status"], "Notes": cc["notes"]}), width="stretch", hide_index=True)
        if not len(q) and not len(c):
            st.caption("No quotations or calls yet.")
