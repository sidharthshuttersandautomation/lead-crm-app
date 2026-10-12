import streamlit as st
import datetime
from components.kpi_cards import render_kpi_card
from components.data_tables import render_interactive_table
from utils.SLA_calculator import evaluate_sla_cutoff

def render_sales_portal(db_adapter, user):
    st.title(" Sales Management Portal")
    
    f_df = db_adapter.fetch_table("followup_tracker")
    q_df = db_adapter.fetch_table("quotation_sheet")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Quotes Requested", str(len(q_df)))
    with c2:
        render_kpi_card("Won Business (INR)", "₹12,45,000", color="#10B981")
    with c3:
        render_kpi_card("Lost Clients", "3", color="#EF4444")
    with c4:
        render_kpi_card("Follow-up Rate", "88%", color="#3B82F6")

    tab1, tab2, tab3 = st.tabs(["Request New Quote / Revision", "Follow-Up Workstation", "My Assigned Clients"])
    
    with tab1:
        st.subheader("Submit Quote Request to Quotation Desk")
        with st.form("request_quote_sales"):
            client_id = st.text_input("Client ID", value="BID-Oct-26-001")
            is_revision = st.checkbox("Is this a Revision Request?")
            rev_count = st.number_input("Revision Number", min_value=1, value=1) if is_revision else 0
            notes = st.text_area("Quotation Specifications / Notes")
            
            if st.form_submit_button("Submit Request"):
                now = datetime.datetime.now()
                is_after, target_date = evaluate_sla_cutoff(now)
                new_q = {
                    "quotation_id": f"Q-00{len(q_df)+1}",
                    "client_id": client_id,
                    "quotation_number": "PENDING",
                    "quotation_amount": 0,
                    "revised_count": rev_count,
                    "quotation_status": "Pending",
                    "follow_up_required": True,
                    "assigned_qs_id": "Unassigned",
                    "quotation_shared_by": user["full_name"],
                    "company_name_1": "",
                    "request_timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "completion_timestamp": "",
                    "is_after_cutoff": is_after,
                    "target_completion_date": target_date
                }
                db_adapter.insert_row("quotation_sheet", new_q)
                st.success(f"Quotation Request Queued! Target Completion Date: {target_date}")
                st.rerun()

    with tab2:
        st.subheader("Follow-Up Logging Window")
        with st.form("log_followup_form"):
            cid = st.text_input("Client ID", value="BID-Oct-26-001")
            fu_status = st.selectbox("Follow-up Outcome", ["Under Discussion", "Won", "Lost", "Rescheduled"])
            next_call = st.text_input("Schedule Next Call (e.g. 2026-10-12 17:00:00)")
            remarks = st.text_area("Follow-up Summary Notes")
            
            if st.form_submit_button("Log Follow-Up Step"):
                new_fu = {
                    "followup_id": f"F-00{len(f_df)+1}",
                    "client_id": cid,
                    "quotation_id": "Q-001",
                    "quotation_follow_up_by": user["full_name"],
                    "followup_1": remarks,
                    "followup_2": "", "followup_3": "", "followup_4": "", "followup_5": "",
                    "total_followups": 1,
                    "followup_status": fu_status,
                    "cancel_category": "",
                    "won_by_followup": True if fu_status == "Won" else False,
                    "scheduled_call_time": next_call,
                    "notes": remarks,
                    "approved_date": "",
                    "month": "October"
                }
                db_adapter.insert_row("followup_tracker", new_fu)
                st.success("Follow-up logged successfully.")
                st.rerun()

    with tab3:
        render_interactive_table(f_df, "sales_followup_table")