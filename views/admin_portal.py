import streamlit as st
import plotly.express as px
from datetime import datetime
from config.settings import DATE_FILTER_OPTIONS, PRIMARY_BLUE
from components.kpi_cards import render_kpi_cards
from components.data_tables import render_interactive_table

def render_admin_portal(db, current_user: dict):
    st.title("🛡️ Admin & Analytics Control Center")
    st.caption("System Performance, SLA Monitoring & User Governance")

    st.selectbox("📅 Reporting Timeframe", DATE_FILTER_OPTIONS, index=2)
    st.divider()

    df_leads = db.fetch_all("leads_data")
    df_quotes = db.fetch_all("quotation_sheet")
    df_users = db.fetch_all("users")

    kpis = [
        {"label": "Total System Leads", "value": len(df_leads)},
        {"label": "Quotations Drafted", "value": len(df_quotes)},
    ]
    render_kpi_cards(kpis)
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 Lead Sources Distribution")
        if not df_leads.empty and "source" in df_leads.columns:
            source_counts = df_leads["source"].value_counts().reset_index()
            source_counts.columns = ["Source", "Count"]
            fig1 = px.pie(source_counts, values="Count", names="Source")
            st.plotly_chart(fig1, use_container_width=True)

    with c2:
        st.subheader("⏱️ SLA Cutoff Distribution")
        if not df_quotes.empty and "is_after_cutoff" in df_quotes.columns:
            sla_counts = df_quotes["is_after_cutoff"].value_counts().reset_index()
            sla_counts.columns = ["After 5:30 PM Cutoff", "Count"]
            fig2 = px.bar(sla_counts, x="After 5:30 PM Cutoff", y="Count")
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("👥 User Management & RBAC")
    tab1, tab2 = st.tabs(["Directory", "Add User"])
    with tab1:
        render_interactive_table(df_users, key="admin_users_table")
    with tab2:
        with st.form("add_user_form"):
            u_id = st.text_input("User ID (e.g., U109)")
            u_name = st.text_input("Full Name")
            u_email = st.text_input("Email")
            u_role = st.selectbox("Role", ["LGE", "QS", "SAM", "ADMIN"])

            if st.form_submit_button("Create User"):
                db.insert_row(
                    "users",
                    {
                        "user_id": u_id,
                        "full_name": u_name,
                        "email": u_email,
                        "role": u_role,
                        "created_at": datetime.now().strftime("%Y-%m-%d"),
                    },
                )
                st.success(f"User {u_name} registered!")
                st.rerun()