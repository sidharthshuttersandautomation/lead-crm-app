import streamlit as st
from database.gsheets_adapter import GSheetsAdapter
from utils.auth import init_session_auth, get_current_user, login_user, logout_user
from components.navbar import render_navbar

<<<<<<< HEAD
=======
import sys
import os

# Add project root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# View Imports
>>>>>>> 3fc4091 (__init__ files)
from views.lead_portal import render_lead_portal
from views.quotation_portal import render_quotation_portal
from views.sales_portal import render_sales_portal
from views.process_portal import render_process_portal
from views.admin_portal import render_admin_portal
from views.notification_center import render_notification_center

st.set_page_config(
    page_title="Sidharth Shutter CRM",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

db = GSheetsAdapter()
init_session_auth()

if not st.session_state.get("authenticated", False):
    st.title("🔒 Sidharth Shutter CRM - Portal Login")
    df_users = db.fetch_all("users")

    if not df_users.empty:
        selected_name = st.selectbox("Select Profile", df_users["full_name"].tolist())
        selected_user = df_users[df_users["full_name"] == selected_name].iloc[0]
        st.info(f"Role: **{selected_user.get('role')}** | Email: {selected_user.get('email')}")

        if st.button("Enter Portal"):
            login_user(db, selected_user.get("full_name"), selected_user.get("role"))
            st.rerun()
    else:
        if st.button("Login as Admin"):
            login_user(db, "Admin User", "ADMIN")
            st.rerun()
    st.stop()

current_user = get_current_user()
render_navbar(current_user)

st.sidebar.title("📌 Navigation")
user_role = current_user.get("role")
available_views = {}

if user_role == "LGE":
    available_views["📥 Lead Generation Portal"] = render_lead_portal
elif user_role == "QS":
    available_views["📝 Quotation Desk Portal"] = render_quotation_portal
elif user_role == "SAM":
    available_views["💼 Sales Management Portal"] = render_sales_portal
elif user_role == "ADMIN":
    available_views["📥 Lead Generation Portal"] = render_lead_portal
    available_views["📝 Quotation Desk Portal"] = render_quotation_portal
    available_views["💼 Sales Management Portal"] = render_sales_portal
    available_views["⚙️ Fulfillment Tracker"] = render_process_portal
    available_views["🛡️ Admin Control Center"] = render_admin_portal

available_views["⚙️ Order Fulfillment"] = render_process_portal
available_views["🔔 Notification Center"] = render_notification_center

selected_view_name = st.sidebar.radio("Select Portal View", list(available_views.keys()))

st.sidebar.divider()
if st.sidebar.button("🚪 Logout"):
    logout_user()
    st.rerun()

available_views[selected_view_name](db, current_user)