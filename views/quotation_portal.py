"""views/quotation_portal.py - Quotation desk: inbound queue, claiming, quotation entry, follow-ups."""
import datetime
import html

import pandas as pd
import streamlit as st

from config.settings import APPROVER_ROLES, DISCOUNT_TYPES, MAX_REVISIONS, QUOTE_APPROVAL, QUOTE_COMPANIES
from components.follow_up_cards import render_time_slot_workday_queue
from components.contact import contact_links
from components.time_picker import fmt_12h, time_12h
from utils.queues import call_queue
from components.kpi_cards import page_title, render_kpi_cards
from utils.id_generator import generate_quotation_number
from utils.metrics import inr, latest_quotes, open_leads
from utils.time_utils import now_ist, now_str, today_ist


# ---------------------------------------------------------------- helpers
def _sla_badge(row, today):
    due = str(row.get("sla_due_date") or "")
    if due and due < str(today):
        return "<span style='background:#FEE2E2; color:#B91C1C; padding:5px 14px; border-radius:20px; font-weight:800; font-size:12px;'>SLA missed · was due " + html.escape(due) + "</span>"
    if due == str(today):
        return "<span style='background:#E0F2FE; color:#0369A1; padding:5px 14px; border-radius:20px; font-weight:800; font-size:12px;'>Due today</span>"
    return "<span style='background:#FEF3C7; color:#B45309; padding:5px 14px; border-radius:20px; font-weight:800; font-size:12px;'>Overnight · due " + html.escape(due) + "</span>"


def _lead_card(row, right_html=""):
    prio = ("<span style='background:#FDE7EA; color:#BE123C; padding:4px 12px; border-radius:20px; font-weight:800; font-size:12px; margin-right:6px;'>High priority</span>"
            if row.get("priority") == "High" else "")
    st.markdown(f"""
    <div class='saas-card'>
        <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;'>
            <span style='font-weight:800; color:#0E2C68; font-size:16px;'>{html.escape(str(row['client_name']))} · {html.escape(str(row.get('company_name') or ''))} ({html.escape(str(row['client_id']))})</span>
            <span>{prio}{right_html}</span>
        </div>
        <div style='margin-top:6px; color:#475569; font-size:13.5px;'>
            <b>Product:</b> {html.escape(str(row['product']))} (Qty {row['qty']}) &nbsp;|&nbsp;
            <b>SAM:</b> {html.escape(str(row.get('assigned_salesperson') or '—'))} &nbsp;|&nbsp;
            <b>Received:</b> {html.escape(str(row.get('ingested_at') or '')[:16])} &nbsp;|&nbsp;
            <b>Source:</b> {html.escape(str(row.get('source') or ''))}
        </div>
        {contact_links(row.get('phone_number'), row.get('email'), str(row.get('client_name') or ''))}
    </div>""", unsafe_allow_html=True)


def revision_table(history: pd.DataFrame) -> pd.DataFrame:
    """Readable revision history: list price, discount and final price per revision."""
    h = history.sort_values("revision_no")
    nets = h["qut_amount"].astype(float).tolist()
    prev_change = ["—"] + [f"{(b - a) / a * 100:+.1f}%" if a else "—" for a, b in zip(nets, nets[1:])]
    clean = lambda v: "—" if v is None or str(v) in ("None", "nan", "") else v
    return pd.DataFrame({
        "Client ID": h["client_id"].values,
        "Revision": h["quotation_ref"].values,
        "List price": h["gross_amount"].map(inr).values,
        "Discount": [f"{inr(a)} ({p:.1f}%)" if a else "—"
                     for a, p in zip(h["discount_amount"].astype(float), h["discount_percent"].astype(float))],
        "Final price": h["qut_amount"].map(inr).values,
        "Change vs previous": prev_change,
        "Status": h["quotation_status"].values,
        "Approved / rejected by": h["approved_by"].map(clean).values,
        "Shared by": h["quotation_shared_by"].map(clean).values,
        "Reason": h["revision_reason"].map(clean).values,
        "Created": h["created_at"].astype(str).str[:16].values,
    })


