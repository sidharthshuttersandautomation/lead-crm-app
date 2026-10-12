import streamlit as st
from utils.notifications import get_scheduled_call_reminders

def render_notification_center(db_adapter, user):
    st.title(" Centralized Alerts & Reminders Center")
    
    f_df = db_adapter.fetch_table("followup_tracker")
    reminders = get_scheduled_call_reminders(f_df, user["full_name"])
    
    if reminders:
        st.subheader(" Scheduled Call Alerts")
        for rem in reminders:
            st.warning(f"**Call Scheduled!** Client ID: `{rem['client_id']}` at `{rem['scheduled_time']}`. Note: {rem['notes']}")
    else:
        st.info("No active call reminders scheduled for today.")