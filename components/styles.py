import streamlit as st

def apply_custom_theme():
    """Injects the corporate brand stylesheet into the Streamlit session."""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* Global Reset */
        html, body, [class*="css"], .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            background-color: #F8FAFC !important;
            color: #0E2C68 !important;
        }

        header[data-testid="stHeader"] { 
            background-color: transparent !important; 
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #184B9C 0%, #0E2C68 100%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
            box-shadow: 4px 0 20px rgba(14, 44, 104, 0.08) !important;
        }

        [data-testid="stSidebar"] * {
            color: #FFFFFF !important;
        }

        /* High-Contrast Blue Borders on Input Fields */
        div[data-baseweb="input"],
        div[data-baseweb="base-input"],
        div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border: 2px solid #184B9C !important;
            border-radius: 8px !important;
            padding: 2px 4px !important;
        }

        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="select"]:focus-within > div {
            border-color: #0E2C68 !important;
            box-shadow: 0 0 0 3px rgba(24, 75, 156, 0.25) !important;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextArea"] textarea {
            background-color: #FFFFFF !important;
            color: #0E2C68 !important;
            font-weight: 600 !important;
            font-size: 14px !important;
        }

        /* Gradient Submit Button */
        div[data-testid="stFormSubmitButton"] button,
        button[kind="primaryFormSubmit"] {
            background: linear-gradient(135deg, #184B9C 0%, #0E2C68 50%, #00A859 100%) !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            border: none !important;
            font-size: 15px !important;
            font-weight: 700 !important;
            padding: 12px 20px !important;
            margin-top: 15px !important;
            width: 100% !important;
            box-shadow: 0 4px 16px rgba(0, 168, 89, 0.3) !important;
            transition: all 0.3s ease-in-out !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        div[data-testid="stFormSubmitButton"] button:hover {
            background: linear-gradient(135deg, #0E2C68 0%, #184B9C 50%, #008F4C 100%) !important;
            box-shadow: 0 6px 20px rgba(0, 168, 89, 0.45) !important;
            transform: translateY(-2px);
        }
        </style>
    """, unsafe_allow_html=True)