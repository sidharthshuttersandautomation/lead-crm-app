import streamlit as st

def render_kpi_cards(kpi_data: list[dict]):
    cols = st.columns(len(kpi_data))
    for idx, item in enumerate(kpi_data):
        with cols[idx]:
            st.metric(
                label=item.get("label"),
                value=item.get("value"),
                delta=item.get("delta", None),
                help=item.get("help", None),
            )