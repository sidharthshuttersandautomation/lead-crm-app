"""views/lead_portal.py - Add a new lead."""
import streamlit as st

from config.settings import CLIENT_TYPES, CUSTOMER_RESPONDED, PRIORITIES, SALESPERSON_LIST, SOURCE_OPTIONS
from utils.people import name_key
from utils.id_generator import generate_client_id
from utils.sla_calculator import evaluate_sla
from components.kpi_cards import page_title, render_kpi_cards
from utils.metrics import delta_kpi
from utils.time_utils import now_ist, TIMESTAMP_FMT

UNASSIGNED = "Unassigned — any specialist can claim it"


def render_lead_portal(db_adapter, current_user):
    page_title("Add new lead", "Saved leads go straight to the quotation desk, or to the specialist you assign.")

    df_products = db_adapter.fetch_all("products")
    df_emp = db_adapter.fetch_all("employees")
    df_customers = db_adapter.fetch_all("customers")

    if df_products.empty:
        st.error("No products are set up. Ask an admin to add products first.")
        return
    products = df_products[df_products["is_active"] == 1]
    by_name = {name_key(n): i for n, i in zip(df_emp["full_name"], df_emp["employee_id"])} if not df_emp.empty else {}
    sam_labels = {}
    for name in SALESPERSON_LIST:
        if name == "N/A":
            sam_labels["N/A"] = None
        elif name_key(name) in by_name:
            sam_labels[name] = by_name[name_key(name)]
    qs_staff = df_emp[(df_emp["role"] == "QS") & (df_emp["is_active"] == 1)]
    qs_labels = {UNASSIGNED: None}
    qs_labels.update(dict(zip(qs_staff["full_name"] + " (" + qs_staff["employee_id"] + ")", qs_staff["employee_id"])))
    qs_keys = list(qs_labels.keys())
    default_qs = next((i for i, v in enumerate(qs_labels.values()) if v == current_user["employee_id"]), 0)

    df_leads = db_adapter.fetch_all("leads_master")
    mine = df_leads[df_leads["handled_by_lge_id"] == current_user["employee_id"]] if not df_leads.empty else df_leads
    won = mine[mine["final_status"] == "Done"] if not mine.empty else mine
    render_kpi_cards([
        delta_kpi("Leads I added (7 days)", mine, "ingested_at", 7, icon="📥", tone="blue"),
        delta_kpi("Leads I added (30 days)", mine, "ingested_at", 30, icon="🗂️", tone="navy"),
        {"label": "Reached quotation", "icon": "📤", "tone": "teal",
         "value": f"{(mine['quote_sent_at'].notna().mean() * 100):.0f}%" if len(mine) else "—",
         "sub": "of all leads you added"},
        {"label": "Done from my leads", "value": len(won), "icon": "🏆", "tone": "green"},
    ])
    from config.settings import PRODUCT_LIST
    active = dict(zip(products["product_name"], products["product_id"]))
    product_ids = {n: active[n] for n in PRODUCT_LIST if n in active}
    product_ids.update({n: i for n, i in active.items() if n not in product_ids})

    with st.form("add_lead_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            client_type = st.selectbox("Type of client *", CLIENT_TYPES)
            client_name = st.text_input("Client name *", placeholder="Full name")
            company_name = st.text_input("Company name", placeholder="Firm or company")
        with c2:
            contact_no = st.text_input("Contact number *", placeholder="10-digit mobile")
            email = st.text_input("Email", placeholder="client@company.com")
            product = st.selectbox("Product *", list(product_ids.keys()))
        with c3:
            quantity = st.number_input("Quantity *", min_value=1, value=1)
            address = st.text_input("Address *", placeholder="Site or office address")
            city = st.text_input("City *", value="Indore")

        c4, c5, c6 = st.columns(3)
        with c4:
            state = st.text_input("State", value="Madhya Pradesh")
        with c5:
            source = st.selectbox("Source *", SOURCE_OPTIONS)
        with c6:
            sam_label = st.selectbox("Assigned salesperson *", list(sam_labels.keys()))

        responded = st.radio("Customer responded", CUSTOMER_RESPONDED, horizontal=True)
        c7, c8, c9 = st.columns([1.6, 1, 1])
        with c7:
            qs_choice = st.selectbox("Assign quotation to", qs_keys, index=default_qs,
                                     help="The lead appears straight away under 'My tickets' on that specialist's dashboard.")
        with c8:
            priority = st.selectbox("Priority", PRIORITIES)
        with c9:
            st.write("")
            key_account = st.checkbox("Key enterprise account")
        remarks = st.text_area("Requirement details", placeholder="Size, site conditions, timeline...")
        allow_duplicate = st.checkbox("Save even if this phone number already exists")

        if st.form_submit_button("Save lead"):
            phone = "".join(ch for ch in contact_no if ch.isdigit())
            missing = [label for label, value in [("Client name", client_name), ("Contact number", phone),
                                                  ("Address", address), ("City", city)] if not str(value).strip()]
            if missing:
                st.error("Fill in: " + ", ".join(missing) + ".")
                return
            if len(phone) < 10:
                st.error("Contact number needs at least 10 digits.")
                return

            if not df_customers.empty and not allow_duplicate:
                existing = df_customers[df_customers["phone_number"].astype(str).str[-10:] == phone[-10:]]
                if not existing.empty:
                    ids = ", ".join(existing["client_id"].astype(str).tolist()[:5])
                    st.error(f"This phone number is already on {ids}. Tick 'Save even if this phone "
                             "number already exists' if this is a genuinely new enquiry.")
                    return

            now = now_ist()
            after_cutoff, due_date, _ = evaluate_sla(now)
            client_id = generate_client_id(db_adapter, client_type, now.date())
            stamp = now.strftime(TIMESTAMP_FMT)

            ok = db_adapter.insert_row("customers", {
                "client_id": client_id, "client_name": client_name.strip(),
                "company_name": company_name.strip() or None, "phone_number": phone,
                "email": email.strip() or None, "address": address.strip(), "city": city.strip(),
                "state": state.strip() or None, "is_key_account": int(key_account), "created_at": stamp,
            })
            if ok is None:
                st.error(db_adapter.last_error)
                return

            assigned_qs = qs_labels[qs_choice]
            lead_id = db_adapter.insert_row("leads_master", {
                "client_id": client_id,
                "product_id": int(product_ids[product]),
                "quantity": int(quantity),
                "source": source,
                "type_of_client": client_type,
                "customer_responded": responded,
                "final_status": "Pending",
                "quotation_status": "Under Process" if assigned_qs else "Not Sent",
                "priority": "High" if key_account else priority,
                "remarks": remarks.strip() or None,
                "handled_by_lge_id": current_user["employee_id"],
                "assigned_sam_id": sam_labels[sam_label],
                "claimed_qs_id": assigned_qs,
                "claimed_at": stamp if assigned_qs else None,
                "followup_owner_id": assigned_qs or current_user["employee_id"],
                "ingestion_date": stamp[:10],
                "ingested_at": stamp,
                "is_after_cutoff": int(after_cutoff),
                "sla_due_date": str(due_date),
                "updated_at": stamp,
            })
            if lead_id is None:
                db_adapter.delete_row("customers", "client_id", client_id)
                st.error(db_adapter.last_error)
                return

            when = "today" if not after_cutoff else f"by {due_date.strftime('%d %b')} (after 5:30 PM cutoff)"
            to = f" Assigned to {qs_choice.split(' (')[0]}." if assigned_qs else " Waiting in the claim queue."
            st.toast(f"Lead {client_id} saved. Quotation due {when}.{to}", icon="✅")
            st.rerun()
