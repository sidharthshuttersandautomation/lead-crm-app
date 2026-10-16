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
NO_FOLLOWER = "Unclaimed — anyone can take it"
FOLLOWUP_ROLES = ["QS", "SAM", "LGE"]


def followup_options(df_emp):
    """'Follow-up by' choices: nobody yet (unclaimed) or any active person who makes client calls."""
    people = df_emp[df_emp["role"].isin(FOLLOWUP_ROLES) & (df_emp["is_active"] == 1)] if not df_emp.empty else df_emp
    people = people.assign(_o=people["role"].map({"QS": 0, "SAM": 1, "LGE": 2})).sort_values(["_o", "full_name"])
    out = {NO_FOLLOWER: None}
    out.update(dict(zip(people["full_name"] + " (" + people["role"].map({"QS": "Quotation", "SAM": "Sales",
                                                                          "LGE": "Lead exec"}) + ")", people["employee_id"])))
    return out


LEAD_SECTIONS = ["📥 Add new lead", "👤 Assign salesperson / follow-up"]


def render_lead_portal(db_adapter, current_user):
    page_title("Leads", "Add new leads and make sure every lead has a salesperson.")
    leads = db_adapter.fetch_all("leads_master")
    pool = _assignable(leads, current_user)
    unassigned = int(pool["assigned_sam_id"].isna().sum()) if not pool.empty else 0
    if "assign_goto" in st.session_state:          # "Assign salesperson" button from Alerts
        st.session_state["lead_section"] = LEAD_SECTIONS[1]
        st.session_state["assign_pick"] = st.session_state.pop("assign_goto")
        st.session_state.pop("assign_sel", None)
        st.session_state["assign_only"] = False
    labels = {LEAD_SECTIONS[0]: LEAD_SECTIONS[0],
              LEAD_SECTIONS[1]: LEAD_SECTIONS[1] + (f" · {unassigned} without one" if unassigned else "")}
    section = st.segmented_control("Section", LEAD_SECTIONS, key="lead_section", format_func=lambda x: labels[x],
                                   default=None if "lead_section" in st.session_state else LEAD_SECTIONS[0],
                                   label_visibility="collapsed") or LEAD_SECTIONS[0]
    if section == LEAD_SECTIONS[0]:
        _add_lead(db_adapter, current_user)
    else:
        _assign_salesperson(db_adapter, current_user, pool)


def _assignable(leads, user):
    """Open leads this person may assign: admins all; others the leads they added (salespeople: also their own)."""
    from utils.metrics import open_leads
    active = open_leads(leads)
    if active.empty or user["role"] == "ADMIN":
        return active
    me = user["employee_id"]
    return active[(active["handled_by_lge_id"] == me) | (active["assigned_sam_id"] == me)]


def salesperson_options(df_emp):
    by_name = {name_key(n): i for n, i in zip(df_emp["full_name"], df_emp["employee_id"])} if not df_emp.empty else {}
    out = {}
    for name in SALESPERSON_LIST:
        if name == "N/A":
            out["N/A"] = None
        elif name_key(name) in by_name:
            out[name] = by_name[name_key(name)]
    sams = df_emp[(df_emp["role"] == "SAM") & (df_emp["is_active"] == 1)] if not df_emp.empty else df_emp
    for n, i in zip(sams["full_name"], sams["employee_id"]):     # any salesperson login not in the list
        if i not in out.values():
            out[n] = i
    return out


