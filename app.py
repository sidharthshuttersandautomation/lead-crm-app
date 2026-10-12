import streamlit as st
from database.gsheets_adapter import GSheetsAdapter
from utils.auth import init_session_auth, login_user, logout_user
from components.navbar import render_navbar

import sys
import os

# Add project root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# View Imports
from views.lead_portal import render_lead_portal
from views.quotation_portal import render_quotation_portal
from views.sales_portal import render_sales_portal
from views.process_portal import render_process_portal
from views.admin_portal import render_admin_portal
from views.notification_center import render_notification_center

st.set_page_config(
    page_title="Sidharth Lead CRM",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_session_auth()
db_adapter = GSheetsAdapter()

if not st.session_state["authenticated"]:
    st.title("Sidharth Shutter & Automation CRM")
    st.subheader("System Login")
    
    with st.form("login_form"):
        email = st.text_input("User Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")
        
        if submitted:
            if login_user(db_adapter, email, password):
                st.success("Login Successful!")
                st.rerun()
            else:
                st.error("Invalid credentials. Try admin@sidharth.com / admin123")
else:
    user = st.session_state["user"]
    render_navbar(user["role"])
    
    # Sidebar Navigation based on Role Capabilities
    st.sidebar.markdown(f"### Logged in as: **{user['full_name']}**")
    
    available_views = []
    if user["role"] == "Admin":
        available_views = ["Admin Portal", "Lead Portal", "Quotation Portal", "Sales Portal", "Process Portal", "Notifications"]
    elif user["role"] == "Lead Executive":
        available_views = ["Lead Portal", "Notifications"]
    elif user["role"] == "Quotation Specialist":
        available_views = ["Quotation Portal", "Notifications"]
    elif user["role"] == "Sales Manager":
        available_views = ["Sales Portal", "Process Portal", "Notifications"]

    selected_view = st.sidebar.radio("Navigate Workspace", available_views)
    
    if st.sidebar.button("Logout"):
        logout_user()

    # View Routing Engine
    if selected_view == "Lead Portal":
        render_lead_portal(db_adapter, user)
    elif selected_view == "Quotation Portal":
        render_quotation_portal(db_adapter, user)
    elif selected_view == "Sales Portal":
        render_sales_portal(db_adapter, user)
    elif selected_view == "Process Portal":
        render_process_portal(db_adapter, user)
    elif selected_view == "Admin Portal":
        render_admin_portal(db_adapter, user)
    elif selected_view == "Notifications":
        render_notification_center(db_adapter, user)