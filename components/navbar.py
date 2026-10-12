import streamlit as st

def render_navbar(current_role: str):
    # CSS styling ensuring contrast and rendering compatibility across macOS and iOS
    st.markdown("""
        <style>
            .stApp header {visibility: hidden;}
            .custom-nav {
                background-color: #0A4B8A !important;
                padding: 12px 24px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-radius: 8px;
                margin-bottom: 25px;
                box-shadow: 0px 4px 10px rgba(0,0,0,0.15);
            }
            .nav-brand {
                color: #FFFFFF !important;
                font-size: 20px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            .nav-user {
                color: #E2E8F0 !important;
                font-size: 14px;
                font-weight: 500;
            }
        </style>
        <div class="custom-nav">
            <div class="nav-brand">SIDHARTH SHUTTER & AUTOMATION CRM</div>
            <div class="nav-user">Role: <b>""" + current_role + """</b></div>
        </div>
    """, unsafe_allow_html=True)