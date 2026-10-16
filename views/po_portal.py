"""
views/po_portal.py - Process Order (PO) & Proforma Invoice desk with 3-stage payment collection.

Flow per order:  PO received -> PO verified (checklist) -> 50% advance -> dispatched -> 40% -> installed -> 10%.
Payment calls work like follow-up calls: outcome, promised date, delay reason, next call (AM/PM).
"""
import datetime
import html
import json

import pandas as pd
import streamlit as st

from components.cards import CSS as CARD_CSS, card_html, clean, esc, flat
from components.contact import contact_links
from components.kpi_cards import page_title, render_kpi_cards
from components.time_picker import fmt_12h, time_12h
from config.settings import (DEFAULT_DELIVERY_DAYS, DELAY_REASONS, PAYMENT_MODES, PAYMENT_OUTCOMES, PAYMENT_TERM_PRESETS,
                             PO_CHECKS, STAGE_WON)
from utils.metrics import inr, latest_quotes
from config.settings import PO_STAGES
from utils.payment_plan import (checks, current_milestone, milestones, paid_percent, payment_alerts, plan_label, plan_of,
                                po_days, stage_label, tracker_html)
from utils.payments import payment_status
from utils.time_utils import now_ist, now_str, today_ist

SECTIONS = ["📅 Today", "📥 Claim new POs", "📦 My orders", "🗂️ Order profile", "📈 PO progress"]


def _num(v, default=0.0) -> float:
    """Number from a cell that may be empty or NaN."""
    try:
        f = float(v)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


def can_use_po(user) -> bool:
    from config.settings import PO_ROLES
    return user.get("role") in PO_ROLES


def mark_dispatched(db, order, when=None):
    when = when or now_str()
    ok = db.update_row("orders", "order_id", order["order_id"],
                       {"dispatched_at": when, "dispatch_status": "Dispatched", "updated_at": now_str()})
    if ok:
        db.log_event("ORDER_DISPATCHED", "orders", order["order_id"])
    return ok


def mark_installed(db, order, when=None):
    when = when or now_str()
    ok = db.update_row("orders", "order_id", order["order_id"],
                       {"installed_at": when, "dispatch_status": "Installed", "updated_at": now_str()})
    if ok:
        db.log_event("ORDER_INSTALLED", "orders", order["order_id"])
    return ok


def render_po_portal(db_adapter, current_user):
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    page_title("PO & payments", "Check each Process Order, then collect 50% advance · 40% before dispatch · 10% after installation.")
    orders = db_adapter.fetch_all("orders")
    owner = None if current_user["role"] == "ADMIN" else current_user["employee_id"]
    alerts = payment_alerts(orders, owner)

    today = today_ist()
    month = str(today)[:7]
    pays = db_adapter.fetch_all("payments")
    collected_month = float(pays[pays["paid_on"].astype(str).str[:7] == month]["amount"].sum()) if not pays.empty else 0.0
    due_now = 0.0
    if not orders.empty:
        for _, o in orders.iterrows():
            m = current_milestone(o)
            if m and m["due"] and m["due"] <= today:
                due_now += m["balance"]
    render_kpi_cards([
        {"label": "POs to verify", "value": len(alerts["verify"]), "icon": "🧾", "tone": "amber"},
        {"label": "Payment calls overdue / today", "value": f"{len(alerts['calls_overdue'])} / {len(alerts['calls_today'])}",
         "icon": "📞", "tone": "red"},
        {"label": "Deliveries in 2 days", "value": len(alerts["deliveries"]), "icon": "🚚", "tone": "blue",
         "sub": "ask for the 40% payment"},
        {"label": "Due now (all stages)", "value": inr(due_now), "icon": "⏳", "tone": "red"},
        {"label": "Collected this month", "value": inr(collected_month), "icon": "💵", "tone": "green"},
    ])

    if "po_goto" in st.session_state:          # requested by a button on the previous run
        st.session_state["po_section"] = SECTIONS[3]
        st.session_state["po_open"] = st.session_state.pop("po_goto")
        st.session_state.pop("po_pick", None)
    leads = db_adapter.fetch_all("leads_master")
    done = leads[leads["final_status"] == STAGE_WON] if not leads.empty else leads
    unclaimed = done[~done["lead_id"].isin(orders["lead_id"])] if not orders.empty and not done.empty else done
    labels = {SECTIONS[0]: SECTIONS[0], SECTIONS[1]: f"{SECTIONS[1]} ({len(unclaimed)})",
              SECTIONS[2]: "📦 All orders" if current_user["role"] == "ADMIN" else SECTIONS[2],
              SECTIONS[3]: SECTIONS[3], SECTIONS[4]: SECTIONS[4]}
    shown = SECTIONS if current_user["role"] == "ADMIN" else SECTIONS[:4]
    section = st.segmented_control("Section", shown, key="po_section", format_func=lambda x: labels[x],
                                   default=None if "po_section" in st.session_state else SECTIONS[0],
                                   label_visibility="collapsed") or SECTIONS[0]
    if section == SECTIONS[0]:
        _today(db_adapter, orders, alerts)
    elif section == SECTIONS[1]:
        _claim(db_adapter, unclaimed, current_user)
    elif section == SECTIONS[2]:
        _orders(db_adapter, orders, current_user)
    elif section == SECTIONS[3]:
        _profile_section(db_adapter, orders, current_user)
    else:
        _po_progress_admin(db_adapter, orders)


