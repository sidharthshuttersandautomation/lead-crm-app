import streamlit as st
from utils.notifications import get_user_reminders

def render_notification_center(db, current_user: dict):
    st.title("🔔 Centralized Alerts & Call Reminders Center")

    reminders = get_user_reminders(db, current_user)
    if not reminders:
        st.success("🎉 You have no pending alerts or call reminders!")
        return

    for item in reminders:
        sev = item.get("severity", "info")
        if sev == "error":
            st.error(f"**{item.get('title')}**\n\n{item.get('message')}")
        elif sev == "warning":
            st.warning(f"**{item.get('title')}**\n\n{item.get('message')}")
        else:
            st.info(f"**{item.get('title')}**\n\n{item.get('message')}")