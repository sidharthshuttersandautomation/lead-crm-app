"""
app.py - Sidharth Shutter CRM: sign-in and role-based navigation.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

st.set_page_config(page_title="Sidharth Shutter CRM", page_icon="🏢", layout="wide",
                   initial_sidebar_state="expanded")

from components.call_reminder import render_call_reminders
from components.desktop_notify import permission_control
from components.navbar import render_navbar
from components.styles import apply_custom_theme
from config.settings import LOGO_PATH, ROLE_DESCRIPTIONS
from database.factory import bootstrap_database, get_adapter, secrets_status
from utils.auth import get_current_user, init_session_auth, login_user, logout_user
from views.account import render_account
from views.accounts_portal import render_collections_portal
from utils.notifications import alert_badge_counts
from views.admin_portal import render_audit_log, render_user_management
from views.client_inspector import render_client_inspector
from views.data_import import render_data_import
from views.po_portal import can_use_po, render_po_portal
from views.admin_quotes import render_admin_quote_desk, render_quote_register
from views.employee_progress import render_my_progress_report
from views.employee_report import render_employee_report
from views.lead_portal import render_lead_portal
from views.management import (render_business_tower, render_master_export, render_reassign_escalate,
                              render_team_performance)
from views.notification_center import render_notification_center
from views.process_order_portal import render_process_portal
from views.quotation_portal import (render_qs_detailed_form_entry, render_qs_followup_workday,
                                    render_qs_generator_and_claim, render_qs_performance_dashboard)
from views.sales_portal import render_sales_portal

apply_custom_theme()

# One adapter per script run; bootstrap (tables, products, first admin) runs once per server.
db_adapter = get_adapter()
bootstrap_database(db_adapter.db_path)
init_session_auth()


def show_logo():
    if Path(ROOT_DIR / LOGO_PATH).exists():
        st.image(str(ROOT_DIR / LOGO_PATH), width="stretch")
    else:
        st.markdown("<h3 style='color:#184B9C; font-weight:800; margin:0;'>SIDHARTH SHUTTER</h3>",
                    unsafe_allow_html=True)


# ------------------------------------------------------------------ sign-in
if not st.session_state.get("authenticated"):
    from views.login import render_login
    render_login(db_adapter, ROOT_DIR)
    st.stop()

# ------------------------------------------------------------------ signed in
user = get_current_user()
db_adapter.set_actor(user["employee_id"])
render_navbar(user)
render_call_reminders(db_adapter, user)

role = user["role"]
initials = "".join(p[0].upper() for p in user["name"].split()[:2]) or "U"

try:
    _f, _q, _c = alert_badge_counts(db_adapter, user)
    _badge = " ".join(x for x in [f"📞{_f}" if _f else "", f"📄{_q}" if _q else "", f"💰{_c}" if _c else ""] if x)
except Exception:
    _badge = ""
ALERTS = ("🔔 Alerts", render_notification_center)
COLLECTIONS = ("💰 Sales & collections", render_collections_portal)
PROGRESS = ("📊 My progress", render_my_progress_report)
INSPECTOR = ("🔍 Client inspector", render_client_inspector)
ACCOUNT = ("🔑 My account", render_account)
FOLLOWUPS = ("📞 Follow-up calls", render_qs_followup_workday)

def grouped(title, items, key):
    """A main-menu entry whose page shows its own sub-tabs (only the chosen sub-tab is loaded)."""
    names = [n for n, _ in items]
    funcs = dict(items)

    def page(db, usr):
        sub = st.segmented_control(title, names, key=key, label_visibility="collapsed",
                                   default=None if key in st.session_state else names[0]) or names[0]
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        funcs[sub](db, usr)
    page.sub_pages = names
    page.sub_key = key
    return title, page


ADMIN_GROUPS = [
    grouped("🏁 Overview", [("🏁 Business tower", render_business_tower), ("👥 Team performance", render_team_performance),
                           ("📈 Employee report card", render_employee_report)], "sub_overview"),
    ALERTS,
    grouped("👥 Leads & clients", [("🔍 Client inspector", render_client_inspector), ("📥 Add new lead", render_lead_portal),
                                  FOLLOWUPS, ("🔀 Reassign & escalate", render_reassign_escalate)], "sub_leads"),
    grouped("📄 Quotations", [("📋 Quotation desk", render_admin_quote_desk), ("📄 Quotation register", render_quote_register)],
            "sub_quotes"),
    grouped("💼 Sales & money", [("💼 Sales pipeline", render_sales_portal), COLLECTIONS, ("🧾 PO & payments", render_po_portal),
                                ("⚙️ Order fulfilment", render_process_portal)], "sub_money"),
    grouped("⚙️ Admin tools", [("🔐 Users", render_user_management), ("🧾 Audit trail", render_audit_log),
                              ("📦 Master export & backup", render_master_export), ("📤 Import from Excel", render_data_import)],
            "sub_tools"),
    ACCOUNT,
]

NAV = {
    "ADMIN": ADMIN_GROUPS,
    "QS": [
        ("📋 Quotation desk", render_qs_performance_dashboard), ALERTS,
        ("📄 Claim & create quotations", render_qs_generator_and_claim),
        ("📝 Quotation entry & revisions", render_qs_detailed_form_entry),
        FOLLOWUPS, ("📥 Add new lead", render_lead_portal), INSPECTOR, PROGRESS, ACCOUNT,
    ],
    "LGE": [("📥 Add new lead", render_lead_portal), ALERTS, FOLLOWUPS, INSPECTOR, PROGRESS, ACCOUNT],
    "SAM": [("💼 Sales pipeline", render_sales_portal), ALERTS, FOLLOWUPS, INSPECTOR, PROGRESS, ACCOUNT],
    "OPERATIONS": [("⚙️ Order fulfilment", render_process_portal), ALERTS, INSPECTOR, PROGRESS, ACCOUNT],
    "PO": [("🧾 PO & payments", render_po_portal), ALERTS, ("💰 Collections", render_collections_portal),
           PROGRESS, ACCOUNT],
    "ACCOUNTS": [("💰 Collections", render_collections_portal), ALERTS, ("⚙️ Orders", render_process_portal),
                 INSPECTOR, PROGRESS, ACCOUNT],
}
nav_items = list(NAV.get(role, [ALERTS, ACCOUNT]))
# extra access given in Users: team leads reassign, PO handlers get the PO desk
if user.get("is_team_lead") and role != "ADMIN":
    nav_items.insert(2, ("🔀 Reassign & escalate", render_reassign_escalate))
views = dict(nav_items)

# "Log this call" from a reminder jumps to the follow-up page filtered to that client
# Buttons elsewhere ("Log this call", "Go to the quote") ask to open a page with some widget values preset.
if "goto" in st.session_state:
    request = st.session_state.pop("goto")
    target = request.get("page")
    found = target in views
    if found:
        st.session_state["nav_page"] = target
    else:  # a sub-tab inside one of the admin's grouped pages
        for name, fn in views.items():
            if target in getattr(fn, "sub_pages", []):
                st.session_state["nav_page"] = name
                st.session_state[fn.sub_key] = target
                found = True
                break
    if found:
        for key, value in request.items():
            if key != "page":
                st.session_state[key] = value

with st.sidebar:
    show_logo()
    st.markdown(f"""
        <div style='background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.18); border-radius:12px; padding:12px 14px; margin-bottom:20px; display:flex; align-items:center; gap:12px;'>
            <div style='background:#00A859; font-weight:800; font-size:15px; width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;'>{initials}</div>
            <div>
                <div style='font-size:14.5px; font-weight:700;'>{st.session_state['user']['name']}</div>
                <div style='font-size:11.5px; font-weight:700;'>{ROLE_DESCRIPTIONS.get(role, role)}</div>
            </div>
        </div>""", unsafe_allow_html=True)

    permission_control()
    selected = st.radio("Menu", list(views.keys()), label_visibility="collapsed", key="nav_page",
                        format_func=lambda k: f"{k}  ·  {_badge}" if k == ALERTS[0] and _badge else k)
    st.markdown("<hr style='border:none; border-top:1px solid rgba(255,255,255,0.15);'>", unsafe_allow_html=True)
    if st.button("Sign out", width="stretch"):
        logout_user(db_adapter)
        st.rerun()

views[selected](db_adapter, user)
