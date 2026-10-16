"""views/notification_center.py - Alerts, grouped as Follow-up alerts and Quotation alerts."""
import datetime

import pandas as pd

import streamlit as st

from components.cards import CSS as CARD_CSS, card_html, clean, esc
from components.contact import contact_links
from components.follow_up_cards import render_follow_up_card, sort_calls
from components.kpi_cards import page_title, render_kpi_cards
from components.time_picker import fmt_12h, time_12h
from utils.metrics import inr, latest_quotes
from utils.notifications import collect_alerts
from utils.quote_review import approve_quotation, request_revision
from utils.time_utils import today_ist

MAX_PER_SECTION = 30
QUOTE_PAGE = "📝 Quotation entry & revisions"


def _go_to_quote(client_id, key):
    if st.session_state.get("user", {}).get("role") == "ADMIN":
        return
    if st.button("➡️ Go to the quote", key=key, type="primary"):
        st.session_state["goto"] = {"page": QUOTE_PAGE, "qe_search": str(client_id)}
        st.rerun()


def render_notification_center(db_adapter, current_user):
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    page_title("Alerts", "Follow-up alerts and quotation alerts, with the client's number one tap away.")
    role = current_user["role"]

    owner = None
    if role == "ADMIN":
        emp = db_adapter.fetch_all("employees")
        emp = emp[emp["is_active"] == 1]
        people = dict(zip(emp["full_name"] + " (" + emp["role"] + ")", emp["employee_id"]))
        pick = st.selectbox("Whose alerts", ["Everyone"] + list(people.keys()))
        owner = people.get(pick)

    a = collect_alerts(db_adapter, current_user, owner)
    n_follow = len(a["overdue"]) + len(a["today"])
    n_quote = len(a["my_tickets"]) + len(a["revisions"]) + len(a["unclaimed"]) + len(a["approvals"])
    n_collect = len(a["collect_overdue"]) + len(a["collect_today"]) + len(a["deliveries"]) + len(a["verify"])
    from views.po_portal import can_use_po
    pay_user = can_use_po(current_user)

    if role == "PO":
        render_kpi_cards([{"label": "Payment alerts", "value": n_collect, "icon": "💰", "tone": "green",
                           "sub": f"{len(a['collect_overdue'])} overdue · {len(a['collect_today'])} today · "
                                  f"{len(a['deliveries'])} deliveries soon · {len(a['verify'])} POs to verify"}], columns=2)
        _payment_alerts(a)
        return

    tiles = [
        {"label": "Follow-up alerts", "value": n_follow, "icon": "📞", "tone": "red" if len(a["overdue"]) else "amber",
         "sub": f"{len(a['overdue'])} overdue · {len(a['today'])} due today"},
        {"label": "Quotation alerts", "value": n_quote, "icon": "📄", "tone": "blue",
         "sub": " · ".join(x for x in [
             f"{len(a['my_tickets'])} to finish" if role in ("QS", "ADMIN") else "",
             f"{len(a['revisions'])} sent back" if role in ("QS", "ADMIN") else "",
             f"{len(a['approvals'])} to approve" if role in ("SAM", "ADMIN") else ""] if x)},
    ]
    if pay_user:
        tiles.append({"label": "Payment alerts", "value": n_collect, "icon": "💰", "tone": "green",
                      "sub": f"{len(a['collect_overdue'])} overdue · {len(a['collect_today'])} today · "
                             f"{len(a['deliveries'])} deliveries soon"})
    render_kpi_cards(tiles)

    tab_names = [f"📞 Follow-up alerts ({n_follow})", f"📄 Quotation alerts ({n_quote})"]
    if pay_user:
        tab_names.append(f"💰 Payment alerts ({n_collect})")
    tabs = st.tabs(tab_names)

    logs = db_adapter.fetch_all("followup_logs")
    lq = latest_quotes(db_adapter.fetch_all("quotations_master"))
    show_owner = role in ("ADMIN", "SAM") and owner is None

    # ------------------------------------------------------------- follow-ups
    with tabs[0]:
        t_over, t_today = st.tabs([f"⏰ Overdue calls ({len(a['overdue'])})", f"📅 Calls due today ({len(a['today'])})"])
        for tab, key, prefix in [(t_over, "overdue", "ao"), (t_today, "today", "at")]:
            with tab:
                df = a[key]
                if df.empty:
                    st.success("Nothing here. 🎉")
                    continue
                st.caption("Call the client, then log the call under the card. Logged calls leave this list.")
                for _, row in sort_calls(df).head(MAX_PER_SECTION).iterrows():
                    render_follow_up_card(db_adapter, row, logs, lq, current_user, show_owner, prefix)

    # ------------------------------------------------------------- quotations
    with tabs[1]:
        sub = []
        if role in ("QS", "ADMIN"):
            sub += [("tickets", f"📝 Quotation tickets to finish ({len(a['my_tickets'])})"),
                    ("revisions", f"↩️ Sent back for revision ({len(a['revisions'])})"),
                    ("unclaimed", f"📥 Unclaimed ({len(a['unclaimed'])})")]
        if role in ("SAM", "ADMIN"):
            sub.append(("approvals", f"🖊️ Waiting for approval ({len(a['approvals'])})"))
        if not sub:
            st.info("No quotation alerts for your role.")
        else:
            subtabs = st.tabs([s[1] for s in sub])
            for (kind, _), tab in zip(sub, subtabs):
                with tab:
                    _quotation_section(db_adapter, kind, a, current_user, role)

    # ------------------------------------------------------------- payments (PO team)
    if pay_user:
        with tabs[2]:
            _payment_alerts(a)


