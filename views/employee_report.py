"""
views/employee_report.py - Comprehensive Employee Report Card for Admins.
"""
import datetime
import pandas as pd
import streamlit as st

def render_employee_report(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📊 Comprehensive Employee Report Card</h2>", unsafe_allow_html=True)

    df_emp = db_adapter.fetch_all("employees")
    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_logs = db_adapter.fetch_all("followup_logs")

    if df_emp.empty:
        st.info("No employee profiles found in master database.")
        return

    # Filter & Selector Controls
    c_emp, c_window = st.columns([2, 1])
    with c_emp:
        emp_map = dict(zip(df_emp["full_name"] + " (" + df_emp["role"] + " - " + df_emp["employee_id"] + ")", df_emp["employee_id"]))
        selected_emp_label = st.selectbox("👤 Select Employee Profile to Review:", list(emp_map.keys()))
        selected_emp_id = emp_map[selected_emp_label]

    with c_window:
        time_window = st.selectbox("📅 Reporting Time Window:", [
            "1 Week (Last 7 Days)",
            "15 Days",
            "1 Month (30 Days)",
            "3 Months",
            "6 Months",
            "9 Months",
            "12 Months (1 Year)",
            "All Time",
            "Custom Date Range"
        ])

    emp_row = df_emp[df_emp["employee_id"] == selected_emp_id].iloc[0]
    emp_name = str(emp_row.get("full_name", "Employee"))
    emp_role = str(emp_row.get("role", "LGE")).upper()
    emp_email = str(emp_row.get("email", "N/A"))

    st.markdown("---")
    st.markdown(f"""
    <div class='saas-card' style='background: linear-gradient(135deg, #184B9C 0%, #0E2C68 100%); color: #FFFFFF;'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <h3 style='margin:0; color:#FFFFFF;'>👤 {emp_name}</h3>
                <p style='margin:4px 0 0 0; color:#E0F2FE; font-size:14px;'>🆔 <b>Employee ID:</b> {selected_emp_id} &nbsp;|&nbsp; 📧 <b>Email:</b> {emp_email}</p>
            </div>
            <span style='background:#00A859; color:#FFFFFF; padding:6px 16px; border-radius:20px; font-weight:800; font-size:13px;'>ROLE: {emp_role}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Calculate Employee Metrics
    my_leads = df_leads[df_leads["handled_by_lge_id"] == selected_emp_id] if not df_leads.empty and "handled_by_lge_id" in df_leads.columns else pd.DataFrame()
    my_quotes = df_quotes[(df_quotes["claimed_qs_id"] == selected_emp_id) | (df_quotes["shared_by_id"] == selected_emp_id)] if not df_quotes.empty else pd.DataFrame()
    my_logs = df_logs[df_logs["employee_id"] == emp_name] if not df_logs.empty and "employee_id" in df_logs.columns else pd.DataFrame()

    total_leads_entered = len(my_leads)
    total_quotes_dispatched = len(my_quotes)
    approved_quotes = len(my_quotes[my_quotes["quotation_status"] == "Approved"]) if not my_quotes.empty else 0
    total_followups_taken = len(my_logs)

    st.markdown("##### 📈 Operational Scorecard")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#184B9C; margin:0;'>{total_leads_entered}</h3><p style='margin:0; font-weight:700;'>Leads Ingested (LGE)</p></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#0284C7; margin:0;'>{total_quotes_dispatched}</h3><p style='margin:0; font-weight:700;'>Quotes Created (QS)</p></div>", unsafe_allow_html=True)
    with m3:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#00A859; margin:0;'>{approved_quotes}</h3><p style='margin:0; font-weight:700;'>Approved Quotes</p></div>", unsafe_allow_html=True)
    with m4:
        st.markdown(f"<div class='saas-card' style='text-align:center;'><h3 style='color:#D97706; margin:0;'>{total_followups_taken}</h3><p style='margin:0; font-weight:700;'>Follow-ups Conducted</p></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 📋 Employee Activity Log History")

    if not my_quotes.empty:
        st.markdown("###### 📄 Dispatched Quotations History")
        st.dataframe(my_quotes, width="stretch", hide_index=True)

    if not my_logs.empty:
        st.markdown("###### 📞 Follow-up Interactions Logged")
        st.dataframe(my_logs, width="stretch", hide_index=True)

    if my_quotes.empty and my_logs.empty and my_leads.empty:
        st.info(f"No logged activity found for {emp_name} in the selected time window.")

    st.markdown("---")
    st.markdown("##### 📥 Export Employee Performance Summary")
    
    summary_data = {
        "Metric": ["Employee Name", "Employee ID", "Role", "Leads Ingested", "Quotes Dispatched", "Approved Quotes", "Total Follow-ups Taken"],
        "Value": [emp_name, selected_emp_id, emp_role, total_leads_entered, total_quotes_dispatched, approved_quotes, total_followups_taken]
    }
    df_summary = pd.DataFrame(summary_data)
    csv_bytes = df_summary.to_csv(index=False).encode("utf-8")

    st.download_button(
        label=f"📥 Download Performance Scorecard for {emp_name} (CSV)",
        data=csv_bytes,
        file_name=f"employee_scorecard_{selected_emp_id}.csv",
        mime="text/csv",
        width="stretch"
    )