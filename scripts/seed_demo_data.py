"""
scripts/seed_demo_data.py - Demo employees and two weeks of sample leads for testing.

Never run this against real data. It refuses if any leads already exist.

    python scripts/seed_demo_data.py --password "Demo@2026"

On Streamlit Cloud it runs automatically when [bootstrap] seed_demo_data = "true"
and the database has no leads.
"""
import argparse
import datetime
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import utils.compat  # noqa: F401,E402
from config.settings import CANCEL_CATEGORY_OPTIONS, IST, SOURCE_OPTIONS  # noqa: E402
from utils.security import hash_password  # noqa: E402
from utils.sla_calculator import evaluate_sla  # noqa: E402

DEMO_EMPLOYEES = [
    ("EMP-101", "Albert Singh", "albert@sidharth.com", "LGE"),
    ("EMP-102", "Pooja", "pooja@sidharth.com", "QS"),
    ("EMP-103", "Anjali", "anjali@sidharth.com", "QS"),
    ("EMP-104", "Dolly", "dolly@sidharth.com", "QS"),
    ("EMP-105", "Jeevan Sharma", "jeevan@sidharth.com", "SAM"),
    ("EMP-106", "Jitendra Sharma", "jitendra@sidharth.com", "SAM"),
    ("EMP-107", "Deepak Sethiya", "deepak@sidharth.com", "SAM"),
    ("EMP-108", "Ravi Operations", "ravi@sidharth.com", "OPERATIONS"),
    ("EMP-109", "Meena Accounts", "meena@sidharth.com", "ACCOUNTS"),
    ("EMP-110", "PO Desk", "po@sidharth.com", "PO"),
    ("EMP-111", "Kirti", "kirti@sidharth.com", "PO"),
]
FIRST = ["Rajesh", "Vikram", "Sanjay", "Anil", "Amit", "Pankaj", "Rohan", "Sunil", "Manish", "Naresh", "Neeraj", "Gaurav"]
LAST = ["Sharma", "Verma", "Gupta", "Patel", "Jain", "Mehta", "Agarwal", "Chawla", "Bhatia", "Joshi", "Reddy", "Rao"]
COMPANIES = ["Insolation Green Energy Pvt Ltd", "Blue Cold Reftech", "Apex Logistics", "Godrej Cold Storage",
             "Kirloskar Engineering", "Malwa Warehousing", "Indore Agro Foods", "Pithampur Auto Parts"]
CITIES = [("Indore", "Madhya Pradesh"), ("Bhopal", "Madhya Pradesh"), ("Pune", "Maharashtra"),
          ("Ahmedabad", "Gujarat"), ("Jaipur", "Rajasthan"), ("Dewas", "Madhya Pradesh")]


