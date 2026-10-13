"""
Sequential Dynamic Client ID Generator starting at integer 1.
"""
import datetime
import pandas as pd

def get_next_sequential_id(df_leads: pd.DataFrame) -> int:
    if df_leads.empty:
        return 1
    if "client_id" in df_leads.columns:
        return len(df_leads) + 1
    return 1

def generate_client_id(client_type: str, date_obj: datetime.date, df_leads: pd.DataFrame) -> str:
    clean_type = str(client_type).strip()
    prefix = "BID" if clean_type == "New Buy" else ("SID" if clean_type == "Service" else "BID")
    month_str = date_obj.strftime("%b-%y")

    count = 1
    if not df_leads.empty and "type_of_client" in df_leads.columns:
        matching = df_leads[df_leads["type_of_client"].astype(str).str.strip() == clean_type]
        count = len(matching) + 1

    return f"{prefix}-{month_str}-{count:03d}"