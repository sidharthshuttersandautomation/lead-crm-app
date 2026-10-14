"""
views/employee_progress.py - My Progress Report Workstation for Employees.
"""
import datetime
import pandas as pd
import streamlit as st

def render_my_progress_report(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📊 My Progress Report</h2>", unsafe_allow_html=True)
    
    emp_id = current_user.get("employee_id", "")
    emp_name = current_user.get("name", "Employee")
    emp_role = current_user.get("role", "QS")

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_logs = db_adapter.fetch_all("followup_logs")

    # Filter data for current user
    my_quotes = df_quotes[df_quotes["shared_by_id"] == emp_id] if not df_quotes.empty and "shared_by_id" in df_quotes.columns else pd.DataFrame()
    if my_quotes.empty and not df_quotes.empty and "claimed_qs_id" in df_quotes.columns:
        my_quotes = df_quotes[df_quotes["claimed_qs_id"] == emp_id]

    my_logs = df_logs[df_logs["employee_id"] == emp_name] if not df_logs.empty and "employee_id" in df_logs.columns else pd.DataFrame()

    st.markdown("##### 📈 Key Performance Indicators")
    c1, c2, c3, c4 = st.columns(4)
    
    total_q = len(my_quotes) if not my_quotes.empty else 0
    approved_q = len(my_quotes[my_quotes["quotation_status"] == "Approved"]) if not my_quotes.empty else 0
    rejected_q = len(my_quotes[my_quotes["quotation_status"] == "Rejected"]) if not my_quotes.empty else 0
    total_fol = len(my_logs) if not my_logs.empty else 0

    with c1:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#184B9C; margin:0;'>{total_q}</h3><p style='margin:0; font-weight:700;'>Total Quotes Generated</p></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#00A859; margin:0;'>{approved_q}</h3><p style='margin:0; font-weight:700;'>Approved Quotes</p></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#E11D48; margin:0;'>{rejected_q}</h3><p style='margin:0; font-weight:700;'>Rejected Quotes</p></div>", unsafe_allow_html=True)
    with c4:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#0284C7; margin:0;'>{total_fol}</h3><p style='margin:0; font-weight:700;'>Follow-ups Conducted</p></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 📅 Performance Window Filter")
    
    time_window = st.selectbox("Select Time Horizon:", ["All Time", "Last 7 Days", "Last 15 Days", "Last 30 Days", "Custom Date Range"])

    if not my_quotes.empty:
        st.markdown("###### 📄 Your Quotation Activity History")
        st.dataframe(my_quotes, width="stretch", hide_index=True)
    else:
        st.info("No quotation activity logged yet for your account.")

    if not my_logs.empty:
        st.markdown("###### 📞 Your Follow-up Log History")
        st.dataframe(my_logs, width="stretch", hide_index=True)