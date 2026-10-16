"""
utils/excel_import.py - Load the company's existing lead workbook into the CRM.

Reads the sheets used before the CRM ("Leads Data", "Quotation Sheet",
"Quotation Follow Up Tracker", "Process Order"), cleans the values and maps
them onto the CRM tables. Nothing is written until the whole file has been
converted, and every assumption is listed in the returned report.
"""
import datetime
import difflib
import re
import secrets

import pandas as pd

from config.settings import CANCEL_CATEGORY_OPTIONS, QUOTE_COMPANIES
from utils.security import hash_password
from utils.sla_calculator import evaluate_sla
from utils.time_utils import IST, financial_year, now_str

SHEETS = {"leads": "Leads Data", "quotes": "Quotation Sheet",
          "followups": "Quotation Follow Up Tracker", "orders": "Process Order"}

SOURCE_MAP = {"whats app": "WhatsApp", "whatsapp": "WhatsApp", "india mart": "IndiaMart", "indiamart": "IndiaMart",
              "enquiry email": "Enquiry Email", "sales email": "Sales Email", "phone call": "Phone Call",
              "marketing team": "Marketing Team", "reference": "Reference", "direct visit": "Direct Visit"}

# Follow Up Status in the tracker -> CRM lead stage
STAGE_MAP = {"under discussion": "In Discussion", "call back": "CallBack", "callback": "CallBack",
             "call not received": "Not Responed", "not responded": "Not Responed", "not responed": "Not Responed",
             "cancel": "Cancled", "cancelled": "Cancled", "cancled": "Cancled", "lost": "Cancled",
             "under finalisation": "Under Finalization", "under finalization": "Under Finalization",
             "pending": "In Discussion", "done": "Done", "won": "Done"}

STATE_MAP = {"maharastra": "Maharashtra", "maharatra": "Maharashtra", "mahartra": "Maharashtra",
             "maharashtra": "Maharashtra", "up": "Uttar Pradesh", "mp": "Madhya Pradesh", "ap": "Andhra Pradesh",
             "tamilnadu": "Tamil Nadu", "tamil nadu": "Tamil Nadu", "hydrabad": "Telangana", "surat": "Gujarat"}

# Remarks on leads that never got a quotation which clearly mean the lead is closed.
LOST_REMARK_RULES = [
    (r"dont provide|don't provide|do not provide", "Technical Mismatch"),
    (r"want from local|from local", "Location Issue"),
    (r"already bought", "Competitor Won"),
    (r"number is not perfect|wrong number", "No Response"),
]

BLANKS = {"", "-", "--", "nan", "none", "nat", "na", "n/a"}


# ------------------------------------------------------------------ cleaning helpers
def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = " ".join(str(v).split())
    return None if s.lower() in BLANKS else s