def _sort_queue(df):
    if df.empty:
        return df
    df = df.copy()
    df["_p"] = (df["priority"] != "High").astype(int)
    return df.sort_values(["_p", "sla_due_date", "ingested_at"]).drop(columns="_p")


# ---------------------------------------------------------------- 1. dashboard
def render_qs_performance_dashboard(db_adapter, current_user):
    page_title("Quotation desk", "Your tickets, the claim queue and today's dispatch progress.")
    qs_id = current_user["employee_id"]
    today = today_ist()

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    if df_leads.empty:
        st.info("No leads yet. New leads appear here as soon as they are saved.")
        return

    active = open_leads(df_leads)
    not_sent = active[active["quotation_status"] != "Sent"]
    mine = not_sent[not_sent["claimed_qs_id"] == qs_id]
    unclaimed = not_sent[not_sent["claimed_qs_id"].isna()]
    received_today = df_leads[df_leads["ingestion_date"] == str(today)]
    sent_today = df_leads[df_leads["quote_sent_at"].astype(str).str[:10] == str(today)]
    latest = latest_quotes(df_quotes)
    under_review = latest[latest["quotation_status"] == "Under Review"] if not latest.empty else latest

    sent_back_ids = set()
    if not latest.empty:
        sb = latest[(latest["revision_requested"] == 1) | (latest["quotation_status"] == "Rejected")]
        sent_back_ids = set(sb["lead_id"])
    late = mine[(mine["sla_due_date"].astype(str) < str(today)) & ~mine["lead_id"].isin(sent_back_ids)] if not mine.empty else mine
    my_sent_today = sent_today[sent_today["claimed_qs_id"] == qs_id] if not sent_today.empty else sent_today
    render_kpi_cards([
        {"label": "My open tickets", "value": len(mine), "icon": "📝", "tone": "blue",
         "sub": f"{len(late)} past SLA" if len(late) else "all within SLA"},
        {"label": "Waiting to be claimed", "value": len(unclaimed), "icon": "📥", "tone": "amber",
         "help": "Leads no specialist has claimed or been assigned yet"},
        {"label": "I sent today", "value": len(my_sent_today), "icon": "📤", "tone": "green",
         "sub": f"team: {len(sent_today)} of {len(received_today)} received today"},
        {"label": "Quotes under review", "value": len(under_review), "icon": "🖊️", "tone": "teal",
         "help": "Latest revision drafted but not yet approved"},
        {"label": "Sent back to me", "value": len(mine[mine["lead_id"].isin(sent_back_ids)]) if not mine.empty else 0,
         "icon": "↩️", "tone": "red", "help": "Salesperson asked for a revision"},
    ])

    st.markdown(f"##### My tickets — assigned to or claimed by {current_user['name']}")
    if mine.empty:
        st.info("You have no assigned or claimed tickets in progress.")
    for _, row in _sort_queue(mine).iterrows():
        badge = ("<span style='background:#FDE7EA; color:#BE123C; padding:5px 14px; border-radius:20px; font-weight:800; "
                 "font-size:12px;'>↩️ Revision requested</span>") if row["lead_id"] in sent_back_ids else _sla_badge(row, today)
        _lead_card(row, badge)

    st.markdown("##### Waiting to be claimed")
    if unclaimed.empty:
        st.success("Every lead has been claimed.")
    for _, row in _sort_queue(unclaimed).iterrows():
        _lead_card(row, _sla_badge(row, today))


