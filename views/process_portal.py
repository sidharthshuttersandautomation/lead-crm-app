import streamlit as st
from components.data_tables import render_interactive_table

def render_process_portal(db_adapter, user):
    st.title(" Order Fulfillment & Production Tracker")
    proc_df = db_adapter.fetch_table("process_order")
    
    st.subheader("Post-Sale Order Execution Pipeline")
    render_interactive_table(proc_df, "process_orders_table")