"""
app.py - Sidharth Shutter CRM Entry Point & Navigation Router.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from components.styles import apply_custom_theme
from database.sqlite_adapter import SQLiteAdapter
from utils.auth import init_session_auth, get_current_user, login_user, logout_user
from components.navbar import render_navbar

from views.lead_portal import render_lead_portal
from views.quotation_portal import (
    render_qs_performance_dashboard,
    render_qs_generator_and_claim,
    render_qs_detailed_form_entry,
    render_qs_followup_workday,
)
from views.sales_portal import render_sales_portal
from views.process_order_portal import render_process_portal
from views.client_inspector import render_client_inspector
from views.admin_portal import render_admin_portal, render_user_management
from views.employee_report import render_employee_report

st.set_page_config(
    page_title="Sidharth Shutter CRM",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_custom_theme()

db_adapter = SQLiteAdapter()
init_session_auth()

if not st.session_state.get("authenticated", False):
    st.markdown("<br><br>", unsafe_allow_html=True)
    c_left, c_center, c_right = st.columns([1, 1.6, 1])

    with c_center:
        st.markdown("<div class='saas-card' style='text-align: center; padding: 30px;'>", unsafe_allow_html=True)
        try:
            st.image("Company Logo.jpeg", use_container_width=True)
        except Exception:
            st.markdown("<h2 style='color: #184B9C; font-weight: 800; margin-bottom: 0;'>SIDHARTH SHUTTER</h2>", unsafe_allow_html=True)

        st.markdown("<p style='color: #64748B; font-weight: 600; font-size: 14px; margin-bottom: 25px;'>Enterprise CRM & Operations Portal</p>", unsafe_allow_html=True)

        with st.form("centered_login_form"):
            username_input = st.text_input("Username / Email", placeholder="e.g. admin, pooja, or albert").strip().lower()
            password_input = st.text_input("Password", type="password", placeholder="Enter account password").strip()

            submit_login = st.form_submit_button("LOGIN TO DASHBOARD")

            if submit_login:
                if login_user(db_adapter, username_input, password_input):
                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials. Try admin / admin123")

        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

user = get_current_user()
render_navbar(user)

user_name = user.get("name") or "User"
user_role = str(user.get("role", "LGE")).upper()

ROLE_DESCRIPTIONS = {
    "LGE": "Lead Generation Executive",
    "QS": "Quotation Specialist",
    "SAM": "Sales Account Manager",
    "ADMIN": "CRM Administrator",
    "OPERATIONS": "Operations Specialist"
}
role_display = ROLE_DESCRIPTIONS.get(user_role, user_role)
initials = "".join([p[0].upper() for p in user_name.strip().split()[:2]]) if user_name else "U"

with st.sidebar:
    st.markdown("<div style='background-color: #FFFFFF; padding: 12px; border-radius: 12px; margin-bottom: 15px; text-align: center;'>", unsafe_allow_html=True)
    try:
        st.image("Company Logo.jpeg", use_container_width=True)
    except Exception:
        st.markdown("<h3 style='color:#184B9C; font-weight:800; margin:0;'>SIDHARTH SHUTTER</h3>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"""
        <div style='background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 12px; padding: 12px 14px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px;'>
            <div style='background: linear-gradient(135deg, #00A859 0%, #008F4C 100%); color: #FFFFFF; font-weight: 800; font-size: 15px; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0;'>
                {initials}
            </div>
            <div>
                <div style='color: #FFFFFF; font-size: 14.5px; font-weight: 700;'>{user_name}</div>
                <div style='color: #00A859; font-size: 11px; font-weight: 700; text-transform: uppercase;'>{role_display}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    available_views = {}
    if user_role in ["ADMIN", "ADMINISTRATOR"]:
        available_views["🛡️ Admin Control Center"] = render_admin_portal
        available_views["👥 User Management"] = render_user_management
        available_views["📥 Lead Generation Portal"] = render_lead_portal
        available_views["📈 Performance & Progress Control"] = render_qs_performance_dashboard
        available_views["📄 Quotation Generator & Convert"] = render_qs_generator_and_claim
        available_views["📝 Detailed Quotation Form Entry"] = render_qs_detailed_form_entry
        available_views["⚡ Follow-up Queue & Workday"] = render_qs_followup_workday
        available_views["💼 Sales Management Portal"] = render_sales_portal
        available_views["⚙️ Order Fulfillment"] = render_process_portal
        available_views["🔍 Client Inspector"] = render_client_inspector
        available_views["📊 Employee Report Card"] = render_employee_report

    elif user_role in ["QS"]:
        # EXPANDED NAVIGATION FOR QUOTATION SPECIALISTS
        available_views["📈 Performance & Progress Control"] = render_qs_performance_dashboard
        available_views["📄 Quotation Generator & Convert"] = render_qs_generator_and_claim
        available_views["📝 Detailed Quotation Form Entry"] = render_qs_detailed_form_entry
        available_views["⚡ Follow-up Queue & Workday"] = render_qs_followup_workday
        available_views["📥 Add New Lead"] = render_lead_portal
        available_views["🔍 Client Inspector"] = render_client_inspector

    elif user_role in ["LGE"]:
        available_views["📥 Lead Generation Portal"] = render_lead_portal
        available_views["⚡ Follow-up Queue & Workday"] = render_qs_followup_workday
        available_views["🔍 Client Inspector"] = render_client_inspector

    elif user_role in ["SAM"]:
        available_views["💼 Sales Management Portal"] = render_sales_portal
        available_views["🔍 Client Inspector"] = render_client_inspector

    elif user_role in ["OPERATIONS"]:
        available_views["⚙️ Order Fulfillment"] = render_process_portal
        available_views["🔍 Client Inspector"] = render_client_inspector

    else:
        available_views["🛡️ Admin Control Center"] = render_admin_portal

    selected_view_name = st.sidebar.radio("WORKSPACE NAVIGATION", list(available_views.keys()))

    st.markdown("<br><hr style='border:none; border-top:1px solid rgba(255,255,255,0.15); margin-bottom: 12px;'>", unsafe_allow_html=True)

    if st.sidebar.button("🚪 Logout", use_container_width=True, key="single_app_logout_btn"):
        logout_user()
        st.rerun()

if selected_view_name in available_views:
    available_views[selected_view_name](db_adapter, user)