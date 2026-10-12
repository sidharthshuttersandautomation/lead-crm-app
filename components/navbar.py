import streamlit as st
from config.settings import PRIMARY_BLUE

def inject_custom_css():
    css = f"""
    <style>
        header[data-testid="stHeader"] {{
            background-color: {PRIMARY_BLUE} !important;
        }}
        .brand-header {{
            background-color: {PRIMARY_BLUE};
            padding: 1rem 1.5rem;
            border-radius: 8px;
            color: white;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .brand-title {{
            font-size: 1.4rem;
            font-weight: 700;
            color: #FFFFFF !important;
            margin: 0;
        }}
        .brand-subtitle {{
            font-size: 0.85rem;
            color: #E2E8F0 !important;
            margin: 0;
        }}
        .user-badge {{
            background: rgba(255, 255, 255, 0.15);
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            color: #FFFFFF;
            font-weight: 600;
            font-size: 0.85rem;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }}
        .stButton>button {{
            background-color: {PRIMARY_BLUE};
            color: white !important;
            font-weight: 600;
            border-radius: 6px;
            border: none;
            padding: 0.5rem 1rem;
        }}
        div[data-testid="stMetricValue"] {{
            color: {PRIMARY_BLUE} !important;
            font-weight: 700;
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_navbar(current_user: dict):
    inject_custom_css()
    role_titles = {
        "LGE": "Lead Generation Portal",
        "QS": "Quotation Desk Portal",
        "SAM": "Sales Management Portal",
        "ADMIN": "Admin Control Center & Analytics",
    }
    user_role = current_user.get("role", "LGE")
    portal_title = role_titles.get(user_role, "Lead CRM Portal")

    st.markdown(
        f"""
        <div class="brand-header">
            <div>
                <p class="brand-title">SIDHARTH SHUTTER & AUTOMATION</p>
                <p class="brand-subtitle">{portal_title}</p>
            </div>
            <div class="user-badge">
                👤 {current_user.get('name')} ({user_role})
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )