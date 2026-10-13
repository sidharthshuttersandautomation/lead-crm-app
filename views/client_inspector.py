"""
Master Client Inspector.
"""
import streamlit as st
import pandas as pd

def render_client_inspector(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>🔍 Client 360-Degree Master Inspector</h2>", unsafe_allow_html=True)

    df_leads = db_adapter.fetch_all("leads_master")
    if df_leads.empty:
        st.info("No client records currently in master sheet.")
        return

    search_query = st.text_input("🔍 Search Client by Name, Company Name, or Client ID:", placeholder="e.g. BID-Oct-26-001, Omprakash, or Blue Cold")

    filtered_df = df_leads.copy()
    if search_query:
        query_str = search_query.strip().lower()
        filtered_df = filtered_df[
            filtered_df["client_id"].astype(str).str.lower().str.contains(query_str, na=False) |
            filtered_df["client_name"].astype(str).str.lower().str.contains(query_str, na=False) |
            filtered_df["company_name"].astype(str).str.lower().str.contains(query_str, na=False)
        ]

    st.markdown("---")
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Search Export (CSV)",
        data=csv_data,
        file_name="client_inspector_export.csv",
        mime="text/csv"
    )