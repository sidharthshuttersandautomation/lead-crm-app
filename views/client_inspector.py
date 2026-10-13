"""
Master Client Inspector & Column Export Workstation.
"""
import streamlit as st
import pandas as pd
from config.settings import REPORTING_TIMEFRAMES

def render_client_inspector(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>🔍 Client 360-Degree Master Inspector</h2>", unsafe_allow_html=True)

    df_leads = db_adapter.fetch_all("leads_data")
    if df_leads.empty:
        st.info("No client records currently in master sheet.")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        search_query = st.text_input("🔍 Search Client by Name or Client ID:", placeholder="e.g. BID-Oct-26-001 or Albert")
    with c2:
        time_range = st.selectbox("📅 Timeframe Filter", REPORTING_TIMEFRAMES, index=2, key="inspector_tf")

    all_cols = list(df_leads.columns)
    default_cols = [c for c in ["client_id", "client_name", "product", "qty", "address", "city", "final_status"] if c in all_cols]

    selected_cols = st.multiselect("📊 Select Custom Columns to Display & Export:", options=all_cols, default=default_cols)

    filtered_df = df_leads.copy()
    if search_query:
        filtered_df = filtered_df[
            filtered_df["client_id"].astype(str).str.contains(search_query, case=False) |
            filtered_df["client_name"].astype(str).str.contains(search_query, case=False)
        ]

    display_df = filtered_df[selected_cols] if selected_cols else filtered_df

    st.markdown("---")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv_data = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Custom Client Report (CSV)",
        data=csv_data,
        file_name="client_inspector_report.csv",
        mime="text/csv"
    )