def _open_button(order_id, key):
    if st.button("Open order ➜", key=key, type="primary"):
        st.session_state["po_goto"] = order_id
        st.rerun()


def _today(db, orders, alerts):
    groups = [("calls_overdue", "⏰ Payment calls overdue", "red"), ("calls_today", "📅 Payment calls today", "amber"),
              ("deliveries", "🚚 Delivery in 2 days — ask for the 40% payment", "blue"),
              ("verify", "🧾 POs waiting for verification", "amber")]
    if all(alerts[k].empty for k, _, _ in groups):
        st.success("Nothing due today. 🎉")
        return
    for key, title, tone in groups:
        df = alerts[key]
        if df.empty:
            continue
        st.markdown(f"##### {title} ({len(df)})")
        for _, o in df.iterrows():
            m = current_milestone(o)
            st.markdown(card_html(
                o["client_id"], o["client_name"], o.get("company_name"),
                big=f"{inr(m['balance'])} due" if m else "Fully paid",
                pills=[(stage_label(o), tone), (m["name"], "navy") if m else ("", "grey")],
                fields=[("Order", esc(o["order_id"])), ("Salesperson", esc(o.get("sales_person"))),
                        ("Order value", inr(o["order_value"])), ("Received", inr(o["received"])),
                        ("Next payment call", esc(fmt_12h(o.get("next_collection_date")))),
                        ("Expected delivery", esc(o.get("expected_delivery_date")))],
                links=contact_links(o.get("phone_number"), o.get("email"), str(o["client_name"])),
                note=f"<b>Last remark:</b> {esc(o.get('collection_remarks'))}" if clean(o.get("collection_remarks"), "") else None,
                accent=tone), unsafe_allow_html=True)
            _open_button(o["order_id"], f"po_open_{key}_{o['order_id']}")


# ------------------------------------------------------------------ orders list + profile
def _my_pool(orders, user, key):
    """PO members see their own orders (plus old unowned ones); a toggle shows the team's, view-only."""
    if user["role"] == "ADMIN" or orders.empty:
        return orders
    if st.toggle("Show the whole team's orders (view only)", value=False, key=key):
        return orders
    return orders[(orders["po_owner_id"] == user["employee_id"]) | orders["po_owner_id"].isna()]


def _orders(db, orders, user):
    if orders.empty:
        st.info("No orders yet. Claim a Done deal in 📥 Claim new POs.")
        return
    orders = _my_pool(orders.copy(), user, "po_teamview")
    if orders.empty:
        st.info("You haven't claimed any POs yet. Claim one from 📥 Claim new POs.")
        return
    orders["stage"] = [stage_label(o) for _, o in orders.iterrows()]
    f1, f2, f3 = st.columns([1.5, 1, 1])
    with f1:
        q = st.text_input("Search orders", placeholder="Client ID, name, company, order or PO number", key="po_q").strip().lower()
    with f2:
        stages = st.multiselect("Stage", PO_STAGES, placeholder="All stages", key="po_st")
    with f3:
        sp = st.multiselect("Salesperson", sorted(orders["sales_person"].dropna().unique()), placeholder="All", key="po_sp")
    view = orders
    if q:
        hay = (view["client_id"].astype(str) + " " + view["client_name"].astype(str) + " " + view["company_name"].fillna("").astype(str)
               + " " + view["order_id"].astype(str) + " " + view["purchase_order_no"].fillna("").astype(str)).str.lower()
        view = view[hay.str.contains(q, regex=False)]
    if stages:
        view = view[view["stage"].isin(stages)]
    else:
        view = view[view["stage"] != "Completed"]
        done = int((orders["stage"] == "Completed").sum())
        if done:
            st.caption(f"{done} completed order(s) hidden — pick 'Completed' in Stage to see them.")
    if view.empty:
        st.info("No orders match.")
        return
    order_rank = {s_: i for i, s_ in enumerate(PO_STAGES)}
    view = view.assign(_r=view["stage"].map(order_rank)).sort_values(["_r", "created_at"])
    for _, o in view.head(40).iterrows():
        revs = int(o.get("po_revisions") or 0)
        st.markdown(flat(f"""
          <div class='ic-card' style='--accent:{"#00874A" if o["stage"] == "Completed" else "#184B9C"}; padding:12px 18px;'>
            <div class='ic-head'><div><span class='ic-id'>{esc(o['client_id'])}</span><span class='ic-name'>{esc(o['client_name'])}</span>
            <div class='ic-co'>{esc(o['order_id'])} · {esc(o.get('company_name'), '')} · sales: {esc(o.get('sales_person'))} ·
            PO: {esc(o.get('po_owner_name'), 'unclaimed')} · terms {plan_label(o)}{f" · PO revised {revs}×" if revs else ""}</div></div>
            <div class='ic-right'><div class='ic-big'>{inr(o['received'])} <span style='font-size:13px; color:#475569;'>of {inr(o['order_value'])}</span></div>
            <span class='ic-pill' style='background:#E8EFFB; color:#184B9C;'>{html.escape(o['stage'])}</span></div></div>
            <div style='margin-top:10px;'>{tracker_html(o, compact=True)}</div></div>"""), unsafe_allow_html=True)
        _open_button(o["order_id"], f"po_list_open_{o['order_id']}")


