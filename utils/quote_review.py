"""utils/quote_review.py - Salesperson decisions on quotations: approve, or send back for revision."""
from utils.time_utils import now_ist, now_str


def approve_quotation(db, quote, lead, user, next_call: str = None, note: str = None) -> bool:
    stamp = now_str()
    ok = db.update_row("quotations_master", "quotation_id", quote["quotation_id"], {
        "quotation_status": "Approved", "approved_by_id": user["employee_id"],
        "approved_date": stamp[:10], "approved_month": now_ist().strftime("%B %Y"),
        "revision_requested": 0, "review_note": note or None,
        "reviewed_by": user["employee_id"], "reviewed_at": stamp,
    })
    if not ok:
        return False
    current = lead.get("followup_owner_id")
    owner = current if current is not None and str(current) not in ("", "nan", "None") else \
        (lead.get("claimed_qs_id") or user["employee_id"])
    updates = {"quotation_status": "Sent", "followup_owner_id": owner, "updated_at": stamp}
    if next_call:
        updates["next_followup_at"] = next_call
    if not lead.get("quote_sent_at") or str(lead.get("quote_sent_at")) in ("nan", "None"):
        updates["quote_sent_at"] = stamp
    if lead.get("final_status") == "Pending":
        updates["final_status"] = "In Discussion"
    ok = db.update_row("leads_master", "lead_id", int(lead["lead_id"]), updates)
    if ok:
        db.log_event("QUOTE_APPROVED", "quotations_master", quote["quotation_id"], None,
                     {"by": user["employee_id"], "note": note})
    return ok


def request_revision(db, quote, lead, user, note: str) -> bool:
    """Sends the quotation back to the quotation team. The QS sees it on their desk and in Alerts."""
    stamp = now_str()
    updates = {"revision_requested": 1, "review_note": note, "reviewed_by": user["employee_id"], "reviewed_at": stamp}
    if quote.get("quotation_status") == "Under Review":
        updates["quotation_status"] = "Rejected"
    if not db.update_row("quotations_master", "quotation_id", quote["quotation_id"], updates):
        return False
    ok = db.update_row("leads_master", "lead_id", int(lead["lead_id"]),
                       {"quotation_status": "Under Process", "updated_at": stamp})
    if ok:
        db.log_event("REVISION_REQUESTED", "quotations_master", quote["quotation_id"], None,
                     {"by": user["employee_id"], "note": note})
    return ok
