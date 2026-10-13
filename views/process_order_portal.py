"""
Order Fulfillment Workstation.
"""
import streamlit as st

def render_process_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>⚙️ Factory Order & PO/PI Fulfillment</h2>", unsafe_allow_html=True)
    df_orders = db_adapter.fetch_all("process_order")
    st.dataframe(df_orders, use_container_width=True, hide_index=True)