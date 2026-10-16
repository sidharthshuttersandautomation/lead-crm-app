"""views/account.py - Change your own password."""
import streamlit as st

from utils.security import hash_password, password_problem, verify_password


def render_account(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>My account</h2>", unsafe_allow_html=True)
    st.write(f"**{current_user['name']}** · {current_user['email']} · {current_user['employee_id']}")

    with st.form("change_password", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Repeat new password", type="password")
        if st.form_submit_button("Change password"):
            record = db_adapter.get_login_record(current_user["employee_id"])
            if not record or not verify_password(current, record["password_hash"]):
                st.error("Current password is incorrect.")
            elif new != confirm:
                st.error("The new passwords don't match.")
            elif password_problem(new):
                st.error(password_problem(new))
            elif db_adapter.update_row("employees", "employee_id", current_user["employee_id"],
                                       {"password_hash": hash_password(new)}):
                st.success("Password changed. Use it next time you sign in.")
            else:
                st.error(db_adapter.last_error)

    st.markdown("##### Desktop alerts")
    st.markdown(
        "- Click **🔔 Turn on desktop alerts** in the menu and choose **Allow**. Do this once on each computer and browser.\n"
        "- Call reminders then pop up on screen 2 minutes before each call, even if you're working in another "
        "program. They stay until you click or close them. If a call is still not logged 10 minutes after its time, "
        "a second alert appears.\n"
        "- Keep one CRM tab open (it can be in the background). A closed tab can't send alerts.\n"
        "- In Chrome or Edge, if alerts arrive late: Settings → Performance → Memory saver → "
        "**Always keep these sites active** → add the CRM address.\n"
        "- On Windows, also check Settings → System → Notifications → your browser is On, and Focus assist / "
        "Do not disturb is off.")
