"""components/data_tables.py - Standard table display."""
import pandas as pd
import streamlit as st


def render_interactive_table(df: pd.DataFrame, title: str = "", height: int = 350, key: str = "data_table"):
    if title:
        st.subheader(title)
    if df is None or df.empty:
        st.info("No records in this view yet.")
        return
    st.dataframe(df, width="stretch", height=height, hide_index=True, key=key)