def _assign_salesperson(db, user, pool):
    from components.cards import CSS as CARD_CSS, card_html, esc
    from components.time_picker import fmt_12h
    from utils.governance import reassign_leads
    if pool.empty:
        st.info("No open leads to assign.")
        return
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    who = "all open leads" if user["role"] == "ADMIN" else "open leads you added"
    st.caption(f"Showing {who}. Every change is saved in the audit trail with your reason.")
    if "assign_only" not in st.session_state:
        st.session_state["assign_only"] = bool(pool["assigned_sam_id"].isna().any())
    only_missing = st.toggle("Only leads without a salesperson", key="assign_only")
    view = pool[pool["assigned_sam_id"].isna()] if only_missing else pool
    if view.empty:
        st.success("Every lead here has a salesperson. 🎉")
        return
    view = view.sort_values("ingested_at", ascending=False)
    labels = {f"{r['client_id']} · {r['client_name']} · now: {r.get('assigned_salesperson') or 'N/A — nobody'}": r["lead_id"]
              for _, r in view.iterrows()}
    ids = list(labels.values())
    want = st.session_state.get("assign_pick")
    pick = st.selectbox("Lead", list(labels.keys()), index=ids.index(want) if want in ids else 0, key="assign_sel")
    row = view[view["lead_id"] == labels[pick]].iloc[0]
    st.markdown(card_html(row["client_id"], row["client_name"], row.get("company_name"),
                          pills=[("No salesperson" if not row.get("assigned_salesperson") or str(row.get("assigned_salesperson")) == "nan"
                                  else f"Salesperson: {row['assigned_salesperson']}", "red" if row["assigned_sam_id"] is None
                                  or str(row["assigned_sam_id"]) == "nan" else "blue")],
                          fields=[("Product", f"{esc(row['product'])} × {row['qty']}"), ("City", esc(row.get("city"))),
                                  ("Source", esc(row.get("source"))), ("Received", esc(fmt_12h(row.get("ingested_at")))),
                                  ("Added by", esc(row.get("leads_handled_by"))), ("Stage", esc(row["final_status"]))]),
                unsafe_allow_html=True)
    df_emp = db.fetch_all("employees")
    opts = salesperson_options(df_emp)
    fu = followup_options(df_emp)
    fu_keys = list(fu.keys())
    cur_fu = next((i for i, v in enumerate(fu.values()) if v == row.get("followup_owner_id")), 0)
    sam_keys = list(opts.keys())
    cur_sam = next((i for i, v in enumerate(opts.values()) if v == row.get("assigned_sam_id")), 0)
    with st.form(f"assign_{row['lead_id']}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            new = st.selectbox("Assign to *", sam_keys, index=cur_sam)
        with c2:
            new_fu = st.selectbox("Follow-up by", fu_keys, index=cur_fu)
        reason = st.text_input("Reason *", placeholder="e.g. Client is in Jeevan sir's area")
        if st.form_submit_button("Save salesperson", type="primary"):
            if not reason.strip():
                st.error("Give a reason — it is saved in the audit trail.")
            else:
                one = view[view["lead_id"] == row["lead_id"]]
                errors, changed = [], []
                if opts[new] != row.get("assigned_sam_id") and opts[new] is not None:
                    errors += reassign_leads(db, one, "SAM", opts[new], reason.strip())[1]
                    changed.append(f"salesperson → {new}")
                if fu[new_fu] is not None and fu[new_fu] != row.get("followup_owner_id"):
                    errors += reassign_leads(db, one, "FOLLOWUP", fu[new_fu], reason.strip())[1]
                    changed.append(f"follow-up by → {new_fu.split(' (')[0]}")
                if errors:
                    st.error(errors[0])
                elif not changed:
                    st.info("Nothing changed — pick a different salesperson or follow-up person.")
                else:
                    st.session_state.pop("assign_pick", None)
                    st.toast(f"{row['client_id']}: " + ", ".join(changed) + ".", icon="✅")
                    st.rerun()


def _add_lead(db_adapter, current_user):

    df_products = db_adapter.fetch_all("products")
    df_emp = db_adapter.fetch_all("employees")
    df_customers = db_adapter.fetch_all("customers")

    if df_products.empty:
        st.error("No products are set up. Ask an admin to add products first.")
        return
    products = df_products[df_products["is_active"] == 1]
    sam_labels = salesperson_options(df_emp)
    sam_keys = list(sam_labels.keys())
    # a salesperson adding their own client is the salesperson by default
    default_sam = next((i for i, v in enumerate(sam_labels.values()) if v == current_user["employee_id"]), 0)
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
            sam_label = st.selectbox("Assigned salesperson *", sam_keys, index=default_sam,
                                     help="Choose N/A if you don't know yet — it can be assigned later under 👤 Assign salesperson.")

        responded = st.radio("Customer responded", CUSTOMER_RESPONDED, horizontal=True)
        fu_labels = followup_options(df_emp)
        fu_keys = list(fu_labels.keys())
        default_fu = next((i for i, v in enumerate(fu_labels.values()) if v == current_user["employee_id"]), 0)
        c7, c8 = st.columns(2)
        with c7:
            qs_choice = st.selectbox("Assign quotation to", qs_keys, index=default_qs,
                                     help="The lead appears straight away under 'My tickets' on that specialist's dashboard.")
        with c8:
            fu_choice = st.selectbox("Follow-up by *", fu_keys, index=default_fu,
                                     help="Who calls the client. 'Unclaimed' puts it in the Unclaimed follow-ups list "
                                          "where anyone can take it.")
        c9, c10 = st.columns(2)
        with c9:
            priority = st.selectbox("Priority", PRIORITIES)
        with c10:
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
                "followup_owner_id": fu_labels[fu_choice],
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
