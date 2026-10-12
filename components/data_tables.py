import streamlit as st
import pandas as pd

def render_interactive_table(
    df: pd.DataFrame, title: str = "", height: int = 350, key: str = "data_table"
):
    if title:
        st.subheader(title)

    if df.empty:
        st.info("No records available in this view.")
        return

    st.dataframe(
        df,
        use_container_width=True,
        height=height,
        hide_index=True,
    )