def _payment_alerts(a):
        from utils.payment_plan import current_milestone, stage_label
        groups = [("collect_overdue", "⏰ Payment calls overdue", "red"), ("collect_today", "📅 Payment calls today", "amber"),
                  ("deliveries", "🚚 Delivery in 2 days", "blue"), ("verify", "🧾 POs to verify", "amber")]
        subtabs = st.tabs([f"{t} ({len(a[k])})" for k, t, _ in groups])
        for (key, _, tone), tab in zip(groups, subtabs):
            with tab:
                if a[key].empty:
                    st.success("Nothing here. 🎉")
                for _, o in a[key].head(MAX_PER_SECTION).iterrows():
                    m = current_milestone(o)
                    st.markdown(card_html(
                        o["client_id"], o["client_name"], o.get("company_name"),
                        big=f"{inr(m['balance'])} due" if m else "Fully paid",
                        pills=[(stage_label(o), tone), (m["name"], "navy") if m else ("", "grey")],
                        fields=[("Order", esc(o["order_id"])), ("Salesperson", esc(o.get("sales_person"))),
                                ("Received", f"{inr(o['received'])} of {inr(o['order_value'])}"),
                                ("Next payment call", esc(fmt_12h(o.get("next_collection_date")))),
                                ("Expected delivery", esc(o.get("expected_delivery_date")))],
                        links=contact_links(o.get("phone_number"), o.get("email"), str(o["client_name"])),
                        note=f"<b>Last remark:</b> {esc(o.get('collection_remarks'))}" if clean(o.get("collection_remarks"), "") else None,
                        accent=tone), unsafe_allow_html=True)
                    if st.button("Open order ➜", key=f"al_po_{key}_{o['order_id']}", type="primary"):
                        st.session_state["goto"] = {"page": "🧾 PO & payments"}
                        st.session_state["po_goto"] = o["order_id"]
                        st.rerun()


def _quotation_section(db_adapter, kind, a, user, role):
    if kind == "tickets":
        df = a["my_tickets"]
        if df.empty:
            st.success("No quotation tickets waiting on you.")
        for _, r in df.head(MAX_PER_SECTION).iterrows():
            late = str(r.get("sla_due_date") or "") < str(today_ist())
            st.markdown(card_html(
                r["client_id"], r["client_name"], r.get("company_name"),
                pills=[("SLA missed" if late else "Due " + clean(r.get("sla_due_date")), "red" if late else "blue"),
                       ("High priority", "red") if r.get("priority") == "High" else ("", "grey")],
                fields=[("Product", f"{esc(r['product'])} × {r['qty']}"), ("Received", esc(fmt_12h(r.get("ingested_at")))),
                        ("Source", esc(r.get("source"))), ("Salesperson", esc(r.get("assigned_salesperson"))),
                        ("Quotation specialist", esc(r.get("claimed_qs_name"))) if role == "ADMIN" else ("", None)],
                links=contact_links(r.get("phone_number"), r.get("email"), str(r["client_name"])),
                note=f"<b>Requirement:</b> {esc(r.get('remarks'))}" if clean(r.get("remarks"), "") else None,
                accent="red" if late else "blue"), unsafe_allow_html=True)
            _go_to_quote(r["client_id"], f"gq_t_{r['lead_id']}")

    elif kind == "revisions":
        df = a["revisions"]
        if df.empty:
            st.success("Nothing has been sent back.")
        for _, q in df.head(MAX_PER_SECTION).iterrows():
            st.markdown(card_html(
                q["client_id"], q["client_name"], q.get("company_name"), big=inr(q["qut_amount"]),
                pills=[("Revision requested", "red")],
                fields=[("Quotation", esc(q["quotation_ref"])), ("Product", f"{esc(q['product'])} × {q['qty']}"),
                        ("Requested by", esc(q.get("reviewed_by_name"))), ("Requested on", esc(fmt_12h(q.get("reviewed_at"))))],
                links=contact_links(q.get("phone_number"), None, str(q["client_name"])),
                note=f"<b>What to change:</b> {esc(q.get('review_note'))}", note_warn=True, accent="red"),
                unsafe_allow_html=True)
            _go_to_quote(q["client_id"], f"gq_r_{q['quotation_id']}")

    elif kind == "unclaimed":
        df = a["unclaimed"]
        if df.empty:
            st.success("Every ticket has been claimed.")
        for _, r in df.head(MAX_PER_SECTION).iterrows():
            st.markdown(card_html(
                r["client_id"], r["client_name"], r.get("company_name"),
                pills=[("Due " + clean(r.get("sla_due_date")), "amber")],
                fields=[("Product", f"{esc(r['product'])} × {r['qty']}"), ("Received", esc(fmt_12h(r.get("ingested_at")))),
                        ("Source", esc(r.get("source")))],
                links=contact_links(r.get("phone_number"), r.get("email"), str(r["client_name"])), accent="amber"),
                unsafe_allow_html=True)
            if role == "QS" and st.button(f"Claim {r['client_id']}", key=f"al_claim_{r['lead_id']}", type="primary"):
                if db_adapter.claim_lead(int(r["lead_id"]), user["employee_id"]):
                    st.toast(f"Claimed {r['client_id']}.", icon="✅")
                else:
                    st.warning(db_adapter.last_error)
                st.rerun()

    elif kind == "approvals":
        df = a["approvals"]
        if df.empty:
            st.success("No quotations waiting for your approval.")
            return
        leads = db_adapter.fetch_all("leads_master")
        st.caption("Approve to send it to the client, or send it back to the quotation team with what to change.")
        for _, q in df.head(MAX_PER_SECTION).iterrows():
            lead = leads[leads["lead_id"] == q["lead_id"]]
            if not lead.empty:
                approval_card(db_adapter, q, lead.iloc[0], user)


