import streamlit as st
import datetime
from components.kpi_cards import render_kpi_card
from components.data_tables import render_interactive_table
from config.settings import LEAD_SOURCES, TYPE_OF_CLIENT

def render_lead_portal(db_adapter, user):
    st.title(" Lead Generation Portal (Albert)")
    
    leads_df = db_adapter.fetch_table("leads_data")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpi_card("Total Ingested Leads", str(len(leads_df)))
    with c2:
        conv = len(leads_df[leads_df["final_status"] == "Done"]) if not leads_df.empty else 0
        render_kpi_card("Converted Leads", str(conv), color="#10B981")
    with c3:
        top_source = leads_df["source"].mode()[0] if not leads_df.empty and "source" in leads_df else "N/A"
        render_kpi_card("Top Inbound Source", str(top_source), color="#F59E0B")

    tab1, tab2 = st.tabs(["New Lead Capture", "Lead Registry"])
    
    with tab1:
        with st.form("new_lead_form", clear_on_submit=True):
            st.subheader("Register New Inbound Lead")
            col_a, col_b = st.columns(2)
            with col_a:
                client_name = st.text_input("Client Name*", placeholder="e.g. Rajesh Kumar")
                company_name = st.text_input("Company Name", placeholder="e.g. Kumar Builders")
                number = st.text_input("Contact Number*")
                email = st.text_input("Email Address")
                product = st.text_input("Product Required*", placeholder="e.g. Rolling Shutter")
            with col_b:
                qty = st.number_input("Quantity", min_value=1, value=1)
                city = st.text_input("City", value="Jaipur")
                source = st.selectbox("Lead Source*", LEAD_SOURCES)
                client_type = st.selectbox("Type of Client", TYPE_OF_CLIENT)
                assigned_sp = st.text_input("Assign Salesperson", value="Jeevan")

            submitted = st.form_submit_button("Submit Lead to Desk")
            if submitted:
                if not client_name or not number:
                    st.error("Please fill in mandatory fields (*)")
                else:
                    new_id = f"BID-Oct-26-00{len(leads_df)+1}"
                    now = datetime.datetime.now()
                    record = {
                        "client_id": new_id,
                        "date_stamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "client_name": client_name,
                        "company_name": company_name,
                        "number": number,
                        "email": email,
                        "product": product,
                        "qty": qty,
                        "address": "",
                        "city": city,
                        "state": "Rajasthan",
                        "source": source,
                        "assigned_salesperson": assigned_sp,
                        "type_of_client": client_type,
                        "customer_responded": "Yes",
                        "final_status": "Under Discussion",
                        "quotation_status": "Pending",
                        "leads_handled_by": user["full_name"],
                        "quotation_sent_by": "",
                        "customer_status": "Active",
                        "remarks": "Inbound intake",
                        "month": now.strftime("%B"),
                        "date": str(now.day)
                    }
                    db_adapter.insert_row("leads_data", record)
                    st.success(f"Lead Created Successfully! Assigned Client ID: {new_id}")
                    st.rerun()

    with tab2:
        render_interactive_table(leads_df, "lge_lead_registry")