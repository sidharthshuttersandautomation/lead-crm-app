import streamlit as st
import datetime
from components.kpi_cards import render_kpi_card
from components.data_tables import render_interactive_table
from utils.SLA_calculator import evaluate_sla_cutoff, calculate_turnaround_time_mins

def render_quotation_portal(db_adapter, user):
    st.title(" Quotation Desk Portal")
    
    q_df = db_adapter.fetch_table("quotation_sheet")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Quotes Drafted", str(len(q_df)))
    with col2:
        approved = len(q_df[q_df["quotation_status"] == "Approved"]) if not q_df.empty else 0
        render_kpi_card("Approved Value", f"₹{approved * 150000:,}", color="#10B981")
    with col3:
        pending = len(q_df[q_df["quotation_status"] == "Pending"]) if not q_df.empty else 0
        render_kpi_card("Pending Requests", str(pending), color="#EF4444")
    with col4:
        render_kpi_card("SLA Compliance", "94.2%", color="#3B82F6")

    tab1, tab2, tab3 = st.tabs(["New Requests (Today's SLA)", "Overnight Queue (> 5:30 PM)", "Revisions Pending"])
    
    with tab1:
        st.subheader("Active Work Queue")
        today_queue = q_df[q_df["is_after_cutoff"] == False] if not q_df.empty else q_df
        render_interactive_table(today_queue, "qs_today_queue")
        
        with st.expander("Process & Dispatch Quotation"):
            with st.form("dispatch_quote_form"):
                q_id = st.text_input("Quotation ID (e.g., Q-001)")
                q_num = st.text_input("Generated Quotation Number", value="SSAPL/2026-27/842")
                amount = st.number_input("Quotation Amount (INR)", min_value=0.0, step=1000.0)
                status = st.selectbox("Quotation Status", ["Sent", "Under Discussion", "Approved"])
                
                if st.form_submit_button("Mark as Sent & Update SLA"):
                    comp_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    db_adapter.update_row("quotation_sheet", "quotation_id", q_id, {
                        "quotation_number": q_num,
                        "quotation_amount": amount,
                        "quotation_status": status,
                        "completion_timestamp": comp_time,
                        "assigned_qs_id": user["full_name"]
                    })
                    st.success("Quotation status updated successfully!")
                    st.rerun()

    with tab2:
        st.subheader("Shifted to Next-Day Task Queue")
        overnight = q_df[q_df["is_after_cutoff"] == True] if not q_df.empty else q_df
        render_interactive_table(overnight, "qs_overnight_queue")

    with tab3:
        st.subheader("Revision Handling Queue")
        revisions = q_df[q_df["revised_count"] > 0] if not q_df.empty else q_df
        render_interactive_table(revisions, "qs_revisions_queue")