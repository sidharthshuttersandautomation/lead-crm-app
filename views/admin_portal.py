import html
"""views/admin_portal.py - Admin overview, user management and audit trail."""
import datetime

import pandas as pd
import streamlit as st

from components.kpi_cards import render_kpi_cards
from config.settings import ROLES
from utils.metrics import amount, call_bucket, inr, latest_quotes, open_leads
from utils.security import hash_password, password_problem
from utils.time_utils import now_str, today_ist


def render_admin_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>Admin overview</h2>", unsafe_allow_html=True)
    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    if df_leads.empty:
        st.info("No leads yet. Add a lead or load demo data to see the overview.")
        return

    today = today_ist()
    lq = latest_quotes(df_quotes)
    active = open_leads(df_leads)
    won = df_leads[df_leads["final_status"] == "Done"]
    lost = df_leads[df_leads["final_status"] == "Cancled"]
    sent = df_leads[df_leads["quote_sent_at"].notna()]
    on_time = sent[sent["quote_sent_at"].astype(str).str[:10] <= sent["sla_due_date"].astype(str)]

    render_kpi_cards([
        {"label": "Leads", "value": len(df_leads)},
        {"label": "Open", "value": len(active)},
        {"label": "Done / Cancled", "value": f"{len(won)} / {len(lost)}"},
        {"label": "Quotes sent on time", "value": f"{len(on_time) / len(sent) * 100:.0f}%" if len(sent) else "—",
         "help": "Sent on or before the SLA date set by the 5:30 PM cutoff"},
    ])
    open_value = amount(lq[lq["lead_id"].isin(active["lead_id"]) & (lq["quotation_status"] == "Approved")]["qut_amount"]) if not lq.empty else 0
    won_value = amount(lq[lq["lead_id"].isin(won["lead_id"])]["qut_amount"]) if not lq.empty else 0
    unclaimed = active[active["claimed_qs_id"].isna() & (active["quotation_status"] != "Sent")]
    overdue = active[active["next_followup_at"].map(call_bucket) == "overdue"]
    render_kpi_cards([
        {"label": "Open pipeline", "value": inr(open_value), "help": "Latest approved quote of each open lead"},
        {"label": "Done value", "value": inr(won_value)},
        {"label": "Unclaimed tickets", "value": len(unclaimed)},
        {"label": "Overdue calls", "value": len(overdue)},
    ])

    st.markdown("---")
    with st.expander("Database backup"):
        st.caption("Downloads the complete database file. On Streamlit Cloud the database is reset "
                   "when the app restarts, so download a backup at the end of every working day.")
        try:
            with open(db_adapter.db_path, "rb") as fh:
                data = fh.read()
            if st.download_button("Download backup", data,
                                  file_name=f"crm_backup_{today.strftime('%Y-%m-%d')}.db",
                                  mime="application/octet-stream"):
                db_adapter.log_event("BACKUP_DOWNLOAD", None, None)
        except OSError as exc:
            st.error(f"Backup not available: {exc}")
    with st.expander("All leads (master data)"):
        st.dataframe(df_leads, width="stretch", hide_index=True)
    with st.expander("All quotations, every revision"):
        st.dataframe(df_quotes, width="stretch", hide_index=True)


