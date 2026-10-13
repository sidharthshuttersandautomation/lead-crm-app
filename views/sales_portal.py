"""
Sales Account Management Workspace.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

def render_sales_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>💼 Sales Management Performance Board</h2>", unsafe_allow_html=True)

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_follow = db_adapter.fetch_all("followup_logs")

    total_leads_cnt = len(df_leads) if not df_leads.empty else 0
    total_quotes_cnt = len(df_quotes) if not df_quotes.empty else 0

    won_leads = df_leads[df_leads["final_status"].astype(str).str.lower().isin(["done", "won"])] if not df_leads.empty else pd.DataFrame()
    conversion_rate = round((len(won_leads) / total_leads_cnt * 100), 1) if total_leads_cnt > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Ingested Leads", total_leads_cnt)
    with c2:
        st.metric("Total Quotations Sent", total_quotes_cnt)
    with c3:
        st.metric("Deals Won", len(won_leads))
    with c4:
        st.metric("Lead Conversion Rate", f"{conversion_rate}%")

    st.markdown("---")
    g1, g2 = st.columns(2)

    with g1:
        st.markdown("##### 📦 Product-Wise Sales Demand")
        if not df_leads.empty and "product" in df_leads.columns:
            prod_counts = df_leads["product"].value_counts().reset_index()
            prod_counts.columns = ["Product", "Inquiries"]
            fig_prod = px.bar(prod_counts.head(8), x="Inquiries", y="Product", orientation="h", color="Inquiries", color_continuous_scale="Blues")
            st.plotly_chart(fig_prod, use_container_width=True)

    with g2:
        st.markdown("##### ⚠️ Lost Client Reason Analysis")
        if not df_follow.empty and "cancel_category" in df_follow.columns:
            lost_df = df_follow[df_follow["cancel_category"].astype(str) != "N/A"]
            if not lost_df.empty:
                cancel_counts = lost_df["cancel_category"].value_counts().reset_index()
                cancel_counts.columns = ["Loss Reason", "Count"]
                fig_bar = px.bar(cancel_counts, x="Loss Reason", y="Count", color="Count", color_continuous_scale="Reds")
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("No cancellation categories recorded.")
        else:
            st.info("No lost deal history tracked.")