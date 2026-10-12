import streamlit as st
import pandas as pd

def render_interactive_table(df: pd.DataFrame, key: str):
    if df.empty:
        st.info("No records available.")
        return
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        key=key
    )