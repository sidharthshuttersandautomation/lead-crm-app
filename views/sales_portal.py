import streamlit as st
import pandas as pd
from datetime import datetime
from config.settings import IST, CANCEL_CATEGORIES
from components.kpi_cards import render_kpi_cards
from components.data_tables import render_interactive_table

def render_sales_portal(db, current_user: dict):
    st.title("💼 Sales Account Manager (SAM) Portal")
    sam_name = current_user.get("name", "Jeevan Sharma")

    df_leads = db.fetch_all("leads_data")
    df_quotes = db.fetch_all("quotation_sheet")
    df_follow = db.fetch_all("followup_tracker")

    my_leads = (
        df_leads[df_leads["assigned_salesperson"] == sam_name]
        if not df_leads.empty
        else pd.DataFrame()
    )

    total_my_leads = len(my_leads)
    won_leads = (
        len(my_leads[my_leads["final_status"] == "Done"]) if total_my_leads > 0 else 0
    )

    kpis = [
        {"label": "My Assigned Clients", "value": total_my_leads},
        {"label": "Deals Won", "value": won_leads},
    ]
    render_kpi_cards(kpis)
    st.divider()

    st.subheader("📌 Client Follow-Up Workstation")
    if my_leads.empty:
        st.info("No assigned clients found.")
        return

    selected_client_id = st.selectbox("Select Client", my_leads["client_id"].tolist())
    col1, col2 = st.columns(2)

    with col1:
        st.write("### 📞 Log Follow-Up Call")
        with st.form("log_followup_form"):
            call_dt = st.datetime_input("Scheduled Call", value=datetime.now(IST))
            f_notes = st.text_area("Notes")
            f_status = st.selectbox(
                "Outcome", ["Under Discussion", "Won", "Lost", "Rescheduled"]
            )
            cancel_cat = st.selectbox("Cancel Reason (If Lost)", CANCEL_CATEGORIES)

            if st.form_submit_button("Save Follow-Up"):
                record = {
                    "followup_id": f"FOL-{len(df_follow) + 1:04d}",
                    "client_id": selected_client_id,
                    "quotation_id": "",
                    "quotation_follow_up_by": sam_name,
                    "followup_1": f_notes,
                    "total_followups": 1,
                    "followup_status": f_status,
                    "cancel_category": cancel_cat if f_status == "Lost" else "",
                    "won_by_followup": True if f_status == "Won" else False,
                    "scheduled_call_time": str(call_dt),
                    "notes": f_notes,
                    "approved_date": datetime.now(IST).strftime("%Y-%m-%d") if f_status == "Won" else "",
                    "month": datetime.now(IST).strftime("%B"),
                }
                db.insert_row("followup_tracker", record)

                if f_status in ["Won", "Lost"]:
                    db.update_row(
                        "leads_data",
                        "client_id",
                        selected_client_id,
                        {"final_status": "Done" if f_status == "Won" else "Canceled"},
                    )
                st.success("Follow-up call saved!")
                st.rerun()

    with col2:
        st.write("### 🔄 Request Revision")
        with st.form("request_revision_form"):
            rev_notes = st.text_area("Revision Details")
            if st.form_submit_button("Submit Revision"):
                if not df_quotes.empty and selected_client_id in df_quotes["client_id"].values:
                    q_row = df_quotes[df_quotes["client_id"] == selected_client_id].iloc[0]
                    cur_rev = int(q_row.get("revised_count", 0))
                    db.update_row(
                        "quotation_sheet",
                        "client_id",
                        selected_client_id,
                        {
                            "revised_count": cur_rev + 1,
                            "quotation_status": "Pending",
                            "request_timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
                        },
                    )
                st.success("Revision requested!")
                st.rerun()

    st.divider()
    st.subheader("📑 My Clients Registry")
    render_interactive_table(my_leads, key="sam_leads_table")