def seed_demo_data(db, demo_password=None, days=45, total=50):
    if db.count_rows("leads_master") > 0:
        print("Leads already exist. Demo data was NOT loaded.")
        return False
    db.set_actor("SYSTEM")
    rnd = random.Random(26)
    stamp = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    def by_role(role):
        emp = db.fetch_all("employees")
        return [] if emp.empty else emp[(emp["role"] == role) & (emp["is_active"] == 1)]["employee_id"].tolist()

    if not (by_role("QS") and by_role("SAM") and (by_role("LGE") or by_role("ADMIN"))):
        if not demo_password:
            print("No QS/SAM accounts and no demo password; demo data was NOT loaded.")
            return False
        pw_hash = hash_password(demo_password)
        from utils.people import name_key
        emp = db.fetch_all("employees")
        by_name = {name_key(n): i for n, i in zip(emp["full_name"], emp["employee_id"])} if not emp.empty else {}
        for _id, name, email, role in DEMO_EMPLOYEES:
            if name_key(name) in by_name:      # e.g. a salesperson record without a login
                db.update_row("employees", "employee_id", by_name[name_key(name)],
                              {"password_hash": pw_hash, "role": role, "is_active": 1})
            else:
                db.insert_row("employees", {"employee_id": db.next_employee_id(), "full_name": name, "email": email,
                                            "password_hash": pw_hash, "role": role, "is_active": 1,
                                            "created_at": stamp})
    qs_ids, sam_ids = by_role("QS"), by_role("SAM")
    lge_id = (by_role("LGE") or by_role("ADMIN"))[0]
    acc_id = (by_role("ACCOUNTS") or by_role("ADMIN") or [None])[0]
    po_id = (by_role("PO") or by_role("ADMIN") or [None])[0]
    ops_id = (by_role("OPERATIONS") or by_role("ADMIN") or [None])[0]

    products = db.fetch_all("products")
    product_ids = products["product_id"].tolist()
    today = datetime.datetime.now(IST).replace(tzinfo=None)
    n = 0

    # exactly `total` leads spread over the last `days` days (more of them recently)
    offsets = sorted((min(days, int(rnd.expovariate(1 / 16))) for _ in range(total)), reverse=True)
    adders = (by_role("LGE") or [lge_id]) * 4 + by_role("QS")       # mostly lead executives, some specialists
    po_team = by_role("PO") or [po_id]
    terms_pool = [(50, 40, 10), (50, 40, 10), (100, 0, 0), (60, 30, 10), (20, 70, 10), (10, 80, 10), (30, 60, 10)]
    for offset in offsets:
        day = (today - datetime.timedelta(days=offset)).date()
        for _ in range(1):
            n += 1
            received = datetime.datetime.combine(day, datetime.time(rnd.randint(9, 19), rnd.choice([0, 15, 30, 45])))
            if received > today:
                received = today - datetime.timedelta(minutes=30 * n % 300)
            r_str = received.strftime("%Y-%m-%d %H:%M:%S")
            after, due, _ = evaluate_sla(IST.localize(received))
            client_id = db.next_client_id("BID", received.strftime("%b-%y"))
            company = rnd.choice(COMPANIES)
            city, state = rnd.choice(CITIES)
            db.insert_row("customers", {
                "client_id": client_id, "client_name": f"Mr {rnd.choice(FIRST)} {rnd.choice(LAST)}",
                "company_name": company, "phone_number": f"9{rnd.randint(100000000, 999999999)}",
                "email": None, "address": f"{rnd.randint(10, 500)} Industrial Area", "city": city,
                "state": state, "is_key_account": int(n % 9 == 0), "created_at": r_str})

            # Lifecycle stage for this demo lead
            age = offset
            roll = rnd.random()
            if age == 0 and roll < 0.6:
                stage = "unclaimed"
            elif age <= 1 and roll < 0.4:
                stage = "claimed"
            elif roll < 0.12:
                stage = "review"
            elif roll < 0.45 and age > 3:
                stage = "won"
            elif roll < 0.60 and age > 3:
                stage = "lost"
            else:
                stage = "sent"

            sam = rnd.choice(sam_ids) if rnd.random() > 0.08 else None   # a few leads still need a salesperson
            qs = None if stage == "unclaimed" else rnd.choice(qs_ids)
            claimed_at = (received + datetime.timedelta(minutes=rnd.randint(20, 240))) if qs else None
            if claimed_at and claimed_at > today:
                claimed_at = today
            lead_id = db.insert_row("leads_master", {
                "client_id": client_id, "product_id": int(rnd.choice(product_ids)),
                "quantity": rnd.randint(1, 6), "source": rnd.choice(SOURCE_OPTIONS),
                "type_of_client": "Buy", "final_status": "Pending", "quotation_status": "Not Sent",
                "priority": "High" if n % 9 == 0 else "Normal",
                "remarks": "Demo lead", "handled_by_lge_id": rnd.choice(adders), "assigned_sam_id": sam,
                "claimed_qs_id": qs, "followup_owner_id": lge_id,
                "customer_responded": rnd.choice(["Yes", "Yes", "No"]),
                "ingestion_date": r_str[:10], "ingested_at": r_str, "is_after_cutoff": int(after),
                "sla_due_date": str(due),
                "claimed_at": claimed_at.strftime("%Y-%m-%d %H:%M:%S") if claimed_at else None,
                "updated_at": r_str})

            if stage in ("unclaimed", "claimed"):
                if stage == "claimed":
                    db.update_row("leads_master", "lead_id", lead_id, {"quotation_status": "Under Process"})
                continue

            # Quotation with 0-3 revisions
            q_number = db.next_quotation_number("2026-27" if day.month >= 4 else "2025-26")
            base_amount = round(rnd.uniform(35000, 380000), -2)
            revs = rnd.choice([0, 0, 1, 1, 2, 3])
            sent_at = None
            for rev in range(revs + 1):
                created = claimed_at + datetime.timedelta(hours=2 + rev * 24)
                if created > today:
                    created = today
                last = rev == revs
                status = ("Under Review" if stage == "review" else "Approved") if last else "Approved"
                if status == "Approved" and sent_at is None:
                    sent_at = created
                db.insert_row("quotations_master", {
                    "quotation_id": db.next_quotation_id(), "lead_id": lead_id, "client_id": client_id,
                    "quotation_number": q_number, "revision_no": rev,
                    "qut_amount": round(base_amount * (1 - 0.04 * rev), -2), "quotation_status": status,
                    "gross_amount": base_amount, "discount_percent": round(4.0 * rev, 2),
                    "discount_amount": round(base_amount - round(base_amount * (1 - 0.04 * rev), -2), 2),
                    "follow_up_required": "Yes", "claimed_qs_id": qs,
                    "approved_by_id": sam if status == "Approved" else None, "shared_by_id": qs,
                    "approved_date": created.strftime("%Y-%m-%d") if status == "Approved" else None,
                    "approved_month": created.strftime("%B %Y") if status == "Approved" else None,
                    "revision_reason": None if rev == 0 else rnd.choice(["Discount requested", "Quantity changed", "Spec change"]),
                    "created_by": qs, "created_at": created.strftime("%Y-%m-%d %H:%M:%S")})

            updates = {"followup_owner_id": qs, "claimed_qs_id": qs}
            if stage == "review" and sent_at is None:
                updates["quotation_status"] = "Under Process"
            else:
                updates["quotation_status"] = "Sent"
                updates["quote_sent_at"] = sent_at.strftime("%Y-%m-%d %H:%M:%S")
                updates["final_status"] = "In Discussion"

            # Follow-up calls
            calls = rnd.randint(1, 3) if stage in ("sent", "won", "lost") else 0
            for seq in range(1, calls + 1):
                call_at = sent_at + datetime.timedelta(days=seq, hours=rnd.randint(0, 5))
                if call_at > today:
                    break
                is_last = seq == calls
                outcome = {"won": "Done", "lost": "Cancled"}.get(stage) if is_last else rnd.choice(["In Discussion", "CallBack", "Not Responed"])
                outcome = outcome or rnd.choice(["In Discussion", "CallBack", "Under Finalization"])
                reason = rnd.choice(CANCEL_CATEGORY_OPTIONS) if outcome == "Cancled" else None
                db.insert_row("followup_logs", {
                    "lead_id": lead_id, "employee_id": qs, "followup_sequence_no": seq,
                    "followup_status": outcome, "cancel_category": reason,
                    "notes": f"Demo call {seq}: client {outcome.lower()}.",
                    "logged_at": call_at.strftime("%Y-%m-%d %H:%M:%S")})
                updates["final_status"] = outcome
                if outcome in ("Done", "Cancled"):
                    updates["closed_at"] = call_at.strftime("%Y-%m-%d %H:%M:%S")
                    updates["lost_reason"] = reason
            if updates.get("final_status") not in ("Done", "Cancled") and updates.get("quotation_status") == "Sent":
                nxt = today + datetime.timedelta(days=rnd.choice([-3, -1, 0, 0, 0, 1, 2, 4]))
                nxt = nxt.replace(hour=rnd.choice([10, 12, 14, 16, 18]), minute=0, second=0, microsecond=0)
                updates["next_followup_at"] = nxt.strftime("%Y-%m-%d %H:%M:%S")
            db.update_row("leads_master", "lead_id", lead_id, updates)

            # Orders and payments for won deals
            if updates.get("final_status") == "Done" and rnd.random() < 0.8:
                closed = datetime.datetime.strptime(updates["closed_at"], "%Y-%m-%d %H:%M:%S")
                created = min(closed + datetime.timedelta(days=1), today)
                net = round(base_amount * (1 - 0.04 * revs), -2)
                value = round(net * 1.18, -2)
                quote_id = db.fetch_all("quotations_master")
                quote_id = quote_id[quote_id["lead_id"] == lead_id].sort_values("revision_no").iloc[-1]["quotation_id"]
                order_id = db.next_order_id()
                owner = rnd.choice(po_team)
                terms = rnd.choice(terms_pool)
                dispatched = rnd.random() < 0.5
                db.insert_row("orders", {
                    "order_id": order_id, "lead_id": lead_id, "client_id": client_id, "quotation_id": quote_id,
                    "purchase_order_no": f"PO-{rnd.randint(1000, 9999)}", "pi_amount": value, "order_value": value,
                    "payment_status": "Pending", "production_status": rnd.choice(["Not Started", "In Production", "Completed"]),
                    "po_date": created.strftime("%Y-%m-%d"), "po_amount": value, "pi_number": f"PI-{rnd.randint(100, 999)}",
                    "delivery_days": 20, "po_checks": "{}", "po_verified_at": created.strftime("%Y-%m-%d %H:%M:%S"),
                    "po_verified_by": owner, "po_owner_id": owner, "po_claimed_at": created.strftime("%Y-%m-%d %H:%M:%S"),
                    "plan_advance": terms[0], "plan_dispatch": terms[1], "plan_install": terms[2],
                    "expected_delivery_date": (created + datetime.timedelta(days=rnd.choice([1, 2, 6, 20]))).strftime("%Y-%m-%d"),
                    "next_collection_date": (today + datetime.timedelta(days=rnd.choice([-4, -1, 0, 2, 5]))).replace(
                        hour=rnd.choice([11, 15]), minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S"),
                    "collection_remarks": "Demo: client promised payment", "created_by": ops_id,
                    "created_at": created.strftime("%Y-%m-%d %H:%M:%S")})
                if dispatched:
                    db.update_row("orders", "order_id", order_id, {"dispatched_at": min(created + datetime.timedelta(days=5), today)
                                                                   .strftime("%Y-%m-%d %H:%M:%S"), "dispatch_status": "Dispatched"})
                received = 0.0
                shares = [terms[0] / 100] if rnd.random() < 0.7 else []
                if dispatched and terms[1] and rnd.random() < 0.5:
                    shares.append(terms[1] / 100)
                for share in shares:
                    amt = round(value * share, -2)
                    paid = min(created + datetime.timedelta(days=rnd.randint(0, 6)), today)
                    db.insert_row("payments", {
                        "payment_id": db.next_payment_id(), "order_id": order_id, "amount": amt,
                        "paid_on": paid.strftime("%Y-%m-%d"), "mode": rnd.choice(["NEFT / RTGS", "UPI", "Cheque"]),
                        "reference": f"UTR{rnd.randint(100000, 999999)}", "recorded_by": owner, "notes": "Demo payment",
                        "created_at": paid.strftime("%Y-%m-%d %H:%M:%S")})
                    received += amt
                status = "Received" if received >= value - 1 else ("Partial" if received else "Pending")
                db.update_row("orders", "order_id", order_id,
                              {"payment_status": status, **({"next_collection_date": None} if status == "Received" else {})})

    # monthly targets for everyone, and a couple of payment calls / snoozes, so every report has something to show
    month = today.strftime("%Y-%m")
    for emp_id in by_role("SAM"):
        for metric, value in (("leads_converted", 3), ("sales_value", 800000), ("calls_logged", 15)):
            db.insert_row("targets", {"employee_id": emp_id, "month": month, "metric": metric, "value": value,
                                      "set_by": None, "set_at": stamp})
    for emp_id in by_role("QS"):
        for metric, value in (("quotations_sent", 12), ("leads_added", 4), ("calls_logged", 20)):
            db.insert_row("targets", {"employee_id": emp_id, "month": month, "metric": metric, "value": value,
                                      "set_by": None, "set_at": stamp})
    for emp_id in by_role("PO"):
        for metric, value in (("collections", 500000), ("pos_verified", 4), ("payment_calls", 10)):
            db.insert_row("targets", {"employee_id": emp_id, "month": month, "metric": metric, "value": value,
                                      "set_by": None, "set_at": stamp})
    orders = db.fetch_all("orders")
    for _, o in orders.head(4).iterrows():
        db.insert_row("payment_followups", {"order_id": o["order_id"], "milestone": "Before dispatch", "logged_by": o["po_owner_id"],
                                            "outcome": rnd.choice(["Promised to pay", "Payment delayed"]),
                                            "delay_reason": rnd.choice(["Client fund issue", "Awaiting internal approval"]),
                                            "notes": "Demo payment call", "logged_at": (today - datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                                            "next_call_at": o["next_collection_date"]})
    print(f"Loaded {n} demo leads across {days + 1} days.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load demo data into an EMPTY CRM database.")
    parser.add_argument("--db", default="data/crm_database.db")
    parser.add_argument("--password", required=True, help="Password for all demo employees")
    args = parser.parse_args()

    from database.sqlite_adapter import SQLiteAdapter
    from config.settings import DEFAULT_PRODUCTS

    adapter = SQLiteAdapter(args.db)
    adapter.init_schema()
    adapter.set_actor("SYSTEM")
    if adapter.count_rows("products") == 0:
        for name, cat in DEFAULT_PRODUCTS:
            adapter.insert_row("products", {"product_name": name, "category": cat, "is_active": 1})
    seed_demo_data(adapter, demo_password=args.password)
