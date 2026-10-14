"""
views/lead_portal.py - Isolated Add New Lead Intake Workstation.
"""
import datetime
import pandas as pd
import streamlit as st
from config.settings import CLIENT_TYPES, FINAL_STATUS_OPTIONS, SOURCE_OPTIONS, IST
from utils.id_generator import generate_client_id, get_next_sequential_id

def render_lead_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📥 Add New Lead Workstation</h2>", unsafe_allow_html=True)
    df_leads = db_adapter.fetch_all("leads_master")
    df_products = db_adapter.fetch_all("products")
    df_emp = db_adapter.fetch_all("employees")

    next_sr_no = get_next_sequential_id(df_leads)
    today_now = datetime.datetime.now(IST)

    product_list = list(df_products["product_name"].unique()) if not df_products.empty else ["Automatic Rolling Shutters"]
    sam_list = list(df_emp[df_emp["role"] == "SAM"]["full_name"].unique()) if not df_emp.empty else ["Jeevan Sharma"]

    with st.form("add_lead_form_single", clear_on_submit=True):
        st.info(f"🔢 **Dynamic Lead Sr. No:** `{next_sr_no}` | **Timestamp:** `{today_now.strftime('%Y-%m-%d %H:%M:%S')}`")

        c1, c2, c3 = st.columns(3)
        with c1:
            client_type = st.selectbox("Type of client *", CLIENT_TYPES)
            client_name = st.text_input("Client Name *", placeholder="Enter full client name")
            company_name = st.text_input("Company Name", placeholder="Enter firm or company name")
        with c2:
            contact_no = st.text_input("Contact No. *", placeholder="e.g. 9876543210")
            email = st.text_input("Email ID", placeholder="client@company.com")
            product_selected = st.selectbox("Product *", product_list)
        with c3:
            quantity = st.number_input("Quantity", min_value=1, value=1)
            address = st.text_input("Address *", placeholder="Site or office address")
            city = st.text_input("City *", value="Indore")

        c4, c5 = st.columns(2)
        with c4:
            state = st.text_input("State", value="Madhya Pradesh")
            source = st.selectbox("Source *", SOURCE_OPTIONS)
        with c5:
            assigned_sam_name = st.selectbox("Assigned Salesperson (SAM) *", sam_list)
            final_status = st.selectbox("Final Status", FINAL_STATUS_OPTIONS)

        remarks = st.text_area("Initial Requirement Remarks", placeholder="Enter requirement details...")
        submit_btn = st.form_submit_button("💾 Save & Ingest Lead")

        if submit_btn:
            if not client_name or not contact_no or not city:
                st.error("Please fill in mandatory fields: Client Name, Contact No., and City.")
            else:
                generated_client_id = generate_client_id(client_type, today_now.date(), df_leads)
                
                customer_record = {
                    "client_id": generated_client_id,
                    "client_name": client_name,
                    "company_name": company_name,
                    "phone_number": contact_no,
                    "email": email,
                    "address": address,
                    "city": city,
                    "state": state
                }
                db_adapter.insert_row("customers", customer_record)

                pid = 1
                if not df_products.empty:
                    matched = df_products[df_products["product_name"] == product_selected]
                    if not matched.empty:
                        pid = int(matched.iloc[0]["product_id"])

                sam_id = "EMP-105"
                if not df_emp.empty:
                    matched_sam = df_emp[df_emp["full_name"] == assigned_sam_name]
                    if not matched_sam.empty:
                        sam_id = str(matched_sam.iloc[0]["employee_id"])

                lead_record = {
                    "client_id": generated_client_id,
                    "product_id": pid,
                    "quantity": quantity,
                    "source": source,
                    "type_of_client": client_type,
                    "final_status": final_status,
                    "quotation_status": "Not Sent",
                    "customer_status": "Active",
                    "customer_responded": "Yes",
                    "product_status": "Standard",
                    "remarks": remarks,
                    "handled_by_lge_id": current_user.get("employee_id", "EMP-101"),
                    "assigned_sam_id": sam_id,
                    "ingestion_date": today_now.strftime("%Y-%m-%d"),
                    "claimed_qs_id": "Unassigned"
                }
                db_adapter.insert_row("leads_master", lead_record)

                st.toast(f"🎉 Lead Ingested! Generated Client ID: {generated_client_id}", icon="✅")
                st.rerun()