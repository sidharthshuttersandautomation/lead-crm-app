"""
views/employee_report.py - Executive Individual Employee Report Card & High-Contrast UI.
"""
import datetime
import pandas as pd
import streamlit as st
import plotly.express as px

def render_employee_report(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800; margin-bottom:15px;'>📊 Individual Employee Performance Report Card</h2>", unsafe_allow_html=True)

    df_emp = db_adapter.fetch_all("employees")
    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_logs = db_adapter.fetch_all("followup_logs")

    if df_emp.empty:
        st.info("No employee profiles found in master database.")
        return

    # 1. Top Control Bar: Individual Employee Selector & Date Horizon
    c_emp, c_window = st.columns([2.2, 1.2])
    with c_emp:
        # Create robust label mapping with fallback
        df_emp["emp_label"] = df_emp["full_name"].fillna("Unknown") + " (" + df_emp["role"].fillna("EMP") + " - " + df_emp["employee_id"].fillna("ID") + ")"
        emp_map = dict(zip(df_emp["emp_label"], df_emp["employee_id"]))
        
        selected_emp_label = st.selectbox("👤 Select Employee to View Report Card:", list(emp_map.keys()))
        selected_emp_id = emp_map[selected_emp_label]

    with c_window:
        time_window = st.selectbox("📅 Reporting Horizon:", [
            "1 Week (Last 7 Days)",
            "15 Days",
            "1 Month (30 Days)",
            "3 Months",
            "6 Months",
            "1 Year",
            "All Time"
        ], index=6)

    # 2. Extract Individual Employee Info
    emp_match = df_emp[df_emp["employee_id"] == selected_emp_id]
    if emp_match.empty:
        st.warning("Selected employee record not found.")
        return
        
    emp_row = emp_match.iloc[0]
    emp_name = str(emp_row.get("full_name", "Employee"))
    emp_role = str(emp_row.get("role", "LGE")).upper()
    emp_email = str(emp_row.get("email", "N/A"))

    st.markdown("---")
    
    # Header High-Contrast Profile Card
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #0E2C68 0%, #184B9C 100%); color: #FFFFFF; padding: 22px 25px; border-radius: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 25px;'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <h2 style='margin:0; color:#FFFFFF; font-weight:800; font-size:24px;'>👤 {emp_name}</h2>
                <div style='margin-top:8px; color:#E0F2FE; font-size:14.5px; font-weight:500;'>
                    🆔 <b>Employee ID:</b> <span style='color:#FFFFFF; font-weight:700;'>{selected_emp_id}</span> &nbsp;|&nbsp; 
                    📧 <b>Email:</b> <span style='color:#FFFFFF; font-weight:700;'>{emp_email}</span>
                </div>
            </div>
            <div style='background:#00A859; color:#FFFFFF; padding:8px 20px; border-radius:25px; font-weight:800; font-size:13px; letter-spacing:0.5px; text-transform:uppercase; box-shadow: 0 2px 6px rgba(0,0,0,0.2);'>
                ROLE: {emp_role}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. Bug-Free Series-Aligned Filtering Logic
    # Filter Leads (LGE or SAM or QS)
    my_leads = pd.DataFrame()
    if not df_leads.empty:
        mask_lge = (df_leads["handled_by_lge_id"] == selected_emp_id) if "handled_by_lge_id" in df_leads.columns else pd.Series(False, index=df_leads.index)
        mask_sam = (df_leads["assigned_sam_id"] == selected_emp_id) if "assigned_sam_id" in df_leads.columns else pd.Series(False, index=df_leads.index)
        mask_qs = (df_leads["claimed_qs_id"] == selected_emp_id) if "claimed_qs_id" in df_leads.columns else pd.Series(False, index=df_leads.index)
        
        my_leads = df_leads[mask_lge | mask_sam | mask_qs].copy()

    # Filter Quotes (QS / Shared By)
    my_quotes = pd.DataFrame()
    if not df_quotes.empty:
        mask_shared = (df_quotes["shared_by_id"] == selected_emp_id) if "shared_by_id" in df_quotes.columns else pd.Series(False, index=df_quotes.index)
        mask_claimed = (df_quotes["claimed_qs_id"] == selected_emp_id) if "claimed_qs_id" in df_quotes.columns else pd.Series(False, index=df_quotes.index)
        
        my_quotes = df_quotes[mask_shared | mask_claimed].copy()

    # Filter Follow-up Logs
    my_logs = pd.DataFrame()
    if not df_logs.empty:
        mask_log = (df_logs["employee_id"] == emp_name) | (df_logs["employee_id"] == selected_emp_id)
        my_logs = df_logs[mask_log].copy()

    # 4. Individual Executive Scorecard KPI Cards
    total_leads = len(my_leads)
    total_quotes = len(my_quotes)
    approved_quotes = len(my_quotes[my_quotes["quotation_status"] == "Approved"]) if not my_quotes.empty and "quotation_status" in my_quotes.columns else 0
    total_followups = len(my_logs)

    st.markdown("<h4 style='color:#0E2C68; font-weight:700; margin-bottom:15px;'>📈 Key Operational Metrics</h4>", unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div style='background:#FFFFFF; padding:18px; border-radius:12px; border-left:5px solid #184B9C; box-shadow:0 2px 8px rgba(0,0,0,0.06); text-align:center;'>
            <h2 style='color:#184B9C; margin:0; font-weight:800;'>{total_leads}</h2>
            <p style='margin:4px 0 0 0; color:#475569; font-weight:700; font-size:13px;'>Leads Handled</p>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div style='background:#FFFFFF; padding:18px; border-radius:12px; border-left:5px solid #0284C7; box-shadow:0 2px 8px rgba(0,0,0,0.06); text-align:center;'>
            <h2 style='color:#0284C7; margin:0; font-weight:800;'>{total_quotes}</h2>
            <p style='margin:4px 0 0 0; color:#475569; font-weight:700; font-size:13px;'>Quotes Dispatched</p>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div style='background:#FFFFFF; padding:18px; border-radius:12px; border-left:5px solid #00A859; box-shadow:0 2px 8px rgba(0,0,0,0.06); text-align:center;'>
            <h2 style='color:#00A859; margin:0; font-weight:800;'>{approved_quotes}</h2>
            <p style='margin:4px 0 0 0; color:#475569; font-weight:700; font-size:13px;'>Approved Quotes</p>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div style='background:#FFFFFF; padding:18px; border-radius:12px; border-left:5px solid #D97706; box-shadow:0 2px 8px rgba(0,0,0,0.06); text-align:center;'>
            <h2 style='color:#D97706; margin:0; font-weight:800;'>{total_followups}</h2>
            <p style='margin:4px 0 0 0; color:#475569; font-weight:700; font-size:13px;'>Follow-up Calls Taken</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 5. Interactive Visual Analytics Section
    st.markdown("<h4 style='color:#0E2C68; font-weight:700; margin-bottom:15px;'>📊 Interactive Visual Analytics</h4>", unsafe_allow_html=True)
    
    g1, g2 = st.columns(2)

    with g1:
        st.markdown("###### 🍩 Quotation Outcome Ratio")
        if not my_quotes.empty and "quotation_status" in my_quotes.columns:
            status_counts = my_quotes["quotation_status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]

            fig_donut = px.pie(
                status_counts, 
                values="Count", 
                names="Status", 
                hole=0.48,
                color="Status",
                color_discrete_map={"Approved": "#00A859", "Rejected": "#E11D48", "Under Review": "#0284C7", "Pending": "#F59E0B"}
            )
            fig_donut.update_traces(textposition='inside', textinfo='percent+label', hoverinfo='label+value+percent')
            fig_donut.update_layout(margin=dict(t=15, b=15, l=15, r=15), height=320)
            st.plotly_chart(fig_donut, width="stretch")
        else:
            st.info(f"No quotation records linked to {emp_name}.")

    with g2:
        st.markdown("###### 📶 Handled Lead Source Split")
        if not my_leads.empty and "source" in my_leads.columns:
            source_counts = my_leads["source"].value_counts().reset_index()
            source_counts.columns = ["Source", "Leads"]

            fig_bar = px.bar(
                source_counts,
                x="Source",
                y="Leads",
                color="Source",
                text="Leads",
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_bar.update_traces(texttemplate='%{text}', textposition='outside')
            fig_bar.update_layout(margin=dict(t=15, b=15, l=15, r=15), height=320, showlegend=False, yaxis_title="Number of Leads")
            st.plotly_chart(fig_bar, width="stretch")
        else:
            st.info(f"No lead records linked to {emp_name}.")

    st.markdown("---")

    # 6. High-Visibility Tabbed Detailed Activity Tables
    st.markdown(f"<h4 style='color:#0E2C68; font-weight:700; margin-bottom:15px;'>📋 Detailed Activity Records for {emp_name}</h4>", unsafe_allow_html=True)

    tab_leads, tab_quotes, tab_logs = st.tabs([
        f"📥 Handled Leads ({len(my_leads)})", 
        f"📄 Dispatched Quotes ({len(my_quotes)})", 
        f"📞 Follow-up Interactions ({len(my_logs)})"
    ])

    with tab_leads:
        if not my_leads.empty:
            # Re-order columns for clear visibility
            col_order = [c for c in ["lead_id", "client_id", "source", "final_status", "quotation_status", "ingestion_date"] if c in my_leads.columns]
            other_c = [c for c in my_leads.columns if c not in col_order]
            st.dataframe(my_leads[col_order + other_c], width="stretch", hide_index=True)
        else:
            st.info("No lead records logged for this employee.")

    with tab_quotes:
        if not my_quotes.empty:
            col_order_q = [c for c in ["quotation_number", "client_id", "qut_amount", "revised", "quotation_status", "approved_date"] if c in my_quotes.columns]
            other_cq = [c for c in my_quotes.columns if c not in col_order_q]
            st.dataframe(my_quotes[col_order_q + other_cq], width="stretch", hide_index=True)
        else:
            st.info("No quotation records logged for this employee.")

    with tab_logs:
        if not my_logs.empty:
            col_order_l = [c for c in ["followup_id", "lead_id", "followup_status", "scheduled_call_time", "notes"] if c in my_logs.columns]
            other_cl = [c for c in my_logs.columns if c not in col_order_l]
            st.dataframe(my_logs[col_order_l + other_cl], width="stretch", hide_index=True)
        else:
            st.info("No follow-up call logs recorded for this employee.")

    st.markdown("---")

    # 7. Downloadable Report Card Summary Exporter
    st.markdown("##### 📥 Export Individual Report Card")
    
    summary_data = {
        "Metric": ["Employee Name", "Employee ID", "Role", "Email", "Total Leads Handled", "Total Quotes Dispatched", "Approved Quotes", "Follow-ups Conducted"],
        "Value": [emp_name, selected_emp_id, emp_role, emp_email, total_leads, total_quotes, approved_quotes, total_followups]
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