def approval_card(db_adapter, q, lead, current_user):
    """A quotation waiting for the salesperson: clear summary + approve / send back."""
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    qid = q["quotation_id"]
    disc = float(q.get("discount_amount") or 0)
    with st.container(border=True):
        st.markdown(card_html(
            q["client_id"], q["client_name"], q.get("company_name"), big=inr(q["qut_amount"]),
            pills=[("Waiting for approval", "amber")],
            fields=[("Quotation", esc(q["quotation_ref"])),
                    ("Product", f"{esc(q['product'])} × {q['qty']}"),
                    ("List price", inr(q.get("gross_amount") or q["qut_amount"])),
                    ("Discount", f"{inr(disc)} ({float(q.get('discount_percent') or 0):.1f}%)" if disc else "None"),
                    ("Prepared by", esc(q.get("claimed_qs_name"))),
                    ("Prepared on", esc(fmt_12h(q.get("created_at"))))],
            links=contact_links(q.get("phone_number"), None, str(q["client_name"])),
            note=f"<b>Revision reason:</b> {esc(q.get('revision_reason'))}" if clean(q.get("revision_reason"), "") else None,
            accent="amber"), unsafe_allow_html=True)
        with st.form(f"review_{qid}", clear_on_submit=True, border=False):
            decision = st.radio("Is this quotation approved?", ["✅ Yes — approve and send to client",
                                                                "↩️ No — send back for revision"],
                                horizontal=True, key=f"rv_dec_{qid}")
            note = st.text_input("What should change? (required when sending back)", key=f"rv_note_{qid}",
                                 placeholder="e.g. Reduce price by 5%, add installation charges separately")
            c1, c2 = st.columns(2)
            with c1:
                nd = st.date_input("First follow-up call (if approved)", value=today_ist() + datetime.timedelta(days=2),
                                   key=f"rv_d_{qid}", format="DD/MM/YYYY")
            with c2:
                nt = time_12h("Call time", key=f"rv_t_{qid}", default=datetime.time(12, 0))
            if st.form_submit_button("Save decision", type="primary"):
                if decision.startswith("✅"):
                    ok = approve_quotation(db_adapter, q, lead, current_user,
                                           next_call=f"{nd} {nt.strftime('%H:%M:%S')}", note=note.strip() or None)
                    msg = f"{q['client_id']} · {q['quotation_ref']} approved."
                else:
                    if not note.strip():
                        st.error("Write what needs to change so the quotation team can revise it.")
                        return
                    ok = request_revision(db_adapter, q, lead, current_user, note.strip())
                    msg = f"{q['client_id']} · {q['quotation_ref']} sent back to {q.get('claimed_qs_name') or 'the quotation team'}."
                if ok:
                    st.toast(msg, icon="✅")
                    st.rerun()
                else:
                    st.error(db_adapter.last_error)
