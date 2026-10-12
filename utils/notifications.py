import datetime

def get_scheduled_call_reminders(followup_df, current_user_name: str):
    """Find scheduled calls due for the logged in user."""
    if followup_df.empty:
        return []
    
    reminders = []
    user_calls = followup_df[
        (followup_df["quotation_follow_up_by"] == current_user_name) & 
        (followup_df["followup_status"] == "Under Discussion")
    ]
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    for _, row in user_calls.iterrows():
        call_time = str(row.get("scheduled_call_time", ""))
        if now_str in call_time:
            reminders.append({
                "client_id": row.get("client_id"),
                "scheduled_time": call_time,
                "notes": row.get("notes")
            })
    return reminders