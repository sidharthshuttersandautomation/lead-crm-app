import streamlit as st
import pandas as pd
import plotly.express as px
from components.kpi_cards import render_kpi_card
from components.data_tables import render_interactive_table

def render_admin_portal(db_adapter, user):
    st.title(" Admin Control Center & Analytics")
    
    # Global Date Range Preset Filters
    st.markdown("### Date Filter Presets")
    filter_option = st.selectbox(
        "Select Performance Time Horizon",
        ["10 Days", "15 Days", "1 Month", "3 Months", "4 Months", "6 Months", "9 Months", "12 Months", "Custom Date Range"]
    )
    if filter_option == "Custom Date Range":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.date_input("Start Date")
        with col_d2:
            st.date_input("End Date")

    tab1, tab2, tab3 = st.tabs(["System Performance", "Employee SLA & Turnaround", "User Management"])
    
    with tab1:
        q_df = db_adapter.fetch_table("quotation_sheet")
        l_df = db_adapter.fetch_table("leads_data")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            render_kpi_card("Total Pipeline Value", "₹48,50,000", color="#10B981")
        with c2:
            render_kpi_card("Total Active Leads", str(len(l_df)))
        with c3:
            render_kpi_card("Overnight Submissions (>5:30 PM)", "12", color="#F59E0B")
            
        if not l_df.empty and "source" in l_df:
            fig = px.pie(l_df, names="source", title="Lead Generation by Source Breakdown")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Employee SLA Compliance & Processing Speed")
        q_df = db_adapter.fetch_table("quotation_sheet")
        render_interactive_table(q_df, "admin_sla_table")

    with tab3:
        st.subheader("System User Provisioning")
        users_df = db_adapter.fetch_table("users")
        render_interactive_table(users_df, "admin_users_table")
        
        with st.expander("Provision New System User"):
            with st.form("create_user_form"):
                uname = st.text_input("Full Name")
                uemail = st.text_input("Email")
                urole = st.selectbox("Assign Portal Role", ["Admin", "Lead Executive", "Quotation Specialist", "Sales Manager"])
                upass = st.text_input("Password", type="password")
                
                if st.form_submit_button("Add User"):
                    new_u = {
                        "user_id": f"u{len(users_df)+1}",
                        "full_name": uname,
                        "email": uemail,
                        "role": urole,
                        "password_hash": upass
                    }
                    db_adapter.insert_row("users", new_u)
                    st.success("New user created successfully!")
                    st.rerun()