import streamlit as st
import pandas as pd
from components.kpi_cards import render_kpi_cards
from components.data_tables import render_interactive_table

def render_process_portal(db, current_user: dict):
    st.title("⚙️ Order Fulfillment & Production Tracker")
    st.caption("Post-Sale Order Management Desk")

    df_orders = db.fetch_all("process_order")
    total_orders = len(df_orders) if not df_orders.empty else 0

    kpis = [{"label": "Total Active Orders", "value": total_orders}]
    render_kpi_cards(kpis)
    st.divider()

    df_leads = db.fetch_all("leads_data")
    won_leads = (
        df_leads[df_leads["final_status"] == "Done"]
        if not df_leads.empty
        else pd.DataFrame()
    )

    if won_leads.empty:
        st.info("No 'Done/Won' deals available for fulfillment.")
    else:
        with st.form("create_process_order_form"):
            selected_client = st.selectbox("Select Won Deal", won_leads["client_id"].tolist())
            client_row = won_leads[won_leads["client_id"] == selected_client].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                pi_amount = st.number_input("PI Amount (INR)", min_value=0.0)
                pay_status = st.selectbox("Payment Status", ["Received", "Pending", "Partial"])
                prod_status = st.selectbox("Production Status", ["Not Started", "In Production", "Completed"])
            with col2:
                meas_status = st.selectbox("Measurement", ["Pending", "Completed"])
                disp_status = st.selectbox("Dispatch Status", ["Pending", "Ready", "Dispatched"])

            prod_remarks = st.text_area("Production Remarks")

            if st.form_submit_button("Save Order Tracker"):
                order_record = {
                    "order_id": f"ORD-{total_orders + 1:04d}",
                    "client_id": selected_client,
                    "client_name": client_row.get("client_name"),
                    "company_name": client_row.get("company_name"),
                    "sales_person": client_row.get("assigned_salesperson"),
                    "quotation_number": "",
                    "product": client_row.get("product"),
                    "qty": client_row.get("qty"),
                    "qut_amount": pi_amount,
                    "start_date": client_row.get("date"),
                    "purchase_order": "PO-ATTACHED",
                    "performa_invoice_amount": pi_amount,
                    "payment_status": pay_status,
                    "measurement_status": meas_status,
                    "drawing_status": "Approved",
                    "production_status": prod_status,
                    "production_remarks": prod_remarks,
                    "before_dispatch_payment": pay_status,
                    "dispatch_status": disp_status,
                    "document_submission": "Done",
                    "packing_list": "Ready",
                    "material_receiving": "Pending",
                    "invoice": "Generated",
                    "final_remarks": prod_remarks,
                }
                db.insert_row("process_order", order_record)
                st.success("Production Order recorded!")
                st.rerun()

    st.divider()
    st.subheader("🏭 Master Production Table")
    render_interactive_table(df_orders, key="process_order_table")