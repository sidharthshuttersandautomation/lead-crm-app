"""
Lead Generation Executive Workstation.
"""
import datetime
import pandas as pd
import streamlit as st

from config.settings import (
    CLIENT_TYPES, FINAL_STATUS_OPTIONS, PRODUCT_NAME_OPTIONS,
    SALESPERSONS_LIST, SOURCE_OPTIONS, TEAM_MEMBERS, REPORTING_TIMEFRAMES, IST
)
from utils.id_generator import generate_client_id, get_next_sequential_id
from components.follow_up_cards import render_follow_up_card

def render_lead_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📥 Lead Generation Workstation</h2>", unsafe_allow_html=True)
    df_leads = db_adapter.fetch_all("leads_data")

    t1, t2, t3 = st.tabs([
        "📈 Performance & Progress Control",
        "📥 Add New Lead",
        "⚡ Follow-up Queue & Workday"
    ])

    # 1. Performance Control
    with t1:
        st.markdown("##### 📈 Monthly Ingestion Analytics & Progress")
        selected_tf = st.selectbox("📅 Reporting Timeframe Filter", REPORTING_TIMEFRAMES, index=2, key="lge_tf")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Ingested Leads", len(df_leads))
        with c2:
            buy_cnt = len(df_leads[df_leads["type_of_client"] == "New Buy"]) if not df_leads.empty and "type_of_client" in df_leads.columns else 0
            st.metric("New Buy Inquiries (BID)", buy_cnt)
        with c3:
            srv_cnt = len(df_leads[df_leads["type_of_client"] == "Service"]) if not df_leads.empty and "type_of_client" in df_leads.columns else 0
            st.metric("Service Inquiries (SID)", srv_cnt)

        st.markdown("---")
        st.dataframe(df_leads, use_container_width=True, hide_index=True)

    # 2. Add New Lead
    with t2:
        st.markdown("##### 📥 Ingest New Client Requirement")
        next_sr_no = get_next_sequential_id(df_leads)
        today_now = datetime.datetime.now(IST)

        with st.form("add_lead_form_lge_master", clear_on_submit=True):
            st.info(f"🔢 **Auto Dynamic Sr. No:** `{next_sr_no}` | **Timestamp:** `{today_now.strftime('%Y-%m-%d %H:%M:%S')}`")

            c1, c2, c3 = st.columns(3)
            with c1:
                client_type = st.selectbox("Type of client *", CLIENT_TYPES)
                client_name = st.text_input("Client Name *", placeholder="Enter full client name")
                company_name = st.text_input("Company Name *", placeholder="Enter firm or company name")
            with c2:
                contact_no = st.text_input("Contact No. *", placeholder="e.g. 9876543210")
                email = st.text_input("Email ID", placeholder="client@company.com")
                product = st.selectbox("Product *", PRODUCT_NAME_OPTIONS)
            with c3:
                quantity = st.number_input("Quantity", min_value=1, value=1)
                address = st.text_input("Address *", placeholder="Site or office address")
                city = st.text_input("City *", value="Indore")

            c4, c5, c6 = st.columns(3)
            with c4:
                state = st.text_input("State", value="Madhya Pradesh")
                source = st.selectbox("Source *", SOURCE_OPTIONS)
                assigned_sp = st.selectbox("Assigned Salesperson *", SALESPERSONS_LIST)
            with c5:
                final_status = st.selectbox("Final Status", FINAL_STATUS_OPTIONS)
                quotation_status = st.selectbox("Quotation Status", ["Pending", "Under Process", "Sent", "Approved"])
                leads_handle_by = st.selectbox("Leads Handled By", TEAM_MEMBERS)
            with c6:
                quotation_sent_by = st.selectbox("Quotation Sent By", TEAM_MEMBERS)
                customer_status = st.selectbox("Customer Status", ["New", "Follow-up Required", "Cold", "Closed"])

            remarks = st.text_area("Initial Remarks", placeholder="Enter requirement details...")
            submit_btn = st.form_submit_button("💾 Save & Ingest Lead")

            if submit_btn:
                if not client_name or not contact_no or not city:
                    st.error("Please fill in mandatory fields: Client Name, Contact No., and City.")
                else:
                    generated_client_id = generate_client_id(client_type, today_now.date(), df_leads)
                    new_lead_data = {
                        "client_id": generated_client_id,
                        "date_stamp": today_now.strftime("%Y-%m-%d %H:%M:%S"),
                        "month": today_now.strftime("%B"),
                        "date": today_now.strftime("%Y-%m-%d"),
                        "client_name": client_name,
                        "company_name": company_name,
                        "number": contact_no,
                        "email": email,
                        "product": product,
                        "qty": quantity,
                        "address": address,
                        "city": city,
                        "state": state,
                        "source": source,
                        "assigned_salesperson": assigned_sp,
                        "type_of_client": client_type,
                        "final_status": final_status,
                        "quotation_status": quotation_status,
                        "leads_handled_by": leads_handle_by,
                        "quotation_sent_by": quotation_sent_by,
                        "customer_status": customer_status,
                        "remarks": remarks,
                        "claimed_by_qs": "Unassigned"
                    }
                    db_adapter.insert_row("leads_data", new_lead_data)

                    follow_entry = {
                        "followup_id": f"FL-{next_sr_no:04d}",
                        "client_id": generated_client_id,
                        "quotation_follow_up_by": assigned_sp,
                        "total_followups": 0,
                        "followup_status": "Pending Quotation",
                        "cancel_category": "N/A",
                        "scheduled_call_time": str(today_now + datetime.timedelta(days=3)),
                        "notes": f"Lead Ingested on {today_now.strftime('%Y-%m-%d %H:%M')}",
                        "month": today_now.strftime("%B"),
                        "last_followed_by": current_user.get("name", "LGE")
                    }
                    db_adapter.insert_row("followup_tracker", follow_entry)

                    st.toast(f"🎉 Lead Created Successfully! Generated Client ID: {generated_client_id}", icon="✅")
                    st.rerun()

    # 3. Follow-up Workstation
    with t3:
        st.markdown("##### ⚡ Dynamic Follow-up Queue")
        df_follow = db_adapter.fetch_all("followup_tracker")
        if not df_follow.empty:
            for idx, row in df_follow.iterrows():
                cid = str(row.get("client_id", "N/A"))
                lead_match = df_leads[df_leads["client_id"] == cid] if not df_leads.empty else pd.DataFrame()
                c_name = lead_match.iloc[0].get("client_name", "Client") if not lead_match.empty else "Client"
                addr = lead_match.iloc[0].get("address", "N/A") if not lead_match.empty else "N/A"
                cty = lead_match.iloc[0].get("city", "N/A") if not lead_match.empty else "N/A"
                prod = lead_match.iloc[0].get("product", "Automation") if not lead_match.empty else "Automation"

                render_follow_up_card(
                    db_adapter=db_adapter,
                    client_id=cid,
                    client_name=c_name,
                    address=addr,
                    city=cty,
                    product=prod,
                    last_price=0.0,
                    followups_count=int(row.get("total_followups", 0)),
                    remarks_history=[str(row.get("notes", "Initial Lead Ingested"))],
                    current_user_name=current_user.get("name", "LGE"),
                    key=f"lge_card_{idx}"
                )