def _profile_section(db, orders, user):
    if orders.empty:
        st.info("No orders yet.")
        return
    pool = _my_pool(orders.copy(), user, "po_teamview_profile")
    pool = pool.assign(stage=[stage_label(o) for _, o in pool.iterrows()])
    want = st.session_state.get("po_open")
    show_done = st.toggle("Include completed orders", value=False, key="po_show_done")
    if not show_done:
        pool = pool[(pool["stage"] != "Completed") | (pool["order_id"] == want)]
    if pool.empty:
        st.info("No open orders. Turn on 'Include completed orders' to see finished ones.")
        return
    labels = {f"{o['client_id']} · {o['client_name']} · {o['order_id']} · {o['stage']}": o["order_id"] for _, o in pool.iterrows()}
    ids = list(labels.values())
    pick = st.selectbox("Order", list(labels.keys()), index=ids.index(want) if want in ids else 0, key="po_pick")
    st.session_state["po_open"] = labels[pick]
    _profile(db, orders[orders["order_id"] == labels[pick]].iloc[0], user)


def _profile(db, o, user):
    oid = o["order_id"]
    readonly = user["role"] != "ADMIN" and str(o.get("po_owner_id")) not in ("None", "nan", user["employee_id"])
    stage = stage_label(o)
    revs = int(o.get("po_revisions") or 0)
    days = po_days(o)
    st.markdown(card_html(
        o["client_id"], o["client_name"], o.get("company_name"), big=inr(o["order_value"]),
        pills=[(stage, "blue"), (f"{paid_percent(o):g}% paid", "green" if paid_percent(o) >= 100 else "amber")],
        fields=[("Order", esc(oid)), ("Salesperson", esc(o.get("sales_person"))), ("Product", f"{esc(o['product'])} × {o['qty']}"),
                ("PO number", esc(o.get("purchase_order_no"))), ("PO date", esc(o.get("po_date"))),
                ("PI number", esc(o.get("pi_number"))),
                ("Delivery period", f"{int(_num(o.get('delivery_days')))} days" if _num(o.get("delivery_days")) else "—"),
                ("Expected delivery", esc(o.get("expected_delivery_date"))), ("PO handled by", esc(o.get("po_owner_name"))),
                ("Payment terms", plan_label(o) + " (advance / dispatch / installation)"),
                ("PO revisions", f"{revs}"), ("PO verified in", f"{days:g} days" if days is not None else "not verified yet"),
                ("Next payment call", esc(fmt_12h(o.get("next_collection_date"))))],
        links=contact_links(o.get("phone_number"), o.get("email"), str(o["client_name"])),
        note=f"<b>Last remark:</b> {esc(o.get('collection_remarks'))}" if clean(o.get("collection_remarks"), "") else None),
        unsafe_allow_html=True)
    st.markdown(f"<div class='saas-card'>{tracker_html(o)}</div>", unsafe_allow_html=True)

    ms = [m for m in milestones(o) if m["percent"] > 0]
    st.dataframe(pd.DataFrame({
        "Stage": [m["name"] for m in ms], "Share": [f"{m['percent']:g}%" for m in ms],
        "Amount": [inr(m["amount"]) for m in ms], "Received": [inr(m["received"]) for m in ms],
        "Balance": [inr(m["balance"]) for m in ms],
        "Due": [f"{m['due'].strftime('%d %b %Y') if m['due'] else '—'} ({m['due_note']})" for m in ms],
        "Status": [m["status"] for m in ms]}), width="stretch", hide_index=True)

    if readonly:
        st.info(f"This order is handled by {o.get('po_owner_name')}. You can view it, but only they can update it.")
        _po_rounds_table(db, oid)
        _history(db, o)
        return
    actions = ["🧾 PO revision", "📞 Log payment call", "💵 Record payment"]
    verified = clean(o.get("po_verified_at"), "") != ""
    if verified and clean(o.get("dispatched_at"), "") == "":
        actions.append("🚚 Material dispatch")
    if clean(o.get("dispatched_at"), "") != "" and clean(o.get("installed_at"), "") == "":
        actions.append("🛠️ Installation")
    actions += ["✏️ Payment terms", "🕘 History"]
    tabs = st.tabs(actions)
    for name, tab in zip(actions, tabs):
        with tab:
            if name.startswith("🧾"):
                _po_revision_tab(db, o, user)
            elif name.startswith("📞"):
                _payment_call_form(db, o, user)
            elif name.startswith("💵"):
                _payment_form(db, o, user)
            elif name.startswith("🚚"):
                st.caption("Mark the material as dispatched. A call for the before-dispatch payment is scheduled automatically.")
                d = st.date_input("Dispatched on", value=today_ist(), key=f"dsp_{oid}", format="DD/MM/YYYY")
                if st.button("Confirm material dispatch", key=f"dspb_{oid}", type="primary"):
                    if mark_dispatched(db, o, f"{d} 10:00:00"):
                        db.update_row("orders", "order_id", oid, {"next_collection_date": f"{d} 11:00:00"})
                        st.toast("Material dispatched. Next payment call scheduled.", icon="🚚")
                        st.rerun()
            elif name.startswith("🛠️"):
                d = st.date_input("Installed on", value=today_ist(), key=f"ins_{oid}", format="DD/MM/YYYY")
                if st.button("Confirm installation", key=f"insb_{oid}", type="primary"):
                    if mark_installed(db, o, f"{d} 10:00:00"):
                        nxt = d + datetime.timedelta(days=1)
                        db.update_row("orders", "order_id", oid, {"next_collection_date": f"{nxt} 11:00:00"})
                        st.toast("Installed. A call for the final payment is scheduled.", icon="🛠️")
                        st.rerun()
            elif name.startswith("✏️"):
                _terms_form(db, o)
            else:
                _history(db, o)


