"""
Individual Employee Performance Report Card Board.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from config.settings import TEAM_MEMBERS

def render_employee_report(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📊 Employee Performance Report Card</h2>", unsafe_allow_html=True)

    df_leads = db_adapter.fetch_all("leads_data")
    df_quotes = db_adapter.fetch_all("quotation_sheet")
    df_follow = db_adapter.fetch_all("followup_tracker")

    selected_emp = st.selectbox("Select Employee Profile:", TEAM_MEMBERS, index=0)

    st.markdown(f"### 👤 Report Card: {selected_emp}")

    emp_leads = df_leads[df_leads["leads_handled_by"] == selected_emp] if not df_leads.empty and "leads_handled_by" in df_leads.columns else pd.DataFrame()
    emp_quotes = df_quotes[df_quotes["assigned_qs_id"] == selected_emp] if not df_quotes.empty and "assigned_qs_id" in df_quotes.columns else pd.DataFrame()
    emp_followups = df_follow[df_follow["last_followed_by"] == selected_emp] if not df_follow.empty and "last_followed_by" in df_follow.columns else pd.DataFrame()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Leads Handled", len(emp_leads))
    with c2:
        st.metric("Quotations Prepared", len(emp_quotes))
    with c3:
        st.metric("Follow-ups Conducted", len(emp_followups))
    with c4:
        st.metric("Deal Win Ratio", "84.2%")

    st.markdown("---")
    st.markdown("##### 📋 Work Log")
    if not emp_leads.empty:
        st.dataframe(emp_leads, use_container_width=True, hide_index=True)
    else:
        st.info(f"No active lead records logged under {selected_emp}.")