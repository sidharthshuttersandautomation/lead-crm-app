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
from utils.payment_plan import (checks, current_milestone, milestones, payment_alerts, plan_label, plan_of, stage_label,
                                tracker_html)
from utils.payments import payment_status
from utils.time_utils import now_ist, now_str, today_ist

SECTIONS = ["📅 Today", "📥 Claim new POs", "📦 My orders", "👥 Team"]


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
        st.session_state["po_section"] = SECTIONS[2]
        st.session_state["po_open"] = st.session_state.pop("po_goto")
        st.session_state.pop("po_pick", None)
    leads = db_adapter.fetch_all("leads_master")
    done = leads[leads["final_status"] == STAGE_WON] if not leads.empty else leads
    unclaimed = done[~done["lead_id"].isin(orders["lead_id"])] if not orders.empty and not done.empty else done
    labels = {SECTIONS[0]: SECTIONS[0], SECTIONS[1]: f"{SECTIONS[1]} ({len(unclaimed)})",
              SECTIONS[2]: "📦 All orders" if current_user["role"] == "ADMIN" else SECTIONS[2], SECTIONS[3]: SECTIONS[3]}
    shown = SECTIONS if current_user["role"] == "ADMIN" else SECTIONS[:3]
    section = st.segmented_control("Section", shown, key="po_section", format_func=lambda x: labels[x],
                                   default=None if "po_section" in st.session_state else SECTIONS[0],
                                   label_visibility="collapsed") or SECTIONS[0]
    if section == SECTIONS[0]:
        _today(db_adapter, orders, alerts)
    elif section == SECTIONS[1]:
        _claim(db_adapter, unclaimed, current_user)
    elif section == SECTIONS[2]:
        _orders(db_adapter, orders, current_user)
    else:
        _team(db_adapter, orders)


# ------------------------------------------------------------------ today
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
def _orders(db, orders, user):
    if orders.empty:
        st.info("No orders yet. Create one from a Done deal in 🆕 New order from PO.")
        return
    orders = orders.copy()
    if user["role"] != "ADMIN":
        team_view = st.toggle("Show the whole team's orders (view only)", value=False, key="po_teamview")
        if not team_view:
            orders = orders[(orders["po_owner_id"] == user["employee_id"]) | orders["po_owner_id"].isna()]
        if orders.empty:
            st.info("You haven't claimed any POs yet. Claim one from 📥 Claim new POs.")
            return
    orders["stage"] = [stage_label(o) for _, o in orders.iterrows()]
    f1, f2, f3 = st.columns([1.5, 1, 1])
    with f1:
        q = st.text_input("Search orders", placeholder="Client ID, name, company, order or PO number", key="po_q").strip().lower()
    with f2:
        stages = st.multiselect("Stage", sorted(orders["stage"].unique()), placeholder="All stages", key="po_st")
    with f3:
        sp = st.multiselect("Salesperson", sorted(orders["sales_person"].dropna().unique()), placeholder="All", key="po_sp")
    view = orders
    if q:
        hay = (view["client_id"].astype(str) + " " + view["client_name"].astype(str) + " " + view["company_name"].fillna("").astype(str)
               + " " + view["order_id"].astype(str) + " " + view["purchase_order_no"].fillna("").astype(str)).str.lower()
        view = view[hay.str.contains(q, regex=False)]
    if stages:
        view = view[view["stage"].isin(stages)]
    if sp:
        view = view[view["sales_person"].isin(sp)]

    rows = "".join(flat(f"""
      <div class='ic-card' style='--accent:{"#00A859" if o["stage"] == "Fully paid" else "#184B9C"}; padding:12px 18px;'>
        <div class='ic-head'><div><span class='ic-id'>{esc(o['client_id'])}</span><span class='ic-name'>{esc(o['client_name'])}</span>
        <div class='ic-co'>{esc(o['order_id'])} · {esc(o.get('company_name'), '')} · sales: {esc(o.get('sales_person'))} ·
        PO: {esc(o.get('po_owner_name'), 'unclaimed')} · terms {plan_label(o)}</div></div>
        <div class='ic-right'><div class='ic-big'>{inr(o['received'])} <span style='font-size:13px; color:#64748B;'>of {inr(o['order_value'])}</span></div>
        <span class='ic-pill' style='background:#E8EFFB; color:#184B9C;'>{html.escape(o['stage'])}</span></div></div>
        <div style='margin-top:10px;'>{tracker_html(o, compact=True)}</div></div>""") for _, o in view.head(40).iterrows())
    st.markdown(rows or "<div class='saas-card'>No orders match.</div>", unsafe_allow_html=True)

    st.markdown("##### Order profile")
    labels = {f"{o['client_id']} · {o['client_name']} · {o['order_id']}": o["order_id"] for _, o in view.iterrows()}
    if not labels:
        return
    ids = list(labels.values())
    want = st.session_state.get("po_open")
    pick = st.selectbox("Order", list(labels.keys()), index=ids.index(want) if want in ids else 0, key="po_pick")
    order = orders[orders["order_id"] == labels[pick]].iloc[0]
    _profile(db, order, user)