def _terms_inputs(key, current=(50, 40, 10)):
    """Preset or custom payment terms. Returns (advance, dispatch, install) or None if they don't add up to 100."""
    names = list(PAYMENT_TERM_PRESETS.keys())
    match = next((n for n, v in PAYMENT_TERM_PRESETS.items() if v and tuple(v) == tuple(int(x) for x in current)), "Custom")
    preset = st.selectbox("Payment terms agreed with the client *", names, index=names.index(match), key=f"{key}_preset")
    vals = PAYMENT_TERM_PRESETS[preset]
    if vals is None:
        c1, c2, c3 = st.columns(3)
        with c1:
            a = st.number_input("Advance %", 0.0, 100.0, float(current[0]), 5.0, key=f"{key}_a")
        with c2:
            d = st.number_input("Before dispatch %", 0.0, 100.0, float(current[1]), 5.0, key=f"{key}_d")
        with c3:
            i = st.number_input("After installation %", 0.0, 100.0, float(current[2]), 5.0, key=f"{key}_i")
        vals = (a, d, i)
    total = sum(vals)
    st.caption(f"Advance {vals[0]:g}% · before dispatch {vals[1]:g}% · after installation {vals[2]:g}% = {total:g}%")
    return vals if abs(total - 100) < 0.01 else None


def _terms_form(db, o):
    oid = o["order_id"]
    st.caption("Change the payment terms if the client agreed something different. Payments already received stay counted.")
    vals = _terms_inputs(f"terms_{oid}", plan_of(o))
    if st.button("Save payment terms", key=f"terms_save_{oid}", type="primary"):
        if vals is None:
            st.error("The three parts must add up to 100%.")
        elif db.update_row("orders", "order_id", oid, {"plan_advance": vals[0], "plan_dispatch": vals[1],
                                                        "plan_install": vals[2], "updated_at": now_str()}):
            st.toast(f"Payment terms set to {vals[0]:g} / {vals[1]:g} / {vals[2]:g}.", icon="✅")
            st.rerun()
        else:
            st.error(db.last_error)


def _po_rounds_table(db, oid):
    r = db.fetch_all("po_revisions")
    r = r[r["order_id"] == oid] if not r.empty else r
    if r.empty:
        st.caption("No PO checks recorded yet.")
        return r
    rows = []
    for _, x in r.sort_values("round_no").iterrows():
        try:
            mism = ", ".join(json.loads(x["mismatches"] or "[]")) or "—"
        except Exception:
            mism = "—"
        rows.append({"Round": int(x["round_no"]), "Result": x["result"], "What was wrong": mism,
                     "Notes": clean(x.get("notes")), "PO number": clean(x.get("po_number")),
                     "PO amount": inr(x["po_amount"]) if _num(x.get("po_amount")) else "—",
                     "Delivery": f"{int(_num(x.get('delivery_days')))} days" if _num(x.get("delivery_days")) else "—",
                     "Terms": clean(x.get("terms")), "Checked by": clean(x.get("checked_by_name")),
                     "When": fmt_12h(x["checked_at"])})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    return r


