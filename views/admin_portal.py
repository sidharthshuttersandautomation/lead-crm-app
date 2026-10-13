"""
views/admin_portal.py - Executive Control Center & User Management
"""
import datetime
import pandas as pd
import streamlit as st

def render_admin_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>🛡️ Executive Admin Analytics Control Center</h2>", unsafe_allow_html=True)

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")

    total_leads = len(df_leads) if not df_leads.empty else 0
    total_quotes = len(df_quotes) if not df_quotes.empty else 0
    
    total_sales = 0.0
    if not df_quotes.empty and "qut_amount" in df_quotes.columns:
        total_sales = pd.to_numeric(df_quotes["qut_amount"], errors="coerce").fillna(0).sum()

    st.markdown("##### 📊 Operational Overview")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Ingested Leads", total_leads)
    with c2:
        st.metric("Total Quotations Issued", total_quotes)
    with c3:
        st.metric("Combined System Records", total_leads + total_quotes)
    with c4:
        st.metric("Total Sales Value", f"₹{total_sales:,.0f}")

    st.markdown("---")
    st.markdown("##### 📋 System Master Data Access")
    
    # Session state toggle so data is hidden until button is clicked
    if "show_admin_excel" not in st.session_state:
        st.session_state["show_admin_excel"] = False

    if st.button("📊 Display / Hide Complete Master Sheet"):
        st.session_state["show_admin_excel"] = not st.session_state["show_admin_excel"]

    if st.session_state["show_admin_excel"]:
        st.markdown("###### 📑 Combined Leads & Quotations Master Data")
        st.dataframe(df_leads, use_container_width=True, hide_index=True)


def render_user_management(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>👥 User Management Governance</h2>", unsafe_allow_html=True)

    df_emp = db_adapter.fetch_all("employees")
    next_emp_id = f"EMP-{len(df_emp) + 109 if not df_emp.empty else 109}"

    st.markdown("##### ➕ Add New Employee Account")
    with st.form("add_employee_form_admin", clear_on_submit=True):
        st.info(f"🆔 **Auto Generated Employee ID:** `{next_emp_id}`")
        c1, c2 = st.columns(2)
        with c1:
            e_fullname = st.text_input("Full Name *")
            e_email = st.text_input("Email *", placeholder="employee@sidharth.com")
        with c2:
            e_password = st.text_input("Password *", type="password")
            e_role = st.selectbox("Role *", ["ADMIN", "LGE", "QS", "SAM", "OPERATIONS"])

        submit_emp = st.form_submit_button("💾 Create Employee Account")

        if submit_emp:
            if e_fullname and e_email and e_password:
                new_emp = {
                    "employee_id": next_emp_id,
                    "full_name": e_fullname,
                    "email": e_email,
                    "password": e_password,
                    "role": e_role,
                    "is_active": 1
                }
                db_adapter.insert_row("employees", new_emp)
                st.toast(f"✅ Created Employee '{e_fullname}' ({next_emp_id})!", icon="🎉")
                st.rerun()
            else:
                st.error("Please fill in all mandatory fields.")

    st.markdown("---")
    if "show_emp_excel" not in st.session_state:
        st.session_state["show_emp_excel"] = False

    if st.button("📋 Display / Hide Employee Directory Sheet"):
        st.session_state["show_emp_excel"] = not st.session_state["show_emp_excel"]

    if st.session_state["show_emp_excel"]:
        st.dataframe(df_emp, use_container_width=True, hide_index=True)