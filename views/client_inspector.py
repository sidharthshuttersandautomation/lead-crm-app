"""
views/client_inspector.py - 360-Degree Client Inspector with Filters & BID/SID Tracking.
"""
import datetime
import pandas as pd
import streamlit as st

def render_client_inspector(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>🔍 Client 360-Degree Inspector & Exporter</h2>", unsafe_allow_html=True)

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")

    if df_leads.empty:
        st.info("No client records currently available in master database.")
        return

    # Ensure BID ID and SID references are present and explicitly displayed
    if "client_id" in df_leads.columns:
        df_leads["BID_ID"] = df_leads["client_id"]
        df_leads["SID"] = "SID-" + df_leads["lead_id"].astype(str).str.zfill(4)

    st.markdown("##### 🔎 Multi-Attribute Search & Dynamic Filters")
    
    col_search, col_source, col_status = st.columns([2, 1, 1])
    with col_search:
        search_query = st.text_input(
            "🔍 Search Client (by Client/BID ID, SID, Name, or Company):",
            placeholder="e.g. BID-Oct-26-001, SID-0005, Omprakash, or Blue Cold"
        ).strip().lower()
    with col_source:
        source_options = ["All Sources"] + list(df_leads["source"].dropna().unique()) if "source" in df_leads.columns else ["All Sources"]
        selected_source = st.selectbox("Filter by Source:", source_options)
    with col_status:
        status_options = ["All Quotation Statuses"] + list(df_leads["quotation_status"].dropna().unique()) if "quotation_status" in df_leads.columns else ["All Quotation Statuses"]
        selected_status = st.selectbox("Filter by Quotation Status:", status_options)

    # Date Range Filter
    c_date1, c_date2 = st.columns(2)
    with c_date1:
        start_date = st.date_input("From Date:", value=datetime.date(2026, 10, 1))
    with c_date2:
        end_date = st.date_input("To Date:", value=datetime.date(2026, 10, 31))

    filtered_df = df_leads.copy()

    # Apply Search Filter
    if search_query:
        filtered_df = filtered_df[
            filtered_df["BID_ID"].astype(str).str.lower().str.contains(search_query, na=False) |
            filtered_df["SID"].astype(str).str.lower().str.contains(search_query, na=False) |
            filtered_df["client_name"].astype(str).str.lower().str.contains(search_query, na=False) |
            filtered_df["company_name"].astype(str).str.lower().str.contains(search_query, na=False)
        ]

    # Apply Dropdown Filters
    if selected_source != "All Sources" and "source" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["source"] == selected_source]

    if selected_status != "All Quotation Statuses" and "quotation_status" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["quotation_status"] == selected_status]

    # Apply Date Range Filter
    if "ingestion_date" in filtered_df.columns:
        filtered_df["ingestion_date_dt"] = pd.to_datetime(filtered_df["ingestion_date"], errors="coerce").dt.date
        filtered_df = filtered_df[
            (filtered_df["ingestion_date_dt"] >= start_date) & 
            (filtered_df["ingestion_date_dt"] <= end_date)
        ]
        filtered_df = filtered_df.drop(columns=["ingestion_date_dt"])

    st.markdown("---")
    st.markdown(f"###### 📊 Displaying `{len(filtered_df)}` Matching Client Record(s)")

    # Rearrange columns so BID ID and SID appear right at the front
    front_cols = ["BID_ID", "SID", "client_name", "company_name", "product", "qty", "city", "source", "quotation_status"]
    other_cols = [c for c in filtered_df.columns if c not in front_cols]
    display_cols = [c for c in front_cols if c in filtered_df.columns] + other_cols

    display_df = filtered_df[display_cols]
    st.dataframe(display_df, width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("##### 📥 Export Filtered Client Report")
    
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        export_columns = st.multiselect(
            "Select Columns to Include in Download:",
            options=list(display_df.columns),
            default=display_cols[:9]
        )
    with exp_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        export_df = display_df[export_columns] if export_columns else display_df
        csv_data = export_df.to_csv(index=False).encode("utf-8")
        
        st.download_button(
            label="📥 Download Filtered Client Sheet (CSV)",
            data=csv_data,
            file_name=f"client_inspector_report_{start_date}_to_{end_date}.csv",
            mime="text/csv",
            width="stretch"
        )