# ---------------------------------------------------------------- 2. claim + generate
def render_qs_generator_and_claim(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>Claim tickets & create quotations</h2>", unsafe_allow_html=True)
    qs_id = current_user["employee_id"]
    today = today_ist()

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    if df_leads.empty:
        st.info("No leads yet.")
        return

    not_sent = open_leads(df_leads)
    not_sent = not_sent[not_sent["quotation_status"] != "Sent"]
    mine = _sort_queue(not_sent[not_sent["claimed_qs_id"] == qs_id])
    unclaimed = _sort_queue(not_sent[not_sent["claimed_qs_id"].isna()])

    tab_mine, tab_open = st.tabs([f"My tickets ({len(mine)})", f"Unclaimed ({len(unclaimed)})"])

    with tab_open:
        if unclaimed.empty:
            st.success("No unclaimed tickets.")
        for _, row in unclaimed.iterrows():
            _lead_card(row, _sla_badge(row, today))
            if st.button(f"Claim {row['client_id']}", key=f"claim_{row['lead_id']}"):
                if db_adapter.claim_lead(int(row["lead_id"]), qs_id):
                    st.session_state["active_claimed_lead_id"] = int(row["lead_id"])
                    st.toast(f"Claimed {row['client_id']}. Open 'My tickets' to create the quotation.", icon="✅")
                else:
                    st.warning(db_adapter.last_error)
                st.rerun()

    with tab_mine:
        if mine.empty:
            st.info("Claim a ticket from the Unclaimed tab to start a quotation.")
            return
        labels = dict(zip(mine["client_id"] + " · " + mine["client_name"], mine["lead_id"]))
        active_id = st.session_state.get("active_claimed_lead_id")
        ids = list(labels.values())
        index = ids.index(active_id) if active_id in ids else 0
        choice = st.selectbox("Ticket", list(labels.keys()), index=index)
        lead_row = mine[mine["lead_id"] == labels[choice]].iloc[0]
        _render_quotation_form_body(db_adapter, lead_row, df_quotes, current_user)


# ---------------------------------------------------------------- 3. any lead
def render_qs_detailed_form_entry(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>Quotation entry & revisions</h2>", unsafe_allow_html=True)
    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    if df_leads.empty:
        st.info("No leads yet.")
        return

    c1, c2 = st.columns([3, 1])
    with c1:
        search = st.text_input("Search client", placeholder="Type BID / client ID, client name, company or phone",
                               key="qe_search").strip().lower()
    with c2:
        include_closed = st.toggle("Include Done & Cancled", value=False)
    pool = df_leads if include_closed else open_leads(df_leads)
    if search:
        hay = (pool["client_id"].astype(str) + " " + pool["client_name"].astype(str) + " "
               + pool["company_name"].fillna("").astype(str) + " " + pool["phone_number"].astype(str)).str.lower()
        pool = pool[hay.str.contains(search, regex=False)]
    if pool.empty:
        st.info("No client matches that search. Try part of the ID (e.g. 004), the name or the company.")
        return
    labels = (pool["client_id"].astype(str) + " · " + pool["client_name"].astype(str) + " ("
              + pool["company_name"].fillna("—").astype(str) + ")")
    lookup = dict(zip(labels, pool["lead_id"]))
    st.caption(f"{len(lookup)} match(es)")
    choice = st.selectbox("Client", list(lookup.keys()))
    lead_row = pool[pool["lead_id"] == lookup[choice]].iloc[0]
    _render_quotation_form_body(db_adapter, lead_row, df_quotes, current_user)


# ---------------------------------------------------------------- shared form
def _render_quotation_form_body(db_adapter, lead_row, df_quotes, current_user):
    lead_id = int(lead_row["lead_id"])
    cid = str(lead_row["client_id"])
    now = now_ist()

    df_emp = db_adapter.fetch_all("employees")
    active_emp = df_emp[df_emp["is_active"] == 1] if not df_emp.empty else df_emp
    approvers = active_emp[active_emp["role"].isin(APPROVER_ROLES)]
    approver_map = dict(zip(approvers["full_name"] + " (" + approvers["role"] + ")", approvers["employee_id"]))
    sharer_map = dict(zip(active_emp["full_name"] + " (" + active_emp["role"] + ")", active_emp["employee_id"]))

    st.markdown("###### Lead details")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("Client ID", value=cid, disabled=True, key=f"ro_cid_{lead_id}")
        st.text_input("Client name", value=str(lead_row["client_name"]), disabled=True, key=f"ro_cn_{lead_id}")
        st.text_input("Company", value=str(lead_row.get("company_name") or ""), disabled=True, key=f"ro_co_{lead_id}")
    with c2:
        st.text_input("Phone", value=str(lead_row.get("phone_number") or ""), disabled=True, key=f"ro_ph_{lead_id}")
        st.text_input("Product", value=f"{lead_row['product']} × {lead_row['qty']}", disabled=True, key=f"ro_pr_{lead_id}")
        st.text_input("City", value=str(lead_row.get("city") or ""), disabled=True, key=f"ro_ci_{lead_id}")
    with c3:
        st.text_input("Received", value=str(lead_row.get("ingested_at") or "")[:16], disabled=True, key=f"ro_rc_{lead_id}")
        st.text_input("Salesperson", value=str(lead_row.get("assigned_salesperson") or ""), disabled=True, key=f"ro_sa_{lead_id}")
        st.text_input("Stage / quote", value=f"{lead_row['final_status']} / {lead_row['quotation_status']}",
                      disabled=True, key=f"ro_st_{lead_id}")
    if lead_row.get("remarks"):
        st.caption(f"Requirement: {lead_row['remarks']}")

    history = df_quotes[df_quotes["lead_id"] == lead_id].sort_values("revision_no") if not df_quotes.empty else pd.DataFrame()
    latest = history.iloc[-1] if not history.empty else None

    if latest is not None:
        st.markdown("###### Revision history")
        st.dataframe(revision_table(history), width="stretch", hide_index=True)

        if int(latest.get("revision_requested") or 0) == 1 or (latest["quotation_status"] == "Rejected" and latest.get("review_note")):
            st.markdown(f"""<div class='saas-card' style='border-left:4px solid #BE123C;'>
                <b style='color:#BE123C;'>↩️ Sent back for revision</b> by {html.escape(str(latest.get('reviewed_by_name') or '—'))}
                on {html.escape(str(latest.get('reviewed_at') or '')[:16])}<br>
                <span style='color:#334155;'>“{html.escape(str(latest.get('review_note') or ''))}”</span></div>""",
                        unsafe_allow_html=True)
        if latest["quotation_status"] == "Under Review":
            _render_approval_update(db_adapter, lead_row, latest, approver_map, current_user)

    # ---- new quotation or new revision
    next_rev = 0 if latest is None else int(latest["revision_no"]) + 1
    if next_rev > MAX_REVISIONS:
        st.error(f"This quotation has reached R{MAX_REVISIONS}, the revision limit. "
                 "Ask an admin to raise MAX_REVISIONS in settings if more are needed.")
        return

    heading = "Create quotation" if latest is None else f"Create revision R{next_rev}"
    st.markdown(f"###### {heading}")
    if latest is None:
        company = st.segmented_control("Quotation company", list(QUOTE_COMPANIES.keys()),
                                       default=list(QUOTE_COMPANIES.keys())[0], key=f"qco_{lead_id}") \
                  or list(QUOTE_COMPANIES.keys())[0]
        default_number = generate_quotation_number(db_adapter, now.date(), company)
    else:
        company = str(latest["quotation_number"]).split("/")[0]
        default_number = str(latest["quotation_number"])
    prev_gross = 50000.0 if latest is None else float(latest.get("gross_amount") or latest["qut_amount"])
    prev_net = None if latest is None else float(latest["qut_amount"])
    r0_net = None if history.empty else float(history.iloc[0]["qut_amount"])

    st.markdown("**Price**")
    p1, p2, p3 = st.columns([1.2, 1, 1])
    with p1:
        gross = st.number_input("List price before discount (₹) *", min_value=0.0, value=prev_gross,
                                step=1000.0, key=f"gross_{lead_id}_{next_rev}")
    with p2:
        disc_type = st.radio("Discount as", DISCOUNT_TYPES, horizontal=True, key=f"dtype_{lead_id}_{next_rev}")
    with p3:
        if disc_type == DISCOUNT_TYPES[0]:
            default_pct = float(latest.get("discount_percent") or 0) if latest is not None else 0.0
            pct = st.number_input("Discount %", min_value=0.0, max_value=100.0, value=default_pct, step=0.5,
                                  key=f"dpct_{lead_id}_{next_rev}")
            disc_amt = round(gross * pct / 100, 2)
        else:
            default_amt = float(latest.get("discount_amount") or 0) if latest is not None else 0.0
            disc_amt = st.number_input("Discount ₹", min_value=0.0, value=min(default_amt, gross), step=500.0,
                                       key=f"damt_{lead_id}_{next_rev}")
            pct = round(disc_amt / gross * 100, 2) if gross else 0.0
    net = round(gross - disc_amt, 2)
    compare = ""
    if prev_net:
        diff = net - prev_net
        compare += f" · vs previous: {'+' if diff >= 0 else '−'}{inr(abs(diff))} ({diff / prev_net * 100:+.1f}%)"
    if r0_net and next_rev > 1:
        compare += f" · vs R0: {(net - r0_net) / r0_net * 100:+.1f}%"
    st.markdown(f"<div class='saas-card' style='padding:12px 18px;'><b>{inr(gross)}</b> list − <b>{inr(disc_amt)}</b> "
                f"discount ({pct:.2f}%) = <span style='color:#047857; font-weight:800; font-size:18px;'>{inr(net)}</span> "
                f"final price<span style='color:#64748B;'>{compare}</span></div>", unsafe_allow_html=True)
    me_label = next((k for k, v in sharer_map.items() if v == current_user["employee_id"]), None)
    sharer_keys = list(sharer_map.keys())

    with st.form(f"quote_form_{lead_id}_{next_rev}"):
        m1, m2, m3 = st.columns(3)
        with m1:
            q_num = st.text_input("Quotation number *", value=default_number, disabled=latest is not None,
                                  help="Revisions keep the original number.")
            q_status = st.selectbox("Status *", ["Choose..."] + QUOTE_APPROVAL,
                                    help="Under Review = drafted, not yet approved. Approved = approved and sent to the client.")
        with m2:
            app_by = st.selectbox("Approved by (required if Approved)", ["—"] + list(approver_map.keys()))
            shared_by = st.selectbox("Shared by *", sharer_keys,
                                     index=sharer_keys.index(me_label) if me_label in sharer_keys else 0)
            approved_date = st.date_input("Approved date", value=now.date())
        with m3:
            drive_link = st.text_input("Folder link", placeholder="https://drive.google.com/...")
            comp_name_1 = st.text_input("Quoting company", value=company, disabled=True)
            requested = (latest is not None and str(latest.get("review_note") or "") not in ("", "None", "nan")
                         and (int(latest.get("revision_requested") or 0) == 1 or latest["quotation_status"] == "Rejected"))
            rev_reason = st.text_input("Reason for revision *" if latest is not None else "Notes",
                                       value=f"Requested by {latest.get('reviewed_by_name')}: {latest.get('review_note')}" if requested else "",
                                       placeholder="e.g. Client asked for 8% discount")

        f1, f2, f3 = st.columns(3)
        with f1:
            follow_req = st.selectbox("Follow-up required *", ["Yes", "No"])
        with f2:
            next_date = st.date_input("Next call date", value=now.date() + datetime.timedelta(days=3))
        with f3:
            next_time = time_12h("Next call time", key=f"qnt_{lead_id}_{next_rev}", default=datetime.time(12, 0))

        if st.form_submit_button("Save quotation"):
            errors = []
            if q_status == "Choose...":
                errors.append("choose a status")
            if gross <= 0:
                errors.append("enter a list price above zero")
            if disc_amt > gross:
                errors.append("keep the discount below the list price")
            if q_status == "Approved" and app_by == "—":
                errors.append("choose who approved it")
            if latest is not None and not rev_reason.strip():
                errors.append("give the reason for this revision")
            if latest is None and not q_num.strip():
                errors.append("enter a quotation number")
            if errors:
                st.error("Please " + "; ".join(errors) + ".")
                return

            stamp = now_str()
            quote_id = db_adapter.insert_row("quotations_master", {
                "quotation_id": db_adapter.next_quotation_id(),
                "lead_id": lead_id,
                "client_id": cid,
                "quotation_number": q_num.strip() if latest is None else str(latest["quotation_number"]),
                "revision_no": next_rev,
                "qut_amount": float(net),
                "gross_amount": float(gross),
                "discount_percent": float(pct),
                "discount_amount": float(disc_amt),
                "quotation_status": q_status,
                "follow_up_required": follow_req,
                "claimed_qs_id": lead_row.get("claimed_qs_id") or current_user["employee_id"],
                "approved_by_id": approver_map.get(app_by),
                "shared_by_id": sharer_map[shared_by],
                "folder_link": drive_link.strip() or None,
                "company_name_1": company,
                "approved_date": str(approved_date) if q_status == "Approved" else None,
                "approved_month": approved_date.strftime("%B %Y") if q_status == "Approved" else None,
                "revision_reason": rev_reason.strip() or None,
                "created_by": current_user["employee_id"],
                "created_at": stamp,
            })
            if quote_id is None:
                st.error(db_adapter.last_error)
                return

            if not _apply_quote_to_lead(db_adapter, lead_row, q_status, follow_req,
                                        f"{next_date} {next_time.strftime('%H:%M:%S')}", current_user, stamp):
                st.error(db_adapter.last_error)
                return

            st.session_state.pop("active_claimed_lead_id", None)
            label = q_num if next_rev == 0 else f"{latest['quotation_number']} R{next_rev}"
            st.toast(f"Quotation {label} saved as {q_status}.", icon="✅")
            st.rerun()


def _has(v) -> bool:
    return v is not None and str(v) not in ("", "nan", "None")


def _apply_quote_to_lead(db_adapter, lead_row, q_status, follow_req, sched_ts, current_user, stamp) -> bool:
    """Moves the lead forward after a quotation is saved or approved."""
    owner = lead_row.get("claimed_qs_id") or current_user["employee_id"]
    updates = {"claimed_qs_id": owner, "updated_at": stamp}
    if q_status == "Approved":
        updates.update({
            "quotation_status": "Sent",
            "followup_owner_id": lead_row.get("followup_owner_id") if _has(lead_row.get("followup_owner_id")) else owner,
            "next_followup_at": sched_ts if follow_req == "Yes" else None,
        })
        if not lead_row.get("quote_sent_at"):
            updates["quote_sent_at"] = stamp
        if lead_row.get("final_status") == "Pending":
            updates["final_status"] = "In Discussion"
    else:
        updates["quotation_status"] = "Under Process"
    if not lead_row.get("claimed_at"):
        updates["claimed_at"] = stamp
    return db_adapter.update_row("leads_master", "lead_id", int(lead_row["lead_id"]), updates)


def _render_approval_update(db_adapter, lead_row, latest, approver_map, current_user):
    """Record approval/rejection for the latest revision that is still under review."""
    with st.expander(f"Record approval for {latest['quotation_ref']} (currently under review)", expanded=True):
        with st.form(f"approve_{latest['quotation_id']}"):
            a1, a2, a3 = st.columns(3)
            with a1:
                decision = st.selectbox("Decision", ["Approved", "Rejected"])
            with a2:
                approver = st.selectbox("Approved / rejected by", list(approver_map.keys()) or ["—"])
            with a3:
                next_date = st.date_input("Next call date", value=today_ist() + datetime.timedelta(days=3))
                next_time = time_12h("Next call time", key=f"apt_{latest['quotation_id']}", default=datetime.time(12, 0))
            if st.form_submit_button("Save decision"):
                stamp = now_str()
                ok = db_adapter.update_row("quotations_master", "quotation_id", latest["quotation_id"], {
                    "quotation_status": decision,
                    "approved_by_id": approver_map.get(approver),
                    "approved_date": stamp[:10] if decision == "Approved" else None,
                    "approved_month": now_ist().strftime("%B %Y") if decision == "Approved" else None,
                })
                if ok:
                    ok = _apply_quote_to_lead(db_adapter, lead_row, decision, "Yes",
                                              f"{next_date} {next_time.strftime('%H:%M:%S')}", current_user, stamp)
                if not ok:
                    st.error(db_adapter.last_error)
                    return
                st.toast(f"{latest['quotation_ref']} marked {decision}.", icon="✅")
                st.rerun()


# ---------------------------------------------------------------- 4. follow-up workday
FU_VIEWS = ["📞 Claimed follow-ups", "🙋 Unclaimed follow-ups"]


def unclaimed_followups(df_leads, user):
    """Open leads that nobody has taken for follow-up yet (salespeople: only their own clients)."""
    active = open_leads(df_leads)
    if active.empty:
        return active
    un = active[active["followup_owner_id"].isna()]
    if user["role"] == "SAM":
        un = un[un["assigned_sam_id"] == user["employee_id"]]
    return un


def render_qs_followup_workday(db_adapter, current_user):
    page_title("Follow-up calls", "Claimed follow-ups have an owner; unclaimed ones are waiting for someone to take them.")
    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_logs = db_adapter.fetch_all("followup_logs")
    un = unclaimed_followups(df_leads, current_user)
    labels = {FU_VIEWS[0]: FU_VIEWS[0], FU_VIEWS[1]: f"{FU_VIEWS[1]} ({len(un)})"}
    view = st.segmented_control("Follow-ups", FU_VIEWS, key="fu_view", format_func=lambda x: labels[x],
                                default=None if "fu_view" in st.session_state else FU_VIEWS[0],
                                label_visibility="collapsed") or FU_VIEWS[0]
    if view == FU_VIEWS[1]:
        _unclaimed_followups(db_adapter, un, current_user)
        return

    show_owner, owner = False, None
    if current_user["role"] == "ADMIN":
        df_emp = db_adapter.fetch_all("employees")
        df_emp = df_emp[df_emp["is_active"] == 1]
        owners = dict(zip(df_emp["full_name"] + " (" + df_emp["employee_id"] + ")", df_emp["employee_id"]))
        pick = st.selectbox("Whose calls", ["Everyone"] + list(owners.keys()))
        owner = owners.get(pick)
        show_owner = owner is None
    elif current_user["role"] == "SAM":
        st.caption("Calls for your own clients only.")
        show_owner = True
    queue = call_queue(df_leads, current_user, owner)
    queue = queue[queue["followup_owner_id"].notna()] if not queue.empty else queue

    render_time_slot_workday_queue(db_adapter, queue, latest_quotes(df_quotes), df_logs,
                                   current_user, now_ist().replace(tzinfo=None), show_owner)


def _unclaimed_followups(db, un, user):
    from components.cards import CSS as CARD_CSS, card_html, esc
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    if un.empty:
        st.success("Every open lead has someone following up. 🎉")
        return
    st.caption("Whoever claims a follow-up first owns it: it moves to their Claimed follow-ups and their reminders."
               + (" As admin, assign them from 👥 Leads & clients → 🔀 Reassign & escalate (Move: Follow-up calls)."
                  if user["role"] == "ADMIN" else ""))
    for _, r in un.sort_values("ingested_at", ascending=False).head(40).iterrows():
        st.markdown(card_html(
            r["client_id"], r["client_name"], r.get("company_name"),
            pills=[(f"Stage: {r['final_status']}", "blue"), ("Unclaimed", "amber")],
            fields=[("Product", f"{esc(r['product'])} × {r['qty']}"), ("Salesperson", esc(r.get("assigned_salesperson"))),
                    ("Quotation", esc(r.get("quotation_status"))), ("Received", esc(fmt_12h(r.get("ingested_at")))),
                    ("Added by", esc(r.get("leads_handled_by")))],
            links=contact_links(r.get("phone_number"), r.get("email"), str(r["client_name"])), accent="amber"),
            unsafe_allow_html=True)
        if user["role"] != "ADMIN" and st.button(f"🙋 Claim follow-up for {r['client_id']}", key=f"fu_claim_{r['lead_id']}",
                                                 type="primary"):
            if db.claim_followup(int(r["lead_id"]), user["employee_id"]):
                st.toast(f"{r['client_id']} is yours to follow up. Set the first call from Claimed follow-ups.", icon="🙋")
            else:
                st.toast(db.last_error, icon="⚠️")
            st.rerun()
