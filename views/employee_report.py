"""
Admin-Only Employee Report Card Board.
"""
import streamlit as st
import pandas as pd
from config.settings import TEAM_MEMBERS

def render_employee_report(db_adapter, current_user):
    user_role = str(current_user.get("role", "")).upper()
    
    if user_role not in ["ADMIN", "ADMINISTRATOR"]:
        st.error("⛔ Security Restriction: Employee Performance Report Cards are strictly restricted to CRM Administrators.")
        st.stop()

    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📊 Individual Employee Report Card (Admin View)</h2>", unsafe_allow_html=True)

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_follow = db_adapter.fetch_all("followup_logs")

    selected_emp = st.selectbox("Select Employee Profile:", TEAM_MEMBERS, index=0)

    st.markdown(f"### 👤 Report Card: {selected_emp}")

    emp_leads = df_leads[df_leads["leads_handled_by"] == selected_emp] if not df_leads.empty else pd.DataFrame()
    emp_quotes = df_quotes[df_quotes["quotation_shared_by"] == selected_emp] if not df_quotes.empty else pd.DataFrame()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Leads Ingested / Handled", len(emp_leads))
    with c2:
        st.metric("Quotations Dispatched", len(emp_quotes))
    with c3:
        st.metric("Total System Logs", len(df_follow))
    with c4:
        st.metric("Target Conversion Rate", "82.4%")

    st.markdown("---")
    st.markdown("##### 📋 Staff Work Log History")
    if not emp_leads.empty:
        st.dataframe(emp_leads, use_container_width=True, hide_index=True)
    else:
        st.info(f"No active lead records logged under {selected_emp}.")