def _num(v):
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _ts(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        t = pd.to_datetime(v)
        return None if pd.isna(t) else t.to_pydatetime().replace(microsecond=0, tzinfo=None)
    except Exception:
        return None


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _phone(v):
    s = _clean(v)
    if not s:
        return None
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits or None


def _title(v):
    s = _clean(v)
    return s.title() if s and (s.islower() or s.isupper()) else s


def _read(xls, name, id_col="Client ID"):
    df = pd.read_excel(xls, name)
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    if id_col not in df.columns:
        raise ValueError(f"Sheet '{name}' has no '{id_col}' column.")
    df[id_col] = df[id_col].map(_clean)
    return df[df[id_col].notna()].copy()


# ------------------------------------------------------------------ people
class PeopleMatcher:
    """Matches names written in the sheets ('Albert', 'Ajali', 'Man Singh Rathore')
    to employees, and creates the people who are not in the CRM yet."""

    def __init__(self, employees: pd.DataFrame):
        self.by_id = {}
        self.names = {}
        for _, e in employees.iterrows():
            self._add(e["employee_id"], e["full_name"])
        self.new_people = []   # (employee_id, name) created by the import
        self.aliases = {}      # sheet text -> employee name (for the report)

    @staticmethod
    def _key(name):
        return re.sub(r"[^a-z]", "", str(name).lower())

    def _add(self, emp_id, name):
        self.by_id[emp_id] = name
        self.names[self._key(name)] = emp_id

    def match(self, raw, next_id_fn, role="SAM"):
        name = _clean(raw)
        if not name:
            return None
        key = self._key(name)
        if key in self.names:
            emp = self.names[key]
        else:
            first = {self._key(n.split()[0]): i for i, n in self.by_id.items()}
            firsts = [i for k, i in first.items() if k == key]
            if len(firsts) == 1:
                emp = firsts[0]
            else:
                close = difflib.get_close_matches(key, list(self.names.keys()) + list(first.keys()), n=1, cutoff=0.82)
                emp = (self.names.get(close[0]) or first.get(close[0])) if close else None
            if emp is None:
                emp = next_id_fn(len(self.new_people))
                self._add(emp, name)
                self.new_people.append((emp, name, role))
        if self.by_id[emp] != name:
            self.aliases[name] = self.by_id[emp]
        return emp


# ------------------------------------------------------------------ main
def convert_workbook(file, db) -> dict:
    """Converts the workbook into CRM rows without writing anything. Returns a plan."""
    xls = pd.ExcelFile(file)
    missing = [s for s in (SHEETS["leads"],) if s not in xls.sheet_names]
    if missing:
        raise ValueError(f"The file has no '{missing[0]}' sheet. Sheets found: {', '.join(xls.sheet_names)}")

    leads = _read(xls, SHEETS["leads"])
    quotes = _read(xls, SHEETS["quotes"]) if SHEETS["quotes"] in xls.sheet_names else pd.DataFrame()
    fups = _read(xls, SHEETS["followups"]) if SHEETS["followups"] in xls.sheet_names else pd.DataFrame()
    orders = _read(xls, SHEETS["orders"]) if SHEETS["orders"] in xls.sheet_names else pd.DataFrame()

    notes, warnings = [], []
    stamp = now_str()
    data_end = None

    employees = db.fetch_all("employees")
    base_emp = max([int(m.group(1)) for m in employees["employee_id"].astype(str).map(lambda v: re.match(r"EMP-(\d+)$", v)) if m] + [100])
    people = PeopleMatcher(employees)
    new_emp_id = lambda i: f"EMP-{base_emp + 1 + i}"

    products = db.fetch_all("products")
    product_ids = {str(n).lower(): int(i) for n, i in zip(products["product_name"], products["product_id"])}
    new_products = []

    def product_id(name):
        key = name.lower()
        if key not in product_ids:
            product_ids[key] = None
            new_products.append(name)
        return key

    q_by_id = {r["Client ID"]: r for _, r in quotes.iterrows()} if not quotes.empty else {}
    f_by_id = {r["Client ID"]: r for _, r in fups.iterrows()} if not fups.empty else {}
    o_by_id = {r["Client ID"]: r for _, r in orders.iterrows()} if not orders.empty else {}

    customers_rows, lead_rows, quote_rows, log_rows, order_rows = [], [], [], [], []
    seen = set()
    lost_by_remark = won = 0
    missing_amount = []

    for _, r in leads.iterrows():
        cid = r["Client ID"]
        if cid in seen:
            warnings.append(f"{cid}: duplicate row in Leads Data, kept the first one.")
            continue
        seen.add(cid)
        q, f, o = q_by_id.get(cid), f_by_id.get(cid), o_by_id.get(cid)

        received = _ts(r.get("Date Stamp")) or _ts(q.get("Date Stamp") if q is not None else None)
        if received is None:
            warnings.append(f"{cid}: no date stamp, used today.")
            received = datetime.datetime.now(IST).replace(tzinfo=None, microsecond=0)
        data_end = max(data_end or received, received)

        name = _clean(r.get("Client Name")) or (_clean(q.get("Client Name")) if q is not None else None)
        company = _clean(r.get("Company Name"))
        phone = _phone(r.get("Number")) or (_phone(q.get("Customer Contact Number")) if q is not None else None)
        if not phone:
            warnings.append(f"{cid}: no phone number.")
        elif len(phone) < 10:
            warnings.append(f"{cid}: phone '{phone}' is shorter than 10 digits.")
        city = _title(r.get("City")) or (_title(q.get("City")) if q is not None else None) or "Unknown"
        state_raw = _clean(r.get("State"))
        state = STATE_MAP.get(state_raw.lower(), state_raw.title() if state_raw and state_raw.islower() else state_raw) if state_raw else None

        customers_rows.append({
            "client_id": cid, "client_name": name or company or "Unknown",
            "company_name": company, "phone_number": phone or "",
            "email": _clean(r.get("Email")), "address": _clean(r.get("Address")), "city": city,
            "state": state, "is_key_account": 0, "created_at": _fmt(received)})

        # product (first item when several are listed)
        product_raw = _clean(r.get("Product")) or (_clean(q.get("Product")) if q is not None else None) or "Spare Part"
        parts = [p.strip() for p in product_raw.split(",") if p.strip()]
        pkey = product_id(parts[0])
        remarks = [x for x in [_clean(r.get("Remarks"))] if x and x.lower() != "done"]
        if len(parts) > 1:
            remarks.append("Products: " + ", ".join(parts))

        source = SOURCE_MAP.get((_clean(r.get("Source")) or "").lower(), _clean(r.get("Source")) or "Phone Call")
        lge = people.match(r.get("Leads Handle By"), new_emp_id, role="LGE")
        sam = people.match(r.get("Assigned Salesperson"), new_emp_id, role="SAM")
        qs = people.match(r.get("Quotation Sent By"), new_emp_id, role="QS")
        followup_by = people.match(f.get("Quotation Follow Up by"), new_emp_id, role="SAM") if f is not None else None

        has_quote = q is not None or str(_clean(r.get("Quotation Status")) or "").lower() == "sent"
        after, due, _ = evaluate_sla(IST.localize(received))

        # stage
        stage, lost_reason = ("In Discussion" if has_quote else "Pending"), None
        fstatus = _clean(f.get("Follow Up Status")) if f is not None else None
        if fstatus:
            stage = STAGE_MAP.get(fstatus.lower(), stage)
        if str(_clean(r.get("Final Status")) or "").lower() in ("cancled", "cancelled", "canceled"):
            stage = "Cancled"
        if not has_quote:
            text = " ".join(remarks).lower()
            for pattern, reason in LOST_REMARK_RULES:
                if re.search(pattern, text):
                    stage, lost_reason = "Cancled", reason
                    lost_by_remark += 1
                    break
        if stage == "Cancled" and not lost_reason:
            cat = _clean(f.get("Cancel Category")) if f is not None else None
            lost_reason = cat if cat in CANCEL_CATEGORY_OPTIONS else None
        if o is not None:
            stage = "Done"
        won += stage == "Done"

        quote_dt = _ts(q.get("Date Stamp")) if q is not None else None
        fu_date = _ts(f.get("Follow Up Date")) if f is not None else None
        closed = stage in ("Done", "Cancled")
        next_call = None if closed or fu_date is None else fu_date.replace(hour=11, minute=0, second=0)
        owner = followup_by or qs or lge

        lead_rows.append({
            "_cid": cid, "_pkey": pkey,
            "client_id": cid, "quantity": int(_num(r.get("Qty")) or 1), "source": source,
            "type_of_client": ("Service" if str(_clean(r.get("Type of client")) or "").lower().startswith("serv")
                               or cid.startswith("SID") else "Buy"),
            "customer_responded": "No" if str(_clean(r.get("Customer Responed")) or "").lower().startswith("n") else "Yes",
            "final_status": stage, "quotation_status": "Sent" if has_quote else ("Under Process" if qs else "Not Sent"),
            "priority": "Normal", "remarks": " | ".join(remarks) or None,
            "handled_by_lge_id": lge, "assigned_sam_id": sam, "claimed_qs_id": qs,
            "followup_owner_id": owner, "next_followup_at": _fmt(next_call), "lost_reason": lost_reason,
            "ingestion_date": received.strftime("%Y-%m-%d"), "ingested_at": _fmt(received),
            "is_after_cutoff": int(after), "sla_due_date": str(due),
            "claimed_at": _fmt(quote_dt) if qs or has_quote else None,
            "quote_sent_at": _fmt(quote_dt or received) if has_quote else None,
            "closed_at": _fmt(fu_date or quote_dt or received) if closed else None,
            "updated_at": stamp,
        })

        # quotation
        if q is not None:
            amount = _num(q.get("Qut. Amount")) or _num(f.get("Qut. Amount") if f is not None else None)
            if amount is None:
                missing_amount.append(cid)
            number = _clean(q.get("Quotation Number")) or f"IMPORTED/{financial_year(received.date())}/{cid}"
            approved_by = people.match(q.get("Qut. Status Approved By"), new_emp_id) if _clean(q.get("Qut. Status Approved By")) else None
            quote_rows.append({
                "_cid": cid, "quotation_number": number, "revision_no": 0, "qut_amount": amount or 0.0,
                "gross_amount": amount or 0.0, "discount_percent": 0.0, "discount_amount": 0.0,
                "quotation_status": "Approved", "follow_up_required": "Yes",
                "claimed_qs_id": qs, "approved_by_id": approved_by, "shared_by_id": qs,
                "folder_link": _clean(q.get("Link")), "company_name_1": _clean(q.get("Company Name-1")) or number.split("/")[0],
                "approved_date": (quote_dt or received).strftime("%Y-%m-%d"),
                "approved_month": (quote_dt or received).strftime("%B %Y"),
                "revision_reason": None, "created_by": qs, "created_at": _fmt(quote_dt or received)})

        # follow-up calls: one log per ticked "Follow UP n" box
        if f is not None:
            ticks = sum(bool(f.get(f"Follow UP {i}")) and str(f.get(f"Follow UP {i}")).lower() not in ("false", "0", "0.0", "nan")
                        for i in range(1, 6))
            note = _clean(f.get("Notes"))
            if ticks == 0 and (note or fstatus):
                ticks = 1
            start = quote_dt or received
            end = fu_date if fu_date and fu_date > start else start + datetime.timedelta(days=ticks + 1)
            caller = followup_by or qs or lge
            for i in range(1, ticks + 1):
                at = start + (end - start) * i / (ticks + 1)
                last = i == ticks
                log_rows.append({
                    "_cid": cid, "employee_id": caller, "followup_sequence_no": i,
                    "followup_status": stage if last else "In Discussion",
                    "cancel_category": lost_reason if last and stage == "Cancled" else None,
                    "scheduled_call_time": _fmt(next_call) if last else None,
                    "notes": (note or f"Follow-up {i} (imported)") if last else f"Follow-up {i} (imported, no notes)",
                    "logged_at": _fmt(at.replace(microsecond=0))})

        # orders
        if o is not None:
            value = _num(o.get("Qut. Amount")) or (quote_rows[-1]["qut_amount"] if q is not None else 0.0)
            po = _clean(o.get("Purchase Order"))
            order_rows.append({
                "_cid": cid, "purchase_order_no": po[:-2] if po and po.endswith(".0") else po,
                "pi_amount": value or 0.0, "order_value": value or None,
                "payment_status": _clean(o.get("Payment Status")) or "Pending",
                "measurement_status": "Pending", "drawing_status": "Pending",
                "production_status": "Not Started", "dispatch_status": "Pending",
                "remarks": _clean(o.get("Remarks")), "created_by": None,
                "created_at": _fmt(_ts(o.get("Start Date")) or quote_dt or received)})
            if not value:
                warnings.append(f"{cid}: order has no amount; set the final order value in Order fulfilment.")

    # ---- report
    if people.new_people:
        notes.append("People found in the sheets but not in the CRM were added as INACTIVE accounts "
                     "(email = first name @sidharth.com). They can't sign in until an admin activates them in Users, "
                     "or you add them to Secrets with that email and sync_passwords = \"true\": "
                     + ", ".join(f"{n} ({i}, {r})" for i, n, r in people.new_people) + ".")
    if people.aliases:
        notes.append("Names matched to existing accounts: "
                     + ", ".join(f"'{a}' → {b}" for a, b in sorted(people.aliases.items())) + ".")
    if new_products:
        notes.append("New products added to the product list: " + ", ".join(new_products) + ".")
    if missing_amount:
        warnings.append(f"{len(missing_amount)} quotation(s) had no amount and were imported at ₹0: "
                        + ", ".join(missing_amount) + ". Add a revision with the real price.")
    notes.append("Leads Data 'Final Status = Done' means 'handled' in the old sheet, so the CRM stage comes from the "
                 "follow-up tracker (Under Discussion → In Discussion, Call Back → CallBack, Call Not Received → "
                 "Not Responed, Cancel → Cancled, Under Finalisation → Under Finalization, Done → Done).")
    if lost_by_remark:
        notes.append(f"{lost_by_remark} lead(s) without a quotation were marked Cancled because the remark says so "
                     "(e.g. 'we dont provide…' → Technical Mismatch, 'want from local' → Location Issue).")
    notes.append("Each ticked 'Follow UP n' box became one call log. The old sheet has no call dates, so calls are "
                 "spread evenly between the quotation date and the follow-up date; the last call carries the notes.")
    notes.append("Quotation amounts are imported as the final price with no discount (old sheet has no list price).")

    return {
        "customers": customers_rows, "leads": lead_rows, "quotes": quote_rows, "logs": log_rows,
        "orders": order_rows, "new_people": people.new_people, "new_products": new_products,
        "notes": notes, "warnings": warnings,
        "summary": {"Leads": len(lead_rows), "Quotations": len(quote_rows), "Follow-up calls": len(log_rows),
                    "Orders": len(order_rows), "Done": won,
                    "Cancled": sum(1 for x in lead_rows if x["final_status"] == "Cancled"),
                    "Open": sum(1 for x in lead_rows if x["final_status"] not in ("Done", "Cancled")),
                    "New accounts": len(people.new_people), "New products": len(new_products),
                    "Data up to": _fmt(data_end)},
    }


def apply_plan(db, plan: dict, replace_existing: bool) -> dict:
    """Writes a converted plan into the database. Returns counts per table."""
    result = {}
    if replace_existing:
        result["cleared"] = db.clear_lead_data()
    else:
        existing = set(db.fetch_all("customers")["client_id"]) if db.count_rows("customers") else set()
        clash = [c["client_id"] for c in plan["customers"] if c["client_id"] in existing]
        if clash:
            raise ValueError(f"{len(clash)} client ID(s) already exist (e.g. {', '.join(clash[:5])}). "
                             "Tick 'Replace existing lead data' to load the file into a clean database.")

    # people and products first
    stamp = now_str()
    taken = set(db.fetch_all("employees")["email"].str.lower())
    people_rows = []
    for i, n, r in plan["new_people"]:
        words = [re.sub(r"[^a-z]", "", w) for w in n.lower().split()]
        email = f"{words[0]}@sidharth.com"
        if email in taken:
            email = f"{'.'.join(words)}@sidharth.com"
        if email in taken:
            email = f"{'.'.join(words)}.{i.lower()}@sidharth.com"
        taken.add(email)
        people_rows.append({"employee_id": i, "full_name": n, "email": email,
                            "password_hash": hash_password(secrets.token_urlsafe(24)), "role": r,
                            "is_active": 0, "created_at": stamp})
    result["employees"] = db.bulk_insert("employees", people_rows) if people_rows else 0
    for name in plan["new_products"]:
        db.insert_row("products", {"product_name": name, "category": "Imported", "is_active": 1})
    products = db.fetch_all("products")
    pid = {str(n).lower(): int(i) for n, i in zip(products["product_name"], products["product_id"])}

    result["customers"] = db.bulk_insert("customers", plan["customers"])
    if result["customers"] != len(plan["customers"]):
        raise RuntimeError(db.last_error or "Customers could not be saved.")

    lead_rows = [{k: v for k, v in r.items() if not k.startswith("_")} | {"product_id": pid[r["_pkey"]]}
                 for r in plan["leads"]]
    result["leads_master"] = db.bulk_insert("leads_master", lead_rows)
    if result["leads_master"] != len(lead_rows):
        raise RuntimeError(db.last_error or "Leads could not be saved.")
    leads = db.fetch_all("leads_master")
    lead_id = dict(zip(leads["client_id"], leads["lead_id"]))

    start = db.next_quotation_id()
    n0 = int(start.split("-")[1])
    qrows, quote_id_by_cid = [], {}
    for i, r in enumerate(plan["quotes"]):
        qid = f"QUO-{n0 + i:04d}"
        quote_id_by_cid[r["_cid"]] = qid
        qrows.append({k: v for k, v in r.items() if not k.startswith("_")}
                     | {"quotation_id": qid, "lead_id": int(lead_id[r["_cid"]]), "client_id": r["_cid"]})
    result["quotations_master"] = db.bulk_insert("quotations_master", qrows)

    lrows = [{k: v for k, v in r.items() if not k.startswith("_")}
             | {"lead_id": int(lead_id[r["_cid"]]), "quotation_id": quote_id_by_cid.get(r["_cid"])}
             for r in plan["logs"]]
    result["followup_logs"] = db.bulk_insert("followup_logs", lrows)

    o0 = int(db.next_order_id().split("-")[1])
    orows = [{k: v for k, v in r.items() if not k.startswith("_")}
             | {"order_id": f"ORD-{o0 + i:04d}", "lead_id": int(lead_id[r["_cid"]]), "client_id": r["_cid"],
                "quotation_id": quote_id_by_cid.get(r["_cid"])}
             for i, r in enumerate(plan["orders"])]
    result["orders"] = db.bulk_insert("orders", orows)
    db.log_event("EXCEL_IMPORT", None, None, None, {k: v for k, v in result.items() if k != "cleared"})
    return result