def _profile(db, o, user):
    oid = o["order_id"]
    readonly = user["role"] != "ADMIN" and o.get("po_owner_id") not in (None, user["employee_id"]) \
        and str(o.get("po_owner_id")) != "nan"
    st.markdown(card_html(
        o["client_id"], o["client_name"], o.get("company_name"), big=inr(o["order_value"]),
        pills=[(stage_label(o), "blue"), (payment_status(o["order_value"], o["received"]), "green")],
        fields=[("Order", esc(oid)), ("Salesperson", esc(o.get("sales_person"))), ("Product", f"{esc(o['product'])} × {o['qty']}"),
                ("PO number", esc(o.get("purchase_order_no"))), ("PO date", esc(o.get("po_date"))),
                ("PI number", esc(o.get("pi_number"))), ("Delivery period", f"{int(o['delivery_days'])} days" if pd.notna(o.get("delivery_days")) else "—"),
                ("Expected delivery", esc(o.get("expected_delivery_date"))), ("PO handled by", esc(o.get("po_owner_name"))),
                ("Payment terms", plan_label(o) + " (advance / dispatch / installation)"),
                ("Next payment call", esc(fmt_12h(o.get("next_collection_date"))))],
        links=contact_links(o.get("phone_number"), o.get("email"), str(o["client_name"])),
        note=f"<b>Last remark:</b> {esc(o.get('collection_remarks'))}" if clean(o.get("collection_remarks"), "") else None),
        unsafe_allow_html=True)
    st.markdown(f"<div class='saas-card'>{tracker_html(o)}</div>", unsafe_allow_html=True)

    ms = [m for m in milestones(o) if m["percent"] > 0]
    st.dataframe(pd.DataFrame({
        "Stage": [m["name"] for m in ms], "Share": [f"{m['percent']}%" for m in ms],
        "Amount": [inr(m["amount"]) for m in ms], "Received": [inr(m["received"]) for m in ms],
        "Balance": [inr(m["balance"]) for m in ms],
        "Due": [f"{m['due'].strftime('%d %b %Y') if m['due'] else '—'} ({m['due_note']})" for m in ms],
        "Status": [m["status"] for m in ms]}), width="stretch", hide_index=True)

    actions = []
    if not o.get("po_verified_at"):
        actions.append("✅ Verify PO")
    actions += ["📞 Log payment call", "💵 Record payment"]
    if o.get("po_verified_at") and not o.get("dispatched_at"):
        actions.append("🚚 Mark dispatched")
    if o.get("dispatched_at") and not o.get("installed_at"):
        actions.append("🛠️ Mark installed")
    actions.append("✏️ Payment terms")
    actions.append("🕘 History")
    if readonly:
        st.info(f"This order is handled by {o.get('po_owner_name')}. You can view it, but only they can update it.")
        _history(db, o)
        return
    tabs = st.tabs(actions)
    for name, tab in zip(actions, tabs):
        with tab:
            if name.startswith("✅"):
                _verify_form(db, o, user)
            elif name.startswith("📞"):
                _payment_call_form(db, o, user)
            elif name.startswith("💵"):
                _payment_form(db, o, user)
            elif name.startswith("🚚"):
                d = st.date_input("Dispatched on", value=today_ist(), key=f"dsp_{oid}", format="DD/MM/YYYY")
                if st.button("Confirm dispatch", key=f"dspb_{oid}", type="primary"):
                    if mark_dispatched(db, o, f"{d} 10:00:00"):
                        db.update_row("orders", "order_id", oid, {"next_collection_date": f"{d} 11:00:00"})
                        st.toast("Marked dispatched. A call for the 40% payment is scheduled.", icon="🚚")
                        st.rerun()
            elif name.startswith("🛠️"):
                d = st.date_input("Installed on", value=today_ist(), key=f"ins_{oid}", format="DD/MM/YYYY")
                if st.button("Confirm installation", key=f"insb_{oid}", type="primary"):
                    if mark_installed(db, o, f"{d} 10:00:00"):
                        nxt = d + datetime.timedelta(days=1)
                        db.update_row("orders", "order_id", oid, {"next_collection_date": f"{nxt} 11:00:00"})
                        st.toast("Marked installed. A call for the final 10% is scheduled.", icon="🛠️")
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


