import streamlit as st

def render_kpi_card(title: str, value: str, subtitle: str = "", color: str = "#0A4B8A"):
    st.markdown(f"""
        <div style="
            background-color: #FFFFFF;
            border-left: 5px solid {color};
            padding: 16px;
            border-radius: 6px;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.06);
            margin-bottom: 12px;
        ">
            <p style="margin:0; font-size: 13px; color: #64748B; font-weight: 600; text-transform: uppercase;">{title}</p>
            <h3 style="margin: 4px 0; font-size: 24px; color: #0F172A; font-weight: 700;">{value}</h3>
            {"<p style='margin:0; font-size: 12px; color: #10B981;'>" + subtitle + "</p>" if subtitle else ""}
        </div>
    """, unsafe_allow_html=True)