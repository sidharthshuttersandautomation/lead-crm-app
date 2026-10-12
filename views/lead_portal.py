import streamlit as st
from datetime import datetime
from config.settings import LEAD_SOURCES, PRODUCTS, IST
from components.kpi_cards import render_kpi_cards
from components.data_tables import render_interactive_table

def render_lead_portal(db, current_user: dict):
    st.title("📥 Lead Generation Executive (LGE) Portal")
    st.caption("Operator: Albert Singh / Lead Ingestion Desk")

    df_leads = db.fetch_all("leads_data")
    total_leads = len(df_leads) if not df_leads.empty else 0
    done_leads = (
        len(df_leads[df_leads["final_status"] == "Done"]) if total_leads > 0 else 0
    )

    kpis = [
        {"label": "Total Leads Ingested", "value": total_leads},
        {"label": "Leads Converted (Done)", "value": done_leads},
        {
            "label": "Conversion Rate",
            "value": f"{round((done_leads / total_leads) * 100, 1)}%" if total_leads > 0 else "0%",
        },
    ]
    render_kpi_cards(kpis)
    st.divider()

    st.subheader("➕ Capture New Lead")
    with st.form("new_lead_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            client_name = st.text_input("Client Name *")
            company_name = st.text_input("Company Name")
            number = st.text_input("Contact Number *")
            email = st.text_input("Email ID")

        with col2:
            product = st.selectbox("Product *", PRODUCTS)
            qty = st.number_input("Quantity", min_value=1, value=1)
            source = st.selectbox("Lead Source *", LEAD_SOURCES)
            assigned_salesperson = st.selectbox(
                "Assigned SAM *", ["Jeevan Sharma", "Jitendra Sir", "Deepak Sir"]
            )

        with col3:
            address = st.text_area("Address")
            city = st.text_input("City")
            state = st.text_input("State")
            remarks = st.text_input("Initial Remarks")

        submitted = st.form_submit_button("Submit Lead")

        if submitted:
            if not client_name or not number:
                st.error("Please fill in mandatory fields (*).")
            else:
                now = datetime.now(IST)
                client_id = f"BID-{now.strftime('%b-%y')}-{total_leads + 1:03d}"

                record = {
                    "client_id": client_id,
                    "date_stamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "client_name": client_name,
                    "company_name": company_name,
                    "number": number,
                    "email": email,
                    "product": product,
                    "qty": qty,
                    "address": address,
                    "city": city,
                    "state": state,
                    "source": source,
                    "assigned_salesperson": assigned_salesperson,
                    "type_of_client": "New",
                    "customer_responded": "Yes",
                    "final_status": "Under Discussion",
                    "quotation_status": "Pending",
                    "leads_handled_by": current_user.get("name", "Albert Singh"),
                    "quotation_sent_by": "",
                    "customer_status": "Active",
                    "remarks": remarks,
                    "month": now.strftime("%B"),
                    "date": now.strftime("%Y-%m-%d"),
                }

                db.insert_row("leads_data", record)
                st.success(f"Lead generated! Client ID: **{client_id}**")
                st.rerun()

    st.divider()
    st.subheader("📋 Ingested Leads Repository")
    render_interactive_table(df_leads, key="lge_leads_table")