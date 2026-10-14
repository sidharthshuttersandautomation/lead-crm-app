"""
views/quotation_portal.py - Quotation Specialist Workstation.
"""
import datetime
import pandas as pd
import streamlit as st
from config.settings import TEAM_MEMBERS, IST


def get_current_ist_time():
    return datetime.datetime.now(IST)


def render_qs_performance_dashboard(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📈 Performance & Progress Control Desk</h2>", unsafe_allow_html=True)
    qs_name = current_user.get("name") or "Quotation Specialist"

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")

    st.markdown("##### 📊 Operational KPI Summary")
    total_quotes = len(df_quotes) if not df_quotes.empty else 0
    approved_quotes = len(df_quotes[df_quotes["quotation_status"] == "Approved"]) if not df_quotes.empty else 0
    rejected_quotes = len(df_quotes[df_quotes["quotation_status"] == "Rejected"]) if not df_quotes.empty else 0
    my_quotes = len(df_quotes[df_quotes["quotation_shared_by"] == qs_name]) if not df_quotes.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#184B9C; margin:0;'>{total_quotes}</h3><p style='margin:0; font-weight:700;'>Total System Quotes</p></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#00A859; margin:0;'>{approved_quotes}</h3><p style='margin:0; font-weight:700;'>Approved Quotes</p></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#E11D48; margin:0;'>{rejected_quotes}</h3><p style='margin:0; font-weight:700;'>Rejected Quotes</p></div>", unsafe_allow_html=True)
    with c4:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#184B9C; margin:0;'>{my_quotes}</h3><p style='margin:0; font-weight:700;'>Quotes Prepared By You</p></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 📋 Today's Assigned Quotation Tasks")

    if not df_leads.empty:
        unassigned = df_leads[df_leads["claimed_qs_id"] == "Unassigned"]
        if not unassigned.empty:
            now_ist = get_current_ist_time()
            cutoff_today = now_ist.replace(hour=17, minute=30, second=0, microsecond=0)

            for _, row in unassigned.iterrows():
                cid = row.get("client_id", "N/A")
                cname = row.get("client_name", "N/A")
                comp = row.get("company_name", "N/A")
                prod = row.get("product", "N/A")

                is_after_cutoff = now_ist > cutoff_today

                if not is_after_cutoff:
                    badge_html = "<span style='background:#E0F2FE; color:#0284C7; padding:5px 14px; border-radius:20px; font-weight:800; font-size:12px;'>📋 TODAY'S TASK: SAME DAY DISPATCH SCHEDULED</span>"
                else:
                    badge_html = "<span style='background:#FEF3C7; color:#D97706; padding:5px 14px; border-radius:20px; font-weight:800; font-size:12px;'>📅 OVERNIGHT TASK: NEXT DAY DISPATCH SCHEDULED</span>"

                st.markdown(f"""
                <div class='saas-card'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <span style='font-weight:800; color:#0E2C68; font-size:16px;'>👤 {cname} | {comp} ({cid})</span>
                        {badge_html}
                    </div>
                    <div style='margin-top:8px; color:#475569; font-size:13.5px;'>
                        📦 <b>Product Requested:</b> {prod} (Qty: {row.get('qty', 1)}) &nbsp;|&nbsp; 👔 <b>Assigned SAM:</b> {row.get('assigned_salesperson', 'N/A')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("🎉 All inbound leads have been processed.")

    st.markdown("---")
    st.markdown("##### 📄 Master Data Sheet Exporter")
    if "show_qs_excel" not in st.session_state:
        st.session_state["show_qs_excel"] = False

    if st.button("📋 Display Custom Excel Export Tool"):
        st.session_state["show_qs_excel"] = not st.session_state["show_qs_excel"]

    if st.session_state["show_qs_excel"]:
        if df_quotes.empty:
            st.info("No quotation records found.")
        else:
            all_cols = list(df_quotes.columns)
            selected_cols = st.multiselect("Select Columns to Include in Export:", all_cols, default=all_cols)
            filtered_quotes = df_quotes[selected_cols] if selected_cols else df_quotes
            st.dataframe(filtered_quotes, width="stretch", hide_index=True)


def render_qs_generator_and_claim(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📄 Quotation Generator & Ticket Claiming</h2>", unsafe_allow_html=True)
    qs_id = current_user.get("employee_id", "EMP-102")
    qs_name = current_user.get("name") or "Quotation Specialist"

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")

    if "active_claimed_lead_id" not in st.session_state:
        st.session_state["active_claimed_lead_id"] = None

    unassigned = df_leads[df_leads["claimed_qs_id"] == "Unassigned"] if not df_leads.empty else pd.DataFrame()

    if st.session_state["active_claimed_lead_id"] is None:
        st.markdown("##### 🔔 Available Unassigned Lead Tickets")
        if not unassigned.empty:
            for idx, row in unassigned.iterrows():
                cid = row.get("client_id")
                cname = row.get("client_name")
                comp = row.get("company_name")
                prod = row.get("product")
                lead_id = row.get("lead_id")

                st.markdown(f"""
                <div class='saas-card'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <span style='font-weight:800; color:#184B9C; font-size:16px;'>👤 {cname} | {comp} ({cid})</span>
                        <span style='background:rgba(24, 75, 156, 0.1); color:#184B9C; padding:4px 12px; border-radius:20px; font-weight:700;'>Unassigned Ticket</span>
                    </div>
                    <div style='margin-top:6px; color:#475569; font-size:13.5px;'>
                        📦 <b>Product:</b> {prod} (Qty: {row.get('qty', 1)})
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"🔒 Claim & Accept Ticket {cid}", key=f"claim_{lead_id}"):
                    db_adapter.update_row("leads_master", "lead_id", str(lead_id), {"claimed_qs_id": qs_id, "quotation_status": "Under Process"})
                    st.session_state["active_claimed_lead_id"] = lead_id
                    st.toast(f"✅ Ticket {cid} accepted! Quotation Form loaded below.", icon="🎉")
                    st.rerun()
        else:
            st.info("🎉 No pending unassigned leads in queue.")

    if st.session_state["active_claimed_lead_id"] is not None:
        active_id = st.session_state["active_claimed_lead_id"]
        lead_match = df_leads[df_leads["lead_id"] == active_id]

        if not lead_match.empty:
            lead_row = lead_match.iloc[0]
            st.markdown("---")
            st.markdown(f"### 📝 Quotation Entry Form for Accepted Lead: `{lead_row.get('client_id')}`")
            _render_quotation_form_body(db_adapter, lead_row, df_quotes, qs_id, qs_name, from_claim_tab=True)


def render_qs_detailed_form_entry(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📝 Detailed Quotation Form Entry</h2>", unsafe_allow_html=True)
    qs_id = current_user.get("employee_id", "EMP-102")
    qs_name = current_user.get("name") or "Quotation Specialist"

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")

    if df_leads.empty:
        st.info("No lead records available in system database.")
        return

    df_leads["lookup_label"] = df_leads["client_id"].astype(str) + " | " + df_leads["client_name"].astype(str) + " (" + df_leads["company_name"].fillna("N/A").astype(str) + ")"
    lookup_map = dict(zip(df_leads["lookup_label"], df_leads["lead_id"]))

    selected_label = st.selectbox("🔍 Select Client (Search by Client ID, Bid ID, Name, or Company):", list(lookup_map.keys()))
    selected_lead_id = lookup_map[selected_label]

    lead_row = df_leads[df_leads["lead_id"] == selected_lead_id].iloc[0]
    _render_quotation_form_body(db_adapter, lead_row, df_quotes, qs_id, qs_name, from_claim_tab=False)


def _render_quotation_form_body(db_adapter, lead_row, df_quotes, qs_id, qs_name, from_claim_tab=False):
    now_dt = get_current_ist_time()
    cid = str(lead_row.get("client_id", ""))
    current_month_str = now_dt.strftime("%B")

    st.markdown("###### 🔄 Automatically Fetched Details from Lead Sheet")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("Client ID / Bid ID", value=cid, disabled=True)
        st.text_input("Date Stamp", value=str(lead_row.get("ingestion_date", "")), disabled=True)
        st.text_input("Client Name", value=str(lead_row.get("client_name", "")), disabled=True)
        st.text_input("Company Name", value=str(lead_row.get("company_name", "")), disabled=True)
    with c2:
        st.text_input("Customer Contact Number", value=str(lead_row.get("phone_number", "")), disabled=True)
        st.text_input("Product", value=str(lead_row.get("product", "")), disabled=True)
        st.number_input("Quantity", value=int(lead_row.get("qty", 1)), disabled=True)
        st.text_input("City", value=str(lead_row.get("city", "")), disabled=True)
    with c3:
        st.text_input("Source", value=str(lead_row.get("source", "")), disabled=True)
        st.text_input("Assigned Salesperson", value=str(lead_row.get("assigned_salesperson", "")), disabled=True)

    st.markdown("---")
    st.markdown("###### ✍️ Manual & Operational Quotation Inputs")

    revised_options = [
        "Choose...",
        "No",
        "Yes - R1",
        "Yes - R2",
        "Yes - R3",
        "Yes - R4",
        "Yes - R5",
        "Yes - R6",
        "Yes - R7"
    ]

    with st.form(f"quotation_entry_form_{lead_row.get('lead_id')}"):
        m1, m2, m3 = st.columns(3)
        with m1:
            q_num = st.text_input("Quotation Number *", value=f"SSAPL/2026-27/{len(df_quotes)+841}")
            q_amount = st.number_input("Qut. Amount (INR) *", min_value=0.0, value=50000.0)
            revised = st.selectbox("Revised *", revised_options, index=0)
            q_status = st.selectbox("Quotation Status *", ["Choose...", "Approved", "Under Review", "Rejected"], index=0)
        with m2:
            follow_req = st.selectbox("Follow Up Required *", ["Choose...", "Yes", "No"], index=0)
            app_by = st.selectbox("Qut. Status Approved By *", ["Choose...", "Jitendra Sir", "Jeevan Sharma", "Sidharth Jain", "Deepak Sethiya"], index=0)
            follow_status = st.selectbox("Follow Up Status *", ["Choose...", "Under Discussion", "Won", "Lost", "CallBack"], index=0)
            drive_link = st.text_input("Link (Folder Link)", value="https://drive.google.com")
        with m3:
            q_shared_by = st.selectbox("Quotation Shared By *", ["Choose..."] + TEAM_MEMBERS, index=0)
            approved_date = st.date_input("Approved Date", value=now_dt.date())
            comp_name_1 = st.text_input("Company Name-1", value=str(lead_row.get("company_name", "")))
            approved_month = st.text_input("Approved Month *", value=current_month_str)

        if follow_req == "Yes":
            st.markdown("###### ⏰ Schedule Next Follow-up Call Reminder")
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                next_f_date = st.date_input("Next Follow-up Date *", value=now_dt.date() + datetime.timedelta(days=3))
            with f_col2:
                next_f_time = st.time_input("Next Follow-up Time *", value=datetime.time(12, 0))

        submit_q_btn = st.form_submit_button("💾 Save & Dispatch Quotation")

        if submit_q_btn:
            if "Choose..." in [revised, q_status, follow_req, app_by, follow_status, q_shared_by]:
                st.error("Please select valid options for all mandatory dropdown fields starting with 'Choose...'.")
            else:
                q_record = {
                    "quotation_id": f"QUO-{len(df_quotes)+1:04d}",
                    "lead_id": int(lead_row.get("lead_id")),
                    "client_id": cid,
                    "quotation_number": q_num,
                    "revised": revised,
                    "qut_amount": q_amount,
                    "quotation_status": q_status,
                    "follow_up_required": follow_req,
                    "claimed_qs_id": qs_id,
                    "approved_by_id": "EMP-106",
                    "shared_by_id": qs_id,
                    "folder_link": drive_link,
                    "company_name_1": comp_name_1,
                    "approved_date": str(approved_date),
                    "approved_month": approved_month
                }
                db_adapter.insert_row("quotations_master", q_record)
                db_adapter.update_row("leads_master", "lead_id", str(lead_row.get("lead_id")), {"quotation_status": "Sent", "claimed_qs_id": qs_id})

                if follow_req == "Yes":
                    sched_ts = f"{next_f_date} {next_f_time}"
                    log_entry = {
                        "lead_id": int(lead_row.get("lead_id")),
                        "employee_id": qs_name,
                        "followup_sequence_no": 1,
                        "followup_status": follow_status,
                        "scheduled_call_time": sched_ts,
                        "notes": "Initial quotation dispatched. Follow-up scheduled."
                    }
                    db_adapter.insert_row("followup_logs", log_entry)

                if from_claim_tab:
                    st.session_state["active_claimed_lead_id"] = None

                st.toast(f"🎉 Quotation {q_num} dispatched successfully!", icon="✅")
                st.rerun()


def render_qs_followup_workday(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>⚡ Follow-up Queue & Workday</h2>", unsafe_allow_html=True)
    qs_name = current_user.get("name") or "Quotation Specialist"
    now_ist = get_current_ist_time()

    df_leads = db_adapter.fetch_all("leads_master")
    df_logs = db_adapter.fetch_all("followup_logs")

    if df_leads.empty:
        st.info("No active follow-ups required.")
        return

    active_queue = df_leads[~df_leads["final_status"].astype(str).str.lower().isin(["done", "won", "cancled", "canceled", "lost"])]

    if active_queue.empty:
        st.info("🎉 All follow-up tasks completed! No active leads remaining.")
        return

    from components.follow_up_cards import render_time_slot_workday_queue
    render_time_slot_workday_queue(db_adapter, active_queue, df_logs, qs_name, now_ist)