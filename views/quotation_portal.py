import streamlit as st
import pandas as pd
from datetime import datetime
from config.settings import IST
from utils.SLA_calculator import evaluate_sla
from components.kpi_cards import render_kpi_cards
from components.data_tables import render_interactive_table

def render_quotation_portal(db, current_user: dict):
    st.title("📝 Quotation Desk Portal")
    st.caption("Team: Pooja, Anjali, Dolly | SLA Cutoff: 17:30 IST")

    df_quotes = db.fetch_all("quotation_sheet")
    total_quotes = len(df_quotes) if not df_quotes.empty else 0
    overnight_count = (
        len(df_quotes[df_quotes["is_after_cutoff"] == True]) if total_quotes > 0 else 0
    )

    kpis = [
        {"label": "Total Quotes Drafted", "value": total_quotes},
        {"label": "Overnight SLA Queue", "value": overnight_count},
    ]
    render_kpi_cards(kpis)
    st.divider()

    st.subheader("⚡ Quotation Dispatch Station")
    df_leads = db.fetch_all("leads_data")
    pending_leads = (
        df_leads[df_leads["quotation_status"] == "Pending"]
        if not df_leads.empty
        else pd.DataFrame()
    )

    if pending_leads.empty:
        st.info("No pending quotation requests.")
    else:
        selected_client_id = st.selectbox(
            "Select Client ID to Quote", pending_leads["client_id"].tolist()
        )
        client_row = pending_leads[
            pending_leads["client_id"] == selected_client_id
        ].iloc[0]

        st.json(
            {
                "Client Name": client_row.get("client_name"),
                "Product": client_row.get("product"),
                "Qty": client_row.get("qty"),
                "Assigned SAM": client_row.get("assigned_salesperson"),
            }
        )

        with st.form("dispatch_quote_form"):
            c1, c2 = st.columns(2)
            with c1:
                q_num = st.text_input(
                    "Quotation Number", value=f"SSAPL/2026-27/{total_quotes + 841}"
                )
                q_amount = st.number_input(
                    "Quotation Amount (INR)", min_value=0.0, step=1000.0
                )
            with c2:
                qs_assigned = st.selectbox("Assigned QS", ["Pooja", "Anjali", "Dolly"])
                rev_count = st.number_input(
                    "Revision Number (0 = New)", min_value=0, value=0
                )

            if st.form_submit_button("Dispatch Quotation"):
                now = datetime.now(IST)
                is_cutoff, target_date, queue_label = evaluate_sla(now)

                quote_record = {
                    "quotation_id": f"QUO-{total_quotes + 1:04d}",
                    "client_id": selected_client_id,
                    "quotation_number": q_num,
                    "quotation_amount": q_amount,
                    "revised_count": rev_count,
                    "quotation_status": "Approved",
                    "follow_up_required": True,
                    "assigned_qs_id": qs_assigned,
                    "quotation_shared_by": client_row.get("assigned_salesperson"),
                    "company_name_1": client_row.get("company_name"),
                    "request_timestamp": client_row.get("date_stamp", now.strftime("%Y-%m-%d %H:%M:%S")),
                    "completion_timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_after_cutoff": is_cutoff,
                    "target_completion_date": str(target_date),
                }

                db.insert_row("quotation_sheet", quote_record)
                db.update_row(
                    "leads_data",
                    "client_id",
                    selected_client_id,
                    {"quotation_status": "Sent", "quotation_sent_by": qs_assigned},
                )
                st.success(f"Quotation {q_num} dispatched successfully!")
                st.rerun()

    st.divider()
    st.subheader("📋 Quotation Registry")
    render_interactive_table(df_quotes, key="qs_registry_table")