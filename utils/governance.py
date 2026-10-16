"""utils/governance.py - Reassignment and priority changes (always audited)."""
from utils.time_utils import now_str

FIELDS = {
    "QS": "claimed_qs_id",
    "SAM": "assigned_sam_id",
    "FOLLOWUP": "followup_owner_id",
}


def reassign_leads(db, leads, target: str, new_emp_id: str, reason: str):
    """
    Move leads to another employee.
      target "QS"       -> quotation specialist (open follow-ups move with it)
      target "SAM"      -> salesperson
      target "FOLLOWUP" -> who makes the next call
    Returns (moved_count, errors).
    """
    field = FIELDS[target]
    moved, errors = 0, []
    for _, lead in leads.iterrows():
        old = lead.get(field)
        old = None if old is None or str(old) == "nan" else old
        if old == new_emp_id:
            continue
        updates = {field: new_emp_id, "updated_at": now_str()}
        if target == "QS":
            if lead.get("quotation_status") == "Not Sent":
                updates["quotation_status"] = "Under Process"
            if not lead.get("claimed_at") or str(lead.get("claimed_at")) == "nan":
                updates["claimed_at"] = now_str()
            if lead.get("followup_owner_id") in (old, None) or str(lead.get("followup_owner_id")) == "nan" \
                    or lead.get("quotation_status") == "Sent":
                updates["followup_owner_id"] = new_emp_id
        if db.update_row("leads_master", "lead_id", int(lead["lead_id"]), updates):
            db.log_event("REASSIGN", "leads_master", int(lead["lead_id"]),
                         {field: None if str(old) == "nan" else old}, {field: new_emp_id, "reason": reason})
            moved += 1
        else:
            errors.append(f"{lead['client_id']}: {db.last_error}")
    return moved, errors


def set_priority(db, leads, priority: str, reason: str):
    changed = 0
    for _, lead in leads.iterrows():
        if lead.get("priority") == priority:
            continue
        if db.update_row("leads_master", "lead_id", int(lead["lead_id"]),
                         {"priority": priority, "updated_at": now_str()}):
            db.log_event("PRIORITY", "leads_master", int(lead["lead_id"]),
                         {"priority": lead.get("priority")}, {"priority": priority, "reason": reason})
            changed += 1
    return changed
