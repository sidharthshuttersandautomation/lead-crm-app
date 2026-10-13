"""
Admin Control Center & User Management Workspace.
"""
import datetime
import pandas as pd
import streamlit as st
from config.settings import REPORTING_TIMEFRAMES

def render_admin_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>🛡️ Executive Admin Analytics Control Center</h2>", unsafe_allow_html=True)

    df_leads = db_adapter.fetch_all("leads_data")
    df_quotes = db_adapter.fetch_all("quotation_sheet")

    # Current Month Default Filter
    today = datetime.datetime.now()
    current_month_str = today.strftime("%B")

    month_leads = df_leads[df_leads["month"] == current_month_str] if not df_leads.empty and "month" in df_leads.columns else df_leads
    month_quotes = df_quotes if not df_quotes.empty else pd.DataFrame()

    total_sales = 0.0
    if not df_quotes.empty and "quotation_amount" in df_quotes.columns:
        total_sales = pd.to_numeric(df_quotes["quotation_amount"], errors="coerce").fillna(0).sum()

    st.markdown(f"##### 📊 Performance Snapshot ({current_month_str} {today.year})")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Current Month Leads", len(month_leads))
    with c2:
        st.metric("Total System Ingested Leads", len(df_leads))
    with c3:
        st.metric("Quotations Issued", len(df_quotes))
    with c4:
        st.metric("Total Sales Value", f"₹{total_sales:,.0f}")

    st.markdown("---")
    st.markdown("##### 📋 System Ingested Leads Master View")
    st.dataframe(df_leads, use_container_width=True, hide_index=True)


def render_user_management(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>👥 User Management Governance</h2>", unsafe_allow_html=True)

    df_users = db_adapter.fetch_all("users")

    st.markdown("##### ➕ Add New Employee Profile")
    with st.form("add_user_form_admin", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            u_username = st.text_input("Username / ID *").strip().lower()
            u_password = st.text_input("Password *", type="password")
        with c2:
            u_role = st.selectbox("Role *", ["ADMIN", "LGE", "QS", "SAM", "OPERATIONS"])
            u_fullname = st.text_input("Full Name *")

        if st.form_submit_button("💾 Create User Account"):
            if u_username and u_password and u_fullname:
                new_u = {
                    "user_id": f"U{len(df_users)+101}",
                    "full_name": u_fullname,
                    "email": f"{u_username}@sidharth.com",
                    "password": u_password,
                    "role": u_role
                }
                db_adapter.insert_row("users", new_u)
                st.toast(f"✅ User account '{u_username}' created successfully!", icon="🎉")
                st.rerun()
            else:
                st.error("Please fill in all mandatory fields.")

    st.markdown("---")
    if st.button("📋 Click to View / Export Registered User Accounts Sheet"):
        st.dataframe(df_users, use_container_width=True, hide_index=True)