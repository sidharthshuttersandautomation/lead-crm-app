from datetime import datetime

def get_user_reminders(db, user: dict) -> list[dict]:
    reminders = []
    user_role = user.get("role")
    user_name = user.get("name")

    # 1. Scheduled Call Alerts
    df_follow = db.fetch_all("followup_tracker")
    if not df_follow.empty and "scheduled_call_time" in df_follow.columns:
        now_str = datetime.now().strftime("%Y-%m-%d")
        todays_calls = df_follow[
            df_follow["scheduled_call_time"].astype(str).str.contains(now_str, na=False)
        ]

        if user_role == "SAM":
            todays_calls = todays_calls[
                todays_calls["quotation_follow_up_by"] == user_name
            ]

        for _, row in todays_calls.iterrows():
            reminders.append(
                {
                    "type": "CALL_REMINDER",
                    "title": f"Scheduled Call: Client {row.get('client_id')}",
                    "message": f"Follow-up scheduled for {row.get('scheduled_call_time')} | Notes: {row.get('notes', 'N/A')}",
                    "severity": "info",
                }
            )

    # 2. Quotation Desk Revisions & Overnight Queue Alerts
    if user_role in ["QS", "ADMIN"]:
        df_quotes = db.fetch_all("quotation_sheet")
        if not df_quotes.empty:
            pending = df_quotes[df_quotes["quotation_status"] == "Pending"]
            if user_role == "QS":
                pending = pending[
                    (pending["assigned_qs_id"] == user_name)
                    | (pending["assigned_qs_id"] == "")
                ]

            for _, row in pending.iterrows():
                rev = int(row.get("revised_count", 0))
                if rev > 0:
                    reminders.append(
                        {
                            "type": "REVISION_ALERT",
                            "title": f"REVISION #{rev}: Client {row.get('client_id')}",
                            "message": f"Revision requested by {row.get('quotation_shared_by', 'SAM')}",
                            "severity": "warning",
                        }
                    )
                elif row.get("is_after_cutoff"):
                    reminders.append(
                        {
                            "type": "OVERNIGHT_SLA",
                            "title": f"Overnight Queue: Client {row.get('client_id')}",
                            "message": f"Submitted after 5:30 PM. Target: {row.get('target_completion_date')}",
                            "severity": "error",
                        }
                    )

    return reminders