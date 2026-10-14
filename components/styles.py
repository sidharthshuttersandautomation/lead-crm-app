"""
components/styles.py - Custom Styling for High-Contrast Readability.
"""
import streamlit as st

def apply_custom_theme():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"], .stApp {
            font-family: 'Inter', sans-serif !important;
            background-color: #F8FAFC !important;
            color: #0E2C68 !important;
        }

        /* High-Contrast Disabled Auto-Fetched Input Fields */
        div[data-baseweb="input"] input:disabled,
        div[data-baseweb="base-input"] input:disabled {
            background-color: #EFF6FF !important;
            color: #0E2C68 !important;
            -webkit-text-fill-color: #0E2C68 !important;
            font-weight: 700 !important;
            border: 1.5px solid #184B9C !important;
            opacity: 1 !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #184B9C 0%, #0E2C68 100%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
        [data-testid="stSidebar"] * { color: #FFFFFF !important; }

        /* Input High Contrast 2px Blue Borders */
        div[data-baseweb="input"],
        div[data-baseweb="base-input"],
        div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border: 2px solid #184B9C !important;
            border-radius: 8px !important;
        }

        /* Vibrant Green Gradient Submit Buttons */
        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #00A859 0%, #008F4C 100%) !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            font-size: 15px !important;
            font-weight: 700 !important;
            border: none !important;
            padding: 12px 20px !important;
            width: 100% !important;
            box-shadow: 0 4px 14px rgba(0, 168, 89, 0.35) !important;
            transition: all 0.2s ease-in-out !important;
            text-transform: uppercase !important;
            margin: 0 auto !important;
            display: block !important;
        }

        div.stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
            background: linear-gradient(135deg, #008F4C 0%, #00733D 100%) !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 18px rgba(0, 168, 89, 0.45) !important;
        }

        .saas-card {
            background: #FFFFFF !important;
            border: 1.5px solid rgba(24, 75, 156, 0.18) !important;
            border-radius: 12px !important;
            padding: 22px 26px !important;
            box-shadow: 0 6px 18px rgba(14, 44, 104, 0.08) !important;
            margin-bottom: 16px !important;
        }
        </style>
    """, unsafe_allow_html=True)