def _po_revision_tab(db, o, user):
    oid = o["order_id"]
    rounds = db.fetch_all("po_revisions")
    rounds = rounds[rounds["order_id"] == oid] if not rounds.empty else rounds
    revs = int((rounds["result"] == "Sent for revision").sum()) if not rounds.empty else 0
    verified = clean(o.get("po_verified_at"), "") != ""
    days = po_days(o)
    render_kpi_cards([
        {"label": "PO status", "value": "Verified" if verified else ("Revision requested" if o.get("po_status") == "Revision requested"
                                                                      else "To check"), "tone": "green" if verified else "amber", "icon": "🧾"},
        {"label": "Times sent for revision", "value": revs, "tone": "red" if revs else "blue", "icon": "↩️"},
        {"label": "Time to verify", "value": f"{days:g} days" if days is not None else "—", "tone": "navy", "icon": "⏱️",
         "sub": "from claim to verified"},
    ], columns=3)
    st.markdown("###### PO check history")
    _po_rounds_table(db, oid)

    if verified:
        st.success(f"PO verified on {fmt_12h(o.get('po_verified_at'))}.")
        with st.expander("Client sent a revised PO after verification? Check it again"):
            note = st.text_input("What changed in the revised PO? *", key=f"repo_note_{oid}")
            if st.button("Re-open the PO check", key=f"repo_{oid}"):
                if not note.strip():
                    st.error("Say what changed.")
                else:
                    db.insert_row("po_revisions", {"order_id": oid, "round_no": len(rounds) + 1, "result": "Revised PO received",
                                                   "notes": note.strip(), "checked_by": user["employee_id"], "checked_at": now_str()})
                    db.update_row("orders", "order_id", oid, {"po_verified_at": None, "po_status": "Received", "updated_at": now_str()})
                    st.toast("PO check re-opened. Check the revised PO.", icon="🧾")
                    st.rerun()
        return

    st.markdown(f"###### Check round {len(rounds) + 1}")
    st.markdown("**Payment terms on the PO**")
    terms = _terms_inputs(f"vterms_{oid}", plan_of(o))
    done = checks(o)
    with st.form(f"verify_{oid}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            po_no = st.text_input("PO number *", value=clean(o.get("purchase_order_no"), ""))
            po_date = st.date_input("PO date", value=today_ist(), format="DD/MM/YYYY")
        with c2:
            po_amt = st.number_input("Amount mentioned on the PO (₹) *", min_value=0.0,
                                     value=_num(o.get("po_amount"), _num(o["order_value"])), step=1000.0)
            value = st.number_input("Final order value incl. GST (₹) *", min_value=0.0, value=_num(o["order_value"]), step=1000.0)
        with c3:
            pi_no = st.text_input("Proforma Invoice (PI) number", value=clean(o.get("pi_number"), ""))
            days_in = st.number_input("Delivery period (days) *", min_value=1, max_value=365,
                                      value=int(_num(o.get("delivery_days"), DEFAULT_DELIVERY_DAYS)))
        st.markdown("**Tick every point that is correct on the PO**")
        tc = st.columns(2)
        ticks = {}
        for i, c in enumerate(PO_CHECKS):
            with tc[i % 2]:
                ticks[c] = st.checkbox(c, value=bool(done.get(c)), key=f"chk_{oid}_{i}")
        note = st.text_area("What needs to be revised / remarks", placeholder="e.g. PO shows ₹2,90,000 but quotation is ₹2,94,300; "
                                                                             "delivery written as 15 days instead of 20")
        b1, b2 = st.columns(2)
        with b1:
            ok_btn = st.form_submit_button("✅ All correct — mark PO verified", type="primary")
        with b2:
            rev_btn = st.form_submit_button("↩️ Send to client for PO revision")
        if ok_btn or rev_btn:
            if terms is None:
                st.error("The payment terms must add up to 100%.")
                return
            if not po_no.strip():
                st.error("Enter the PO number.")
                return
            wrong = [c for c, v in ticks.items() if not v]
            stamp = now_str()
            base = {"po_checks": json.dumps(ticks), "purchase_order_no": po_no.strip(), "po_amount": float(po_amt),
                    "order_value": float(value), "pi_amount": float(value), "pi_number": pi_no.strip() or None,
                    "delivery_days": int(days_in), "po_date": str(po_date),
                    "plan_advance": terms[0], "plan_dispatch": terms[1], "plan_install": terms[2],
                    "po_owner_id": o.get("po_owner_id") if clean(o.get("po_owner_id"), "") else user["employee_id"],
                    "updated_at": stamp}
            rnd = {"order_id": oid, "round_no": len(rounds) + 1, "po_number": po_no.strip(), "po_amount": float(po_amt),
                   "delivery_days": int(days_in), "terms": f"{terms[0]:g}/{terms[1]:g}/{terms[2]:g}",
                   "checked_by": user["employee_id"], "checked_at": stamp}
            if ok_btn:
                if wrong:
                    st.error("Not everything is ticked. Tick all points, or send the PO back for revision.")
                    return
                db.insert_row("po_revisions", {**rnd, "result": "Verified", "notes": note.strip() or None})
                base.update({"po_verified_at": stamp, "po_verified_by": user["employee_id"], "po_status": "Verified",
                             "expected_delivery_date": str(today_ist() + datetime.timedelta(days=int(days_in)))})
                if terms[0] > 0:
                    base["next_collection_date"] = f"{today_ist() + datetime.timedelta(days=1)} 11:00:00"
                if db.update_row("orders", "order_id", oid, base):
                    db.log_event("PO_VERIFIED", "orders", oid, None, {"round": rnd["round_no"]})
                    st.toast(f"PO verified. Delivery expected {base['expected_delivery_date']}."
                             + (f" Collect the {terms[0]:g}% advance." if terms[0] else ""), icon="✅")
                    st.rerun()
                st.error(db.last_error)
            else:
                if not wrong and not note.strip():
                    st.error("Untick what is wrong, or write what needs revising.")
                    return
                db.insert_row("po_revisions", {**rnd, "result": "Sent for revision", "mismatches": json.dumps(wrong),
                                               "notes": note.strip() or None})
                base.update({"po_status": "Revision requested",
                             "collection_remarks": f"{today_ist().strftime('%d %b')}: PO sent back — "
                                                   + "; ".join(wrong + ([note.strip()] if note.strip() else []))})
                if db.update_row("orders", "order_id", oid, base):
                    db.log_event("PO_REVISION_REQUESTED", "orders", oid, None, {"round": rnd["round_no"], "wrong": wrong})
                    st.toast(f"PO sent back for revision (round {rnd['round_no']}). Check the revised PO when it arrives.", icon="↩️")
                    st.rerun()
                st.error(db.last_error)


def _payment_call_form(db, o, user):
    oid = o["order_id"]
    m = current_milestone(o)
    if m is None:
        st.success("This order is fully paid.")
        return
    overdue = bool(m["due"] and m["due"] < today_ist())
    st.caption(f"Calling for: **{m['name']}** · balance {inr(m['balance'])} · due "
               f"{m['due'].strftime('%d %b') if m['due'] else '—'}" + (" · **overdue — give the reason for the delay**" if overdue else ""))
    with st.form(f"paycall_{oid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            outcome = st.selectbox("Call outcome *", ["Choose..."] + PAYMENT_OUTCOMES)
            reason = st.selectbox("Reason for delay" + (" *" if overdue else ""), ["—"] + DELAY_REASONS)
        with c2:
            promised = st.date_input("Client promised to pay on", value=None, format="DD/MM/YYYY")
            notes = st.text_input("Notes *", placeholder="e.g. Accounts head will release on Friday")
        d1, d2 = st.columns(2)
        with d1:
            nd = st.date_input("Next payment call", value=today_ist() + datetime.timedelta(days=2), format="DD/MM/YYYY")
        with d2:
            nt = time_12h("Call time", key=f"pct_{oid}", default=datetime.time(11, 0))
        if st.form_submit_button("Save payment call", type="primary"):
            if outcome == "Choose..." or not notes.strip():
                st.error("Choose the outcome and add a note.")
                return
            if (overdue or outcome == "Payment delayed") and outcome != "Payment received" and reason == "—":
                st.error("This payment is late — choose the reason for the delay.")
                return
            nxt = datetime.datetime.combine(nd, nt)
            if nxt <= now_ist().replace(tzinfo=None):
                st.error("Pick a next call time later than now.")
                return
            stamp = now_str()
            db.insert_row("payment_followups", {
                "order_id": oid, "milestone": m["name"], "logged_by": user["employee_id"], "outcome": outcome,
                "promised_date": str(promised) if promised else None, "delay_reason": None if reason == "—" else reason,
                "notes": notes.strip(), "next_call_at": nxt.strftime("%Y-%m-%d %H:%M:%S"), "logged_at": stamp})
            remark = f"{today_ist().strftime('%d %b')}: {outcome}" + (f" ({reason})" if reason != "—" else "") + f" — {notes.strip()}"
            if db.update_row("orders", "order_id", oid, {"next_collection_date": nxt.strftime("%Y-%m-%d %H:%M:%S"),
                                                        "collection_remarks": remark, "updated_at": stamp}):
                st.toast(f"Payment call saved. Next call {nxt.strftime('%d %b, %I:%M %p')}.", icon="✅")
                st.rerun()
            else:
                st.error(db.last_error)


def _payment_form(db, o, user):
    oid = o["order_id"]
    m = current_milestone(o)
    if m is None:
        st.success("This order is fully paid.")
        return
    with st.form(f"popay_{oid}", clear_on_submit=True):
        st.caption(f"Next due: **{m['name']}** — {inr(m['balance'])}")
        c1, c2 = st.columns(2)
        with c1:
            amount = st.number_input("Amount received (₹) *", min_value=0.0, value=float(m["balance"]), step=1000.0)
            mode = st.selectbox("Mode *", PAYMENT_MODES)
        with c2:
            paid_on = st.date_input("Received on *", value=today_ist(), format="DD/MM/YYYY")
            ref = st.text_input("UTR / cheque no.")
        if st.form_submit_button("Save payment", type="primary"):
            balance = float(o["order_value"] or 0) - float(o["received"] or 0)
            if amount <= 0 or amount > balance + 1:
                st.error(f"Enter an amount between ₹1 and the order balance ({inr(balance)}).")
                return
            if db.insert_row("payments", {"payment_id": db.next_payment_id(), "order_id": oid, "amount": float(amount),
                                          "paid_on": str(paid_on), "mode": mode, "reference": ref.strip() or None,
                                          "notes": f"{m['name']}", "recorded_by": user["employee_id"],
                                          "created_at": now_str()}) is None:
                st.error(db.last_error)
                return
            new_received = float(o["received"] or 0) + float(amount)
            status = payment_status(o["order_value"], new_received)
            updates = {"payment_status": status, "updated_at": now_str()}
            nxt_m = current_milestone({**o.to_dict(), "received": new_received})
            if nxt_m is None:
                updates["next_collection_date"] = None
            db.update_row("orders", "order_id", oid, updates)
            db.insert_row("payment_followups", {"order_id": oid, "milestone": m["name"], "logged_by": user["employee_id"],
                                                "outcome": "Payment received", "notes": f"{inr(amount)} via {mode}",
                                                "logged_at": now_str()})
            st.toast(f"{inr(amount)} recorded for {o['client_name']}." + (" Order fully paid! 🎉" if nxt_m is None
                     else f" Next: {nxt_m['name']}."), icon="✅")
            st.rerun()


def _history(db, o):
    fu = db.fetch_all("payment_followups")
    fu = fu[fu["order_id"] == o["order_id"]] if not fu.empty else fu
    pays = db.fetch_all("payments")
    pays = pays[pays["order_id"] == o["order_id"]] if not pays.empty else pays
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Payment calls")
        if fu.empty:
            st.caption("No payment calls yet.")
        else:
            f = fu.sort_values("logged_at", ascending=False)
            st.dataframe(pd.DataFrame({"When": f["logged_at"].map(fmt_12h), "Stage": f["milestone"], "Outcome": f["outcome"],
                                       "Delay reason": f["delay_reason"].fillna("—"), "Promised": f["promised_date"].fillna("—"),
                                       "Notes": f["notes"], "By": f["logged_by_name"]}), width="stretch", hide_index=True)
    with c2:
        st.markdown("###### Payments")
        if pays.empty:
            st.caption("No payments yet.")
        else:
            st.dataframe(pd.DataFrame({"Date": pays["paid_on"], "Amount": pays["amount"].map(inr), "Mode": pays["mode"],
                                       "Ref": pays["reference"].fillna("—"), "For": pays["notes"].fillna("—")}),
                         width="stretch", hide_index=True)


# ------------------------------------------------------------------ claim (first come, first served)
def _claim(db, unclaimed, user):
    if unclaimed.empty:
        st.success("Every Done deal already has a PO owner. New ones appear here as soon as a deal is marked Done.")
        return
    st.caption("Whoever claims a PO first owns it: it counts in their report and only they can update it.")
    lq = latest_quotes(db.fetch_all("quotations_master"))
    price = dict(zip(lq["lead_id"], lq["qut_amount"])) if not lq.empty else {}
    ref = dict(zip(lq["lead_id"], lq["quotation_ref"])) if not lq.empty else {}
    qid = dict(zip(lq["lead_id"], lq["quotation_id"])) if not lq.empty else {}
    for _, r in unclaimed.sort_values("closed_at", ascending=False).iterrows():
        quoted = float(price.get(r["lead_id"], 0) or 0)
        st.markdown(card_html(
            r["client_id"], r["client_name"], r.get("company_name"), big=inr(quoted) if quoted else None,
            pills=[("Done — waiting for PO", "green")],
            fields=[("Product", f"{esc(r['product'])} × {r['qty']}"), ("Quotation", esc(ref.get(r["lead_id"]))),
                    ("Salesperson", esc(r.get("assigned_salesperson"))), ("Done on", esc(fmt_12h(r.get("closed_at"))))],
            links=contact_links(r.get("phone_number"), r.get("email"), str(r["client_name"])), accent="green"),
            unsafe_allow_html=True)
        if user["role"] == "PO" and st.button(f"🙋 Claim PO for {r['client_id']}", key=f"po_claim_{r['lead_id']}", type="primary"):
            stamp = now_str()
            oid = db.insert_row("orders", {
                "order_id": db.next_order_id(), "lead_id": int(r["lead_id"]), "client_id": r["client_id"],
                "quotation_id": qid.get(r["lead_id"]), "order_value": round(quoted * 1.18, 0), "pi_amount": round(quoted * 1.18, 0),
                "payment_status": "Pending", "po_owner_id": user["employee_id"], "po_claimed_at": stamp, "po_status": "Received",
                "plan_advance": 50, "plan_dispatch": 40, "plan_install": 10,
                "created_by": user["employee_id"], "created_at": stamp})
            if oid is None:
                st.toast("Someone else claimed this PO a moment ago — it is theirs now.", icon="⚠️")
            else:
                db.log_event("PO_CLAIMED", "orders", oid, None, {"po_owner_id": user["employee_id"]})
                st.session_state["po_goto"] = oid
                st.toast(f"{r['client_id']} is yours. Enter the PO details and check them.", icon="🙋")
            st.rerun()


# ------------------------------------------------------------------ team (admin)
def _po_progress_admin(db, orders):
    import plotly.express as px
    if orders.empty:
        st.info("No orders yet.")
        return
    o = orders.copy()
    o["stage"] = [stage_label(x) for _, x in o.iterrows()]
    o["paid_pct"] = [paid_percent(x) for _, x in o.iterrows()]
    o["po_days"] = [po_days(x) for _, x in o.iterrows()]
    verified_days = o["po_days"].dropna()
    render_kpi_cards([
        {"label": "Orders", "value": len(o), "icon": "📦", "tone": "blue", "sub": f"{int((o['stage'] == 'Completed').sum())} completed"},
        {"label": "POs waiting to verify", "value": int(o["stage"].isin(["PO to verify", "PO revision pending"]).sum()), "icon": "🧾",
         "tone": "amber", "sub": f"{int((o['stage'] == 'PO revision pending').sum())} with the client for revision"},
        {"label": "PO revisions requested", "value": int(o["po_revisions"].fillna(0).sum()), "icon": "↩️", "tone": "red"},
        {"label": "Average time to verify a PO", "value": f"{verified_days.mean():.1f} days" if len(verified_days) else "—",
         "icon": "⏱️", "tone": "navy"},
        {"label": "Money received", "value": f"{o['received'].sum() / o['order_value'].sum() * 100:.0f}%" if o["order_value"].sum() else "—",
         "icon": "💵", "tone": "green", "sub": f"{inr(o['received'].sum())} of {inr(o['order_value'].sum())}"},
    ])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Orders by stage")
        sc = o["stage"].value_counts().reindex(PO_STAGES).fillna(0).astype(int).reset_index()
        sc.columns = ["Stage", "Orders"]
        fig = px.bar(sc, x="Orders", y="Stage", orientation="h", text="Orders", color_discrete_sequence=["#184B9C"],
                     category_orders={"Stage": PO_STAGES})
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(height=330, margin=dict(t=10, b=10, l=10, r=30), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          xaxis_title="", yaxis_title="")
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.markdown("###### PO team: speed and revisions")
        emp = db.fetch_all("employees")
        team = emp[(emp["role"] == "PO") & (emp["is_active"] == 1)]
        pays = db.fetch_all("payments")
        fu = db.fetch_all("payment_followups")
        month = str(today_ist())[:7]
        rows = []
        for _, e in team.iterrows():
            mine = o[o["po_owner_id"] == e["employee_id"]]
            p_ = pays[pays["order_id"].isin(mine["order_id"])] if not pays.empty else pays
            f_ = fu[(fu["logged_by"] == e["employee_id"]) & (fu["logged_at"].astype(str).str[:7] == month)] if not fu.empty else fu
            d_ = mine["po_days"].dropna()
            rows.append({"PO member": e["full_name"], "Claimed": len(mine), "Verified": int(mine["po_verified_at"].notna().sum()),
                         "Revisions requested": int(mine["po_revisions"].fillna(0).sum()),
                         "Avg days to verify": round(d_.mean(), 1) if len(d_) else None,
                         "Completed": int((mine["stage"] == "Completed").sum()),
                         "Collected this month": inr(p_[p_["paid_on"].astype(str).str[:7] == month]["amount"].sum()) if len(p_) else "₹0",
                         "Payment calls (month)": len(f_)})
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.info("No PO & PI team members yet.")
    st.markdown("###### Every order")
    tbl = o.assign(_r=o["stage"].map({s_: i for i, s_ in enumerate(PO_STAGES)})).sort_values(["_r", "created_at"])
    st.dataframe(pd.DataFrame({
        "Client": tbl["client_id"] + " · " + tbl["client_name"], "Order": tbl["order_id"], "PO member": tbl["po_owner_name"].fillna("unclaimed"),
        "Stage": tbl["stage"], "Paid %": tbl["paid_pct"], "Order value": tbl["order_value"].map(inr), "Received": tbl["received"].map(inr),
        "Terms": [plan_label(x) for _, x in tbl.iterrows()], "PO revisions": tbl["po_revisions"].fillna(0).astype(int),
        "Days to verify": tbl["po_days"], "Salesperson": tbl["sales_person"].fillna("—")}),
        width="stretch", hide_index=True,
        column_config={"Paid %": st.column_config.ProgressColumn("Paid %", min_value=0, max_value=100, format="%.0f%%")})


def render_po_progress(db_adapter, current_user):
    """Admin: PO progress across the whole PO & PI team."""
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    page_title("PO progress", "Every order's PO check, payment progress and the PO team's speed.")
    _po_progress_admin(db_adapter, db_adapter.fetch_all("orders"))
