"""utils/queues.py - Who sees which leads."""
import pandas as pd

from utils.metrics import open_leads


def my_clients(df_leads: pd.DataFrame, user: dict) -> pd.DataFrame:
    """Salesperson: leads assigned to them or whose calls they own. Others: unchanged."""
    if df_leads.empty or user.get("role") != "SAM":
        return df_leads
    me = user["employee_id"]
    return df_leads[(df_leads["assigned_sam_id"] == me) | (df_leads["followup_owner_id"] == me)]


def call_queue(df_leads: pd.DataFrame, user: dict, owner: str = None) -> pd.DataFrame:
    """
    Open leads whose follow-up calls this user should see.
      SAM   -> calls of their own clients (assigned to them, or owned by them)
      ADMIN -> everyone, or one person when `owner` is given
      other -> calls they own
    """
    active = open_leads(df_leads)
    if active.empty:
        return active
    role, me = user.get("role"), user.get("employee_id")
    if role == "ADMIN":
        return active if owner is None else active[(active["followup_owner_id"] == owner) |
                                                   (active["assigned_sam_id"] == owner)]
    if role == "SAM":
        return my_clients(active, user)
    return active[active["followup_owner_id"] == me]
