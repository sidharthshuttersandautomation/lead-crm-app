"""utils/notifications.py - What needs the signed-in user's attention right now."""
import pandas as pd

from config.settings import APPROVER_ROLES, COLLECTION_ROLES
from utils.metrics import call_bucket, latest_quotes, open_leads
from utils.queues import call_queue
from utils.time_utils import today_ist


def collect_alerts(db, user: dict, owner_filter: str = None) -> dict:
    """
    Returns dataframes keyed by alert type. owner_filter: employee_id (admin view
    of one person), or None = the signed-in user (admins: everyone).
    """
    role, emp_id = user.get("role"), user.get("employee_id")
    is_admin = role == "ADMIN"
    who = owner_filter or (None if is_admin else emp_id)
    empty = pd.DataFrame()
    out = {k: empty for k in ("overdue", "today", "my_tickets", "unclaimed", "approvals", "revisions",
                              "collect_overdue", "collect_today", "deliveries", "verify")}

    leads = db.fetch_all("leads_master")
    if not leads.empty:
        active = open_leads(leads)
        mine = call_queue(leads, user, owner_filter)
        if not mine.empty:
            buckets = mine["next_followup_at"].map(call_bucket)
            out["overdue"] = mine[buckets == "overdue"]
            out["today"] = mine[buckets == "today"]
        if role in ("QS", "ADMIN"):
            pending = active[active["quotation_status"] != "Sent"]
            qs = who if who else None
            out["my_tickets"] = pending[pending["claimed_qs_id"] == qs] if qs else pending[pending["claimed_qs_id"].notna()]
            out["unclaimed"] = pending[pending["claimed_qs_id"].isna()]

    lq = latest_quotes(db.fetch_all("quotations_master")) if role in APPROVER_ROLES + ["QS"] else pd.DataFrame()
    if role in ("QS", "ADMIN") and not lq.empty:
        back = lq[((lq["revision_requested"] == 1) | (lq["quotation_status"] == "Rejected"))
                  & ~lq["final_status"].isin(["Done", "Cancled"])]
        if role == "QS":
            back = back[back["claimed_qs_id"] == emp_id]
        elif who:
            back = back[back["claimed_qs_id"] == who]
        out["revisions"] = back
    if role in APPROVER_ROLES:
        if not lq.empty:
            waiting = lq[(lq["quotation_status"] == "Under Review") & ~lq["final_status"].isin(["Done", "Cancled"])]
            if role == "SAM":
                waiting = waiting[waiting["assigned_sam_id"] == emp_id]
            elif who:
                waiting = waiting[waiting["assigned_sam_id"] == who]
            out["approvals"] = waiting

    from views.po_portal import can_use_po
    if can_use_po(user):
        from utils.payment_plan import payment_alerts
        orders = db.fetch_all("orders")
        mine = None if role == "ADMIN" and not owner_filter else (owner_filter or emp_id)
        pa = payment_alerts(orders, mine)
        out["collect_overdue"], out["collect_today"] = pa["calls_overdue"], pa["calls_today"]
        out["deliveries"], out["verify"] = pa["deliveries"], pa["verify"]
    return out


def alert_badge_counts(db, user: dict) -> tuple:
    """(follow-up alerts, quotation alerts, collection alerts) for the sidebar badges."""
    a = collect_alerts(db, user)
    follow = len(a["overdue"]) + len(a["today"])
    quote = len(a["approvals"]) + len(a["revisions"]) + (len(a["my_tickets"]) + len(a["unclaimed"]) if user.get("role") == "QS" else 0)
    collect = len(a["collect_overdue"]) + len(a["collect_today"]) + len(a["deliveries"]) + len(a["verify"])
    return follow, quote, collect