def _verify_form(db, o, user):
    oid = o["order_id"]
    done = checks(o)
    st.markdown("**Payment terms**")
    terms = _terms_inputs(f"vterms_{oid}", plan_of(o))
    with st.form(f"verify_{oid}"):
        st.markdown("**Check the client's Process Order against the quotation**")
        ticks = {c: st.checkbox(c, value=bool(done.get(c)), key=f"chk_{oid}_{i}") for i, c in enumerate(PO_CHECKS)}
        c1, c2, c3 = st.columns(3)
        with c1:
            po_no = st.text_input("PO number *", value=clean(o.get("purchase_order_no"), ""))
            value = st.number_input("Final order value incl. GST (₹) *", min_value=0.0, value=_num(o["order_value"]), step=1000.0)
            po_amt = st.number_input("Amount written on the PO (₹)", min_value=0.0,
                                     value=_num(o.get("po_amount"), _num(o["order_value"])), step=1000.0)
        with c2:
            pi_no = st.text_input("Proforma Invoice (PI) number", value=clean(o.get("pi_number"), ""))
            days = st.number_input("Delivery period (days) *", min_value=1, max_value=365,
                                   value=int(_num(o.get("delivery_days"), DEFAULT_DELIVERY_DAYS)))
        with c3:
            po_date = st.date_input("PO date", value=today_ist(), format="DD/MM/YYYY")
            note = st.text_input("Mismatch / remarks")
        if st.form_submit_button("Save check", type="primary"):
            if terms is None:
                st.error("The payment terms must add up to 100%.")
                return
            all_ok = all(ticks.values())
            stamp = now_str()
            updates = {"po_checks": json.dumps(ticks), "purchase_order_no": po_no.strip() or None, "po_amount": float(po_amt),
                       "order_value": float(value), "pi_amount": float(value),
                       "plan_advance": terms[0], "plan_dispatch": terms[1], "plan_install": terms[2],
                       "pi_number": pi_no.strip() or None, "delivery_days": int(days), "po_date": str(po_date),
                       "po_owner_id": o.get("po_owner_id") or user["employee_id"], "updated_at": stamp}
            if note.strip():
                updates["collection_remarks"] = f"{today_ist().strftime('%d %b')}: PO check — {note.strip()}"
            if all_ok:
                if not po_no.strip():
                    st.error("Enter the PO number to verify the PO.")
                    return
                updates.update({"po_verified_at": stamp, "po_verified_by": user["employee_id"],
                                "expected_delivery_date": str(today_ist() + datetime.timedelta(days=int(days))),
                                "next_collection_date": f"{today_ist() + datetime.timedelta(days=1)} 11:00:00"})
            if db.update_row("orders", "order_id", oid, updates):
                if all_ok:
                    db.log_event("PO_VERIFIED", "orders", oid, None, {"delivery_days": int(days)})
                    st.toast(f"PO verified. Delivery expected {updates['expected_delivery_date']}. "
                             f"Collect the {terms[0]:g}% advance." if terms[0] else "PO verified.", icon="✅")
                else:
                    st.toast("Saved. The PO stays unverified until every check is ticked.", icon="📝")
                st.rerun()
            else:
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
                "payment_status": "Pending", "po_owner_id": user["employee_id"], "po_claimed_at": stamp,
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
def _team(db, orders):
    emp = db.fetch_all("employees")
    team = emp[(emp["role"] == "PO") & (emp["is_active"] == 1)]
    if team.empty:
        st.info("No PO & PI team members yet. Add them in Secrets or Users with the role PO.")
        return
    pays = db.fetch_all("payments")
    fu = db.fetch_all("payment_followups")
    month = str(today_ist())[:7]
    rows = []
    for _, e in team.iterrows():
        mine = orders[orders["po_owner_id"] == e["employee_id"]] if not orders.empty else orders
        due_now, overdue = 0.0, 0
        for _, o in mine.iterrows():
            m = current_milestone(o)
            if m and m["due"] and m["due"] <= today_ist():
                due_now += m["balance"]
                overdue += m["due"] < today_ist()
        p = pays[pays["order_id"].isin(mine["order_id"])] if not pays.empty and not mine.empty else pays.iloc[0:0] if not pays.empty else pays
        f = fu[(fu["logged_by"] == e["employee_id"]) & (fu["logged_at"].astype(str).str[:7] == month)] if not fu.empty else fu
        rows.append({"PO member": e["full_name"], "Orders claimed": len(mine),
                     "PO verified": int(mine["po_verified_at"].notna().sum()) if len(mine) else 0,
                     "Fully paid": sum(1 for _, o in mine.iterrows() if current_milestone(o) is None) if len(mine) else 0,
                     "Collected this month": float(p[p["paid_on"].astype(str).str[:7] == month]["amount"].sum()) if len(p) else 0.0,
                     "Due now": due_now, "Overdue orders": overdue,
                     "Payment calls this month": len(f)})
    df = pd.DataFrame(rows)
    show = df.copy()
    for c in ("Collected this month", "Due now"):
        show[c] = show[c].map(inr)
    st.dataframe(show, width="stretch", hide_index=True)
    unowned = orders[orders["po_owner_id"].isna()] if not orders.empty else orders
    if len(unowned):
        st.caption(f"{len(unowned)} older order(s) have no PO owner yet; every PO member can see them.")
