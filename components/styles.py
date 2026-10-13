"""
Custom CSS Injector for Corporate Brand Theme.
"""
import streamlit as st

PRIMARY_BLUE = "#184B9C"
DARK_NAVY = "#0E2C68"
BG_LIGHT = "#F8FAFC"

def apply_custom_theme():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"], .stApp {{
            font-family: 'Inter', -apple-system, sans-serif !important;
            background-color: {BG_LIGHT} !important;
            color: {DARK_NAVY} !important;
        }}

        header[data-testid="stHeader"] {{ background-color: transparent !important; }}

        /* Sidebar Styling */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {PRIMARY_BLUE} 0%, {DARK_NAVY} 100%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
        }}
        [data-testid="stSidebar"] * {{ color: #FFFFFF !important; }}

        /* Navigation Radio Labels */
        div[data-testid="stRadio"] label {{
            background: rgba(255, 255, 255, 0.08) !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            font-size: 13.5px !important;
            font-weight: 600 !important;
            padding: 10px 14px !important;
            margin-bottom: 6px !important;
            border-radius: 8px !important;
            transition: all 0.2s ease-in-out !important;
            cursor: pointer !important;
        }}
        div[data-testid="stRadio"] label:hover {{
            background-color: rgba(255, 255, 255, 0.2) !important;
            transform: translateX(3px);
        }}

        /* Input High-Contrast 2px Blue Borders */
        div[data-baseweb="input"],
        div[data-baseweb="base-input"],
        div[data-baseweb="select"] > div {{
            background-color: #FFFFFF !important;
            border: 2px solid {PRIMARY_BLUE} !important;
            border-radius: 8px !important;
            padding: 2px 4px !important;
        }}

        /* Login Button (Green) */
        div[data-testid="stFormSubmitButton"] > button {{
            background: linear-gradient(135deg, #16A34A 0%, #15803D 100%) !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            font-size: 15px !important;
            font-weight: 700 !important;
            border: none !important;
            padding: 12px 20px !important;
            width: 100% !important;
            box-shadow: 0 4px 16px rgba(22, 163, 74, 0.35) !important;
            transition: all 0.2s ease-in-out !important;
            text-transform: uppercase !important;
        }}
        div[data-testid="stFormSubmitButton"] > button:hover {{
            background: linear-gradient(135deg, #15803D 0%, #166534 100%) !important;
        }}

        /* Logout Button (Vibrant Green Gradient) */
        div.stButton > button[key="single_app_logout_btn"] {{
            background: linear-gradient(135deg, #16A34A 0%, #15803D 100%) !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            border: none !important;
            padding: 10px 16px !important;
            box-shadow: 0 4px 12px rgba(22, 163, 74, 0.35) !important;
            transition: all 0.2s ease-in-out !important;
            text-transform: uppercase !important;
        }}
        div.stButton > button[key="single_app_logout_btn"]:hover {{
            background: linear-gradient(135deg, #15803D 0%, #166534 100%) !important;
            transform: translateY(-1px) !important;
        }}

        .saas-card {{
            background: #FFFFFF !important;
            border: 1.5px solid rgba(24, 75, 156, 0.18) !important;
            border-radius: 12px !important;
            padding: 18px 22px !important;
            box-shadow: 0 6px 18px rgba(14, 44, 104, 0.06) !important;
            margin-bottom: 14px !important;
        }}
        </style>
    """, unsafe_allow_html=True)