def render_user_management(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>Users</h2>", unsafe_allow_html=True)
    df_emp = db_adapter.fetch_all("employees")

    tab_add, tab_edit, tab_list = st.tabs(["Add employee", "Edit employee", "Directory"])

    with tab_add:
        with st.form("add_employee", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Full name *")
                email = st.text_input("Email *", placeholder="name@sidharth.com")
            with c2:
                password = st.text_input("Temporary password *", type="password",
                                         help="At least 8 characters, letters and numbers. They can change it after signing in.")
                role = st.selectbox("Role *", ROLES)
            if st.form_submit_button("Create employee"):
                problem = password_problem(password)
                if not name.strip() or not email.strip():
                    st.error("Enter a name and email.")
                elif "@" not in email:
                    st.error("Enter a valid email address.")
                elif problem:
                    st.error(problem)
                else:
                    emp_id = db_adapter.next_employee_id()
                    ok = db_adapter.insert_row("employees", {
                        "employee_id": emp_id, "full_name": name.strip(),
                        "email": email.strip().lower(), "password_hash": hash_password(password),
                        "role": role, "is_active": 1, "is_team_lead": 0, "can_handle_po": 0, "created_at": now_str(),
                    })
                    if ok is None:
                        st.error(db_adapter.last_error)
                    else:
                        st.toast(f"Created {name.strip()} ({emp_id}).", icon="✅")
                        st.rerun()

    with tab_edit:
        if df_emp.empty:
            st.info("No employees yet.")
        else:
            labels = dict(zip(df_emp["full_name"] + " (" + df_emp["employee_id"] + ")", df_emp["employee_id"]))
            choice = st.selectbox("Employee", list(labels.keys()))
            emp = df_emp[df_emp["employee_id"] == labels[choice]].iloc[0]
            is_self = emp["employee_id"] == current_user["employee_id"]
            with st.form(f"edit_{emp['employee_id']}"):
                c1, c2 = st.columns(2)
                with c1:
                    new_name = st.text_input("Full name", value=emp["full_name"])
                    new_role = st.selectbox("Role", ROLES, index=ROLES.index(emp["role"]) if emp["role"] in ROLES else 0,
                                            disabled=is_self)
                with c2:
                    active = st.checkbox("Active (can sign in)", value=bool(emp["is_active"]), disabled=is_self)
                    lead = st.checkbox("Team lead — can use 🔀 Reassign & escalate", value=bool(emp.get("is_team_lead")))
                    reset = st.text_input("New password (leave blank to keep)", type="password")
                st.caption("Team-lead access applies the next time that person signs in. "
                           "PO access comes from the PO role (PO & PI Team).")
                if is_self:
                    st.caption("You can't change your own role or deactivate yourself.")
                if st.form_submit_button("Save changes"):
                    updates = {"full_name": new_name.strip() or emp["full_name"], "is_team_lead": int(lead)}
                    if not is_self:
                        updates.update({"role": new_role, "is_active": int(active)})
                    if reset:
                        problem = password_problem(reset)
                        if problem:
                            st.error(problem)
                            st.stop()
                        updates["password_hash"] = hash_password(reset)
                    if db_adapter.update_row("employees", "employee_id", emp["employee_id"], updates):
                        st.toast("Employee updated.", icon="✅")
                        st.rerun()
                    else:
                        st.error(db_adapter.last_error)

    with tab_list:
        st.dataframe(df_emp, width="stretch", hide_index=True)


ACTION_ICON = {"LOGIN": "🔓", "LOGOUT": "🚪", "LOGIN_FAILED": "⛔", "INSERT": "➕", "UPDATE": "✏️", "DELETE": "🗑️",
               "CLAIM": "🙋", "REASSIGN": "🔀", "PRIORITY": "🚩", "EXPORT": "📤", "BACKUP_DOWNLOAD": "💾",
               "QUOTE_APPROVED": "✅", "REVISION_REQUESTED": "↩️", "PO_VERIFIED": "🧾", "ORDER_DISPATCHED": "🚚",
               "ORDER_INSTALLED": "🛠️", "BULK_INSERT": "📥", "EXCEL_IMPORT": "📥", "CLEAR_LEAD_DATA": "🧹"}
CATEGORY = {"employees": "Users & sign-ins", "customers": "Leads", "leads_master": "Leads", "quotations_master": "Quotations",
            "followup_logs": "Calls", "call_snoozes": "Calls", "orders": "Orders & payments", "payments": "Orders & payments",
            "payment_followups": "Orders & payments", "targets": "Targets", "products": "Settings"}
FIELD = {"final_status": "stage", "quotation_status": "quotation status", "claimed_qs_id": "quotation specialist",
         "assigned_sam_id": "salesperson", "followup_owner_id": "call owner", "next_followup_at": "next call",
         "qut_amount": "final price", "is_active": "active", "next_collection_date": "next payment call",
         "collection_remarks": "payment remark", "payment_status": "payment status", "dispatch_status": "dispatch"}
HIDDEN = {"password_hash", "updated_at", "created_at", "claimed_at", "po_checks"}


def _json(value) -> dict:
    """Audit old/new values as a dict; empty cells (NaN/None) become {}."""
    import json
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        out = json.loads(value)
        return out if isinstance(out, dict) else {}
    except ValueError:
        return {}


def _describe(r, names, leads, quotes, orders):
    import json
    a, t, rid = r["action"], r["table_name"], str(r["record_id"] or "")
    new = _json(r.get("new_values"))

    def lead(i):
        return leads.get(str(i), f"lead {i}")
    what = {"leads_master": lambda: lead(rid), "customers": lambda: rid, "quotations_master": lambda: quotes.get(rid, rid),
            "orders": lambda: orders.get(rid, rid), "employees": lambda: names.get(rid, rid),
            "followup_logs": lambda: lead(new.get("lead_id", "")) if new else f"call {rid}",
            "payments": lambda: orders.get(str(new.get("order_id", "")), rid),
            "payment_followups": lambda: orders.get(str(new.get("order_id", "")), rid),
            "targets": lambda: names.get(str(new.get("employee_id", "")), "an employee"),
            "call_snoozes": lambda: lead(new.get("lead_id", ""))}.get(t, lambda: rid)
    w = html.escape(str(what()))
    text = {
        "LOGIN": "signed in", "LOGOUT": "signed out", "LOGIN_FAILED": f"failed to sign in ({html.escape(str(new.get('identifier', '')))})",
        "CLAIM": f"claimed the quotation ticket for <b>{w}</b>", "REASSIGN": f"reassigned <b>{w}</b>",
        "PRIORITY": f"changed priority of <b>{w}</b>", "EXPORT": f"exported {new.get('rows', '')} rows ({html.escape(str(t))})",
        "BACKUP_DOWNLOAD": "downloaded a database backup", "QUOTE_APPROVED": f"approved quotation <b>{w}</b>",
        "REVISION_REQUESTED": f"sent quotation <b>{w}</b> back for revision", "PO_VERIFIED": f"verified the PO for <b>{w}</b>",
        "ORDER_DISPATCHED": f"marked <b>{w}</b> dispatched", "ORDER_INSTALLED": f"marked <b>{w}</b> installed",
        "BULK_INSERT": f"imported {new.get('rows', '')} rows into {html.escape(str(t))}", "EXCEL_IMPORT": "imported the Excel workbook",
        "CLEAR_LEAD_DATA": "cleared all lead data before an import",
    }.get(a)
    if text is None:
        noun = {"leads_master": "lead", "customers": "client", "quotations_master": "quotation", "followup_logs": "call log",
                "orders": "order", "payments": "payment", "payment_followups": "payment call", "employees": "user",
                "targets": "target", "call_snoozes": "reminder snooze", "products": "product"}.get(t, t)
        verb = {"INSERT": "added", "UPDATE": "updated", "DELETE": "deleted"}.get(a, a.lower())
        extra = ""
        if t == "payments" and a == "INSERT":
            extra = f" of ₹{float(new.get('amount', 0)):,.0f}"
        if t == "followup_logs" and a == "INSERT":
            extra = f" — {html.escape(str(new.get('followup_status', '')))}"
        text = f"{verb} {noun} <b>{w}</b>{extra}"
    return text


def _changes(r, names):
    import json
    new = _json(r.get("new_values"))
    if r["action"] != "UPDATE" or not new:
        return ""
    old = _json(r.get("old_values"))
    chips = []
    for k, v in new.items():
        if k in HIDDEN:
            continue
        o = old.get(k)
        o, v = names.get(str(o), o), names.get(str(v), v)
        o = None if str(o).lower() in ("nan", "none") else o
        v = None if str(v).lower() in ("nan", "none") else v
        chips.append(f"<span style='display:inline-block; background:#F1F5F9; border-radius:8px; padding:2px 8px; margin:3px 4px 0 0;"
                     f" font-size:12px; color:#475569;'>{html.escape(FIELD.get(k, k.replace('_', ' ')))}: "
                     f"<s style='color:#64748B;'>{html.escape(str(o if o not in (None, '') else '—'))[:40]}</s> → "
                     f"<b style='color:#0E2C68;'>{html.escape(str(v if v not in (None, '') else '—'))[:40]}</b></span>")
    return "".join(chips[:6])


def render_audit_log(db_adapter, current_user):
    from components.cards import flat
    from components.kpi_cards import page_title
    page_title("Audit trail", "Who did what, and when. Entries can't be edited or deleted.")
    df = db_adapter.fetch_all("audit_log")
    if df.empty:
        st.info("No activity recorded yet.")
        return
    emp = db_adapter.fetch_all("employees")
    names = dict(zip(emp["employee_id"], emp["full_name"])) if not emp.empty else {}
    names.update({"SYSTEM": "System", "None": "—"})
    L = db_adapter.fetch_all("leads_master")
    leads = {str(i): f"{c} · {n}" for i, c, n in zip(L["lead_id"], L["client_id"], L["client_name"])} if not L.empty else {}
    Q = db_adapter.fetch_all("quotations_master")
    quotes = {str(i): f"{r} ({c})" for i, r, c in zip(Q["quotation_id"], Q["quotation_ref"], Q["client_id"])} if not Q.empty else {}
    O = db_adapter.fetch_all("orders")
    orders = {str(i): f"{c} · {n}" for i, c, n in zip(O["order_id"], O["client_id"], O["client_name"])} if not O.empty else {}

    df["who"] = df["actor_id"].map(lambda a: names.get(a, a) if a else "—")
    df["category"] = [("Users & sign-ins" if a.startswith("LOG") else CATEGORY.get(t, "Other"))
                      for a, t in zip(df["action"], df["table_name"].fillna(""))]
    today = str(today_ist())
    day = df["at"].astype(str).str[:10]
    d7 = str(today_ist() - datetime.timedelta(days=7))
    active_today = df[(day == today) & ~df["action"].isin(["LOGIN", "LOGOUT", "LOGIN_FAILED"]) & ~df["who"].isin(["System", "—"])]["who"].value_counts()
    render_kpi_cards([
        {"label": "Actions today", "value": int((day == today).sum()), "icon": "⚡", "tone": "blue"},
        {"label": "Sign-ins today", "value": int(((day == today) & (df["action"] == "LOGIN")).sum()), "icon": "🔓", "tone": "green",
         "sub": f"{df[(day == today) & (df['action'] == 'LOGIN')]['who'].nunique()} people"},
        {"label": "Failed sign-ins (7 days)", "value": int(((day > d7) & (df["action"] == "LOGIN_FAILED")).sum()), "icon": "⛔",
         "tone": "red"},
        {"label": "Most active today", "value": active_today.index[0] if len(active_today) else "—", "icon": "🏃", "tone": "teal",
         "sub": f"{int(active_today.iloc[0])} changes" if len(active_today) else ""},
    ])

    c1, c2, c3, c4 = st.columns([1, 1.3, 1.3, 1.4])
    with c1:
        span = st.selectbox("When", ["Today", "Last 7 days", "Last 30 days", "All time"], index=1, key="au_span")
    with c2:
        who = st.multiselect("Who", sorted(df["who"].dropna().unique()), placeholder="Everyone", key="au_who")
    with c3:
        cats = st.multiselect("What", sorted(df["category"].unique()), placeholder="Everything", key="au_cat")
    with c4:
        q = st.text_input("Search", placeholder="Client ID, quotation, name…", key="au_q").strip().lower()
    since = {"Today": today, "Last 7 days": d7, "Last 30 days": str(today_ist() - datetime.timedelta(days=30)), "All time": ""}[span]
    out = df[day >= since] if since else df
    if who:
        out = out[out["who"].isin(who)]
    if cats:
        out = out[out["category"].isin(cats)]
    out = out.sort_values("audit_id", ascending=False)
    out = out.assign(text=[_describe(r, names, leads, quotes, orders) for _, r in out.iterrows()])
    if q:
        out = out[(out["text"].str.lower() + " " + out["record_id"].astype(str).str.lower()
                   + " " + out["new_values"].fillna("").str.lower()).str.contains(q, regex=False)]

    if not out.empty:
        per = out.assign(d=pd.to_datetime(out["at"].astype(str).str[:10])).groupby(["d", "category"]).size().reset_index(name="Actions")
        import plotly.express as px
        fig = px.bar(per, x="d", y="Actions", color="category",
                     color_discrete_sequence=["#184B9C", "#00A859", "#0E7490", "#B45309", "#7C3AED", "#BE123C", "#94A3B8"])
        fig.update_layout(height=200, margin=dict(t=10, b=10, l=10, r=10), legend_title_text="", xaxis_title="", yaxis_title="",
                          legend=dict(orientation="h", y=1.25), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", bargap=0.2)
        st.plotly_chart(fig, width="stretch")

    view_mode = st.segmented_control("View", ["Activity feed", "Table"], default="Activity feed", key="au_view") or "Activity feed"
    st.caption(f"{len(out)} entries")
    if out.empty:
        st.info("Nothing matches these filters.")
        return
    if view_mode == "Table":
        st.dataframe(out[["at", "who", "category", "action", "table_name", "record_id", "old_values", "new_values"]],
                     width="stretch", hide_index=True)
    else:
        pages = max(1, (len(out) - 1) // 60 + 1)
        page = st.number_input("Page", 1, pages, 1, key="au_page") if pages > 1 else 1
        chunk = out.iloc[(page - 1) * 60: page * 60]
        html_parts, current = [], None
        for _, r in chunk.iterrows():
            d = str(r["at"])[:10]
            if d != current:
                current = d
                label = "Today" if d == today else datetime.date.fromisoformat(d).strftime("%A, %d %B %Y")
                html_parts.append(f"<div style='font-weight:800; color:#0E2C68; margin:16px 0 6px;'>{label}</div>")
            initials = "".join(p[0] for p in str(r["who"]).split()[:2]).upper() or "?"
            bad = r["action"] == "LOGIN_FAILED"
            html_parts.append(flat(f"""
              <div style='display:flex; gap:12px; align-items:flex-start; background:#FFFFFF; border:1px solid rgba(24,75,156,0.12);
                border-left:4px solid {"#BE123C" if bad else "#184B9C"}; border-radius:12px; padding:10px 14px; margin-bottom:6px;'>
                <div style='width:34px; height:34px; border-radius:50%; background:#E8EFFB; color:#184B9C; font-weight:800; font-size:12.5px;
                  display:flex; align-items:center; justify-content:center; flex-shrink:0;'>{html.escape(initials)}</div>
                <div style='flex:1; min-width:0;'>
                  <div style='font-size:14px; color:#1E293B;'>{ACTION_ICON.get(r["action"], "•")} <b>{html.escape(str(r["who"]))}</b> {r["text"]}</div>
                  <div style='font-size:12px; color:#64748B; margin-top:2px;'>{str(r["at"])[11:16]} · {html.escape(r["category"])}</div>
                  <div>{_changes(r, names)}</div>
                </div></div>"""))
        st.markdown("".join(html_parts), unsafe_allow_html=True)
    st.download_button("Download these entries (CSV)", out.drop(columns=["text"]).to_csv(index=False).encode("utf-8"),
                       file_name="audit_trail.csv", mime="text/csv")
