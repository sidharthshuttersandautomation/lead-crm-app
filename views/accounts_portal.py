"""
views/accounts_portal.py - Sales & collections (Accounts department and admins).
Total sales booked, money received, balance to collect, party-wise outstanding,
payment recording and collection follow-ups.
"""
import datetime
import html

import pandas as pd
import plotly.express as px
import streamlit as st

from components.contact import contact_links
from components.kpi_cards import page_title, render_kpi_cards
from config.settings import AGEING_BUCKETS, PAYMENT_MODES
from utils.metrics import inr
from utils.payments import enrich_orders, monthly_sales_vs_collections, payment_status
from utils.time_utils import now_str, today_ist

BLUE, GREEN, RED, AMBER = "#184B9C", "#00A859", "#BE123C", "#B45309"
TEAL_C = "#0E7490"
import plotly.graph_objects as go
AGE_COLORS = {"0–30 days": "#7CC4A3", "31–60 days": "#F2B84B", "61–90 days": "#E07B39", "90+ days": RED}


def _sum_since(df, date_col, value_col, start, end=None):
    if df.empty:
        return 0.0
    d = df[date_col].astype(str).str[:10]
    mask = d > str(start) if end is None else (d > str(start)) & (d <= str(end))
    return float(df.loc[mask, value_col].sum())


def render_collections_portal(db_adapter, current_user):
    is_admin = current_user["role"] == "ADMIN"
    page_title("Sales & collections" if is_admin else "Collections",
               "What's being sold, what's received and who still has to pay.")
    if is_admin:
        t_over, t_coll = st.tabs(["📊 Sales overview", "💰 Collections"])
        with t_over:
            _sales_overview(db_adapter)
        with t_coll:
            _collections(db_adapter, current_user)
    else:
        _collections(db_adapter, current_user)


def _sales_overview(db):
    from config.settings import REPORTING_WINDOWS, STAGE_PROBABILITY
    from utils.metrics import filter_by_window, latest_quotes, open_leads
    from utils.payment_plan import current_milestone, stage_label
    from utils.time_utils import window_start
    window = st.segmented_control("Period", list(REPORTING_WINDOWS.keys()), default="This month", key="so_window") or "This month"
    start = window_start(REPORTING_WINDOWS[window])
    L = db.fetch_all("leads_master")
    if L.empty:
        st.info("No leads yet.")
        return
    lq = latest_quotes(db.fetch_all("quotations_master"))
    price = dict(zip(lq["lead_id"], lq["qut_amount"])) if not lq.empty else {}
    status = dict(zip(lq["lead_id"], lq["quotation_status"])) if not lq.empty else {}
    O = enrich_orders(db.fetch_all("orders"))
    P = db.fetch_all("payments")
    done_p = filter_by_window(L[L["final_status"] == "Done"], "closed_at", start)
    active = open_leads(L)
    pipeline = sum(price.get(i, 0) for i in active["lead_id"] if status.get(i) == "Approved")
    expected = sum(price.get(i, 0) * STAGE_PROBABILITY.get(st_, 0) for i, st_ in zip(active["lead_id"], active["final_status"]))
    booked = float(filter_by_window(O, "created_at", start)["order_value"].sum()) if not O.empty else 0.0
    collected = float(filter_by_window(P, "paid_on", start)["amount"].sum()) if not P.empty else 0.0
    outstanding = float(O["balance"].clip(lower=0).sum()) if not O.empty else 0.0

    render_kpi_cards([
        {"label": f"Deals done ({window.lower()})", "value": len(done_p), "icon": "🏆", "tone": "green",
         "sub": inr(sum(price.get(i, 0) for i in done_p["lead_id"]))},
        {"label": "Open pipeline (approved quotes)", "value": inr(pipeline), "icon": "💼", "tone": "blue",
         "sub": f"{len(active)} open leads"},
        {"label": "Expected to convert", "value": inr(expected), "icon": "🔮", "tone": "teal", "help": "Open value × stage probability"},
    ], columns=3)
    render_kpi_cards([
        {"label": f"Orders booked ({window.lower()})", "value": inr(booked), "icon": "🧾", "tone": "navy"},
        {"label": f"Collected ({window.lower()})", "value": inr(collected), "icon": "💵", "tone": "green"},
        {"label": "Outstanding on all orders", "value": inr(outstanding), "icon": "⏳", "tone": "red"},
    ], columns=3)

    # ---------------- per salesperson
    st.markdown("##### By salesperson")
    rows = []
    for sp, g in L.groupby(L["assigned_salesperson"].fillna("N/A")):
        g_open = g[~g["final_status"].isin(["Done", "Cancled"])]
        g_done = filter_by_window(g[g["final_status"] == "Done"], "closed_at", start)
        g_closed = g[g["final_status"].isin(["Done", "Cancled"])]
        g_orders = O[O["lead_id"].isin(g["lead_id"])] if not O.empty else O
        rows.append({"Salesperson": sp, "Open leads": len(g_open),
                     "Open pipeline": sum(price.get(i, 0) for i in g_open["lead_id"] if status.get(i) == "Approved"),
                     f"Done ({window.lower()})": len(g_done), "Done value": sum(price.get(i, 0) for i in g_done["lead_id"]),
                     "Win rate %": round((g_closed["final_status"] == "Done").mean() * 100) if len(g_closed) else None,
                     "Collected": float(g_orders["received"].sum()) if not g_orders.empty else 0.0,
                     "Outstanding": float(g_orders["balance"].clip(lower=0).sum()) if not g_orders.empty else 0.0})
    sp = pd.DataFrame(rows).sort_values("Done value", ascending=False)
    show = sp.copy()
    for c in ("Open pipeline", "Done value", "Collected", "Outstanding"):
        show[c] = show[c].map(inr)
    st.dataframe(show, width="stretch", hide_index=True,
                 column_config={"Win rate %": st.column_config.ProgressColumn("Win rate %", min_value=0, max_value=100, format="%d%%")})

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Pipeline vs done value by salesperson")
        sp2 = sp[(sp["Open pipeline"] > 0) | (sp["Done value"] > 0)].sort_values("Open pipeline")
        fig = go.Figure()
        fig.add_bar(y=sp2["Salesperson"], x=sp2["Open pipeline"], name="Open pipeline", orientation="h", marker_color=BLUE)
        fig.add_bar(y=sp2["Salesperson"], x=sp2["Done value"], name="Done value", orientation="h", marker_color=GREEN)
        fig.update_traces(hovertemplate="%{y}: ₹%{x:,.0f}<extra>%{fullData.name}</extra>")
        fig.update_layout(barmode="group", height=90 + 60 * max(1, len(sp2)), margin=dict(t=10, b=10, l=10, r=10),
                          legend=dict(orientation="h", y=1.1), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.markdown("###### Where the orders are (payment stages)")
        if O.empty:
            st.info("No orders yet — they start in 🧾 PO & payments when a deal is Done.")
        else:
            stg = []
            for _, o in O.iterrows():
                m = current_milestone(o)
                stg.append({"Stage": stage_label(o), "Due": m["balance"] if m else 0.0})
            sdf = pd.DataFrame(stg).groupby("Stage").agg(Orders=("Due", "size"), Due=("Due", "sum")).reset_index()
            fig = px.bar(sdf.sort_values("Orders"), x="Orders", y="Stage", orientation="h",
                         text=[f"{n} · {inr(d)} due" for n, d in zip(sdf.sort_values("Orders")["Orders"], sdf.sort_values("Orders")["Due"])],
                         color_discrete_sequence=[TEAL_C])
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(height=90 + 50 * len(sdf), margin=dict(t=10, b=10, l=10, r=90), xaxis_range=[0, sdf["Orders"].max() * 1.8],
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", yaxis_title="", xaxis_title="")
            st.plotly_chart(fig, width="stretch")

    st.markdown("##### Coming up in the next 7 days")
    soon = str(today_ist() + datetime.timedelta(days=7))
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("###### 🚚 Expected deliveries")
        d = O[O["expected_delivery_date"].notna() & O["dispatched_at"].isna()
              & (O["expected_delivery_date"].astype(str) <= soon)] if not O.empty else O
        if d.empty:
            st.caption("None.")
        else:
            st.dataframe(pd.DataFrame({"Client": d["client_id"] + " · " + d["client_name"], "Delivery": d["expected_delivery_date"],
                                       "Salesperson": d["sales_person"], "Received": d["received"].map(inr),
                                       "Order value": d["order_value"].map(inr)}), width="stretch", hide_index=True)
    with c4:
        st.markdown("###### 📞 Payment calls planned")
        c = O[O["next_collection_date"].notna() & (O["balance"] > 0.5)
              & (O["next_collection_date"].astype(str).str[:10] <= soon)] if not O.empty else O
        if c.empty:
            st.caption("None.")
        else:
            from components.time_picker import fmt_12h
            st.dataframe(pd.DataFrame({"Client": c["client_id"] + " · " + c["client_name"],
                                       "Call": c["next_collection_date"].map(fmt_12h), "Balance": c["balance"].map(inr),
                                       "Handled by": c["po_owner_name"].fillna("—")}), width="stretch", hide_index=True)


def _collections(db_adapter, current_user):
    orders = enrich_orders(db_adapter.fetch_all("orders"))
    payments = db_adapter.fetch_all("payments")
    if orders.empty:
        st.info("No orders yet. Orders are created by Operations when a deal is won.")
        return

    today = today_ist()
    d30, d60 = today - datetime.timedelta(days=30), today - datetime.timedelta(days=60)
    due = orders[orders["balance"] > 0.5]
    total_sales = float(orders["order_value"].sum())
    collected = float(orders["received"].sum())
    outstanding = float(due["balance"].sum())
    coll_30 = _sum_since(payments, "paid_on", "amount", d30)
    coll_prev = _sum_since(payments, "paid_on", "amount", d60, d30)
    sales_30 = _sum_since(orders, "created_at", "order_value", d30)
    sales_prev = _sum_since(orders, "created_at", "order_value", d60, d30)
    over_90 = float(due[due["days_outstanding"] > 90]["balance"].sum())
    fu_overdue = int((due["follow_up"] == "Overdue").sum())

    render_kpi_cards([
        {"label": "Total sales booked", "value": inr(total_sales), "icon": "🧾", "tone": "blue",
         "sub": f"{len(orders)} orders"},
        {"label": "Payment received", "value": inr(collected), "icon": "✅", "tone": "green",
         "sub": f"{collected / total_sales * 100:.0f}% collected" if total_sales else ""},
        {"label": "Left to collect", "value": inr(outstanding), "icon": "⏳", "tone": "red",
         "sub": f"{due['client_id'].nunique()} parties"},
        {"label": "Older than 90 days", "value": inr(over_90), "icon": "⚠️", "tone": "amber",
         "sub": "needs escalation" if over_90 else "none"},
    ])
    render_kpi_cards([
        {"label": "Collected, last 30 days", "value": inr(coll_30), "icon": "💵", "tone": "green",
         "delta": coll_30 - coll_prev, "sub": "vs previous 30 days"},
        {"label": "Sales booked, last 30 days", "value": inr(sales_30), "icon": "📈", "tone": "blue",
         "delta": sales_30 - sales_prev, "sub": "vs previous 30 days"},
        {"label": "Payment follow-ups overdue", "value": fu_overdue, "icon": "📞", "tone": "red", "delta_good": "down"},
        {"label": "Fully paid orders", "value": int((orders["status"] == "Received").sum()), "icon": "🏁", "tone": "teal"},
    ])

    g1, g2, g3 = st.columns([1.3, 1, 1.2])
    with g1:
        st.markdown("###### Sales booked vs collected")
        m = monthly_sales_vs_collections(orders, payments)
        if not m.empty:
            fig = px.bar(m, x="Month", y="Value", color="Series", barmode="group",
                         color_discrete_map={"Sales booked": BLUE, "Collected": GREEN})
            fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10), legend_title_text="",
                              yaxis_title="₹", xaxis_title="", legend=dict(orientation="h", y=1.12))
            st.plotly_chart(fig, width="stretch")
    with g2:
        st.markdown("###### Balance by age")
        if due.empty:
            st.success("Everything is collected.")
        else:
            age = due.groupby("ageing", as_index=False)["balance"].sum()
            age["order"] = age["ageing"].map({b[2]: i for i, b in enumerate(AGEING_BUCKETS)})
            fig = px.pie(age.sort_values("order"), values="balance", names="ageing", hole=0.55,
                         color="ageing", color_discrete_map=AGE_COLORS)
            fig.update_traces(textinfo="percent", hovertemplate="%{label}: ₹%{value:,.0f}<extra></extra>")
            fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(fig, width="stretch")
    with g3:
        st.markdown("###### Biggest balances")
        if not due.empty:
            top = due.groupby("client_name", as_index=False)["balance"].sum().nlargest(8, "balance")
            fig = px.bar(top, x="balance", y="client_name", orientation="h", color_discrete_sequence=[RED])
            fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10), xaxis_title="₹", yaxis_title="",
                              yaxis=dict(autorange="reversed"))
            fig.update_traces(hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>")
            st.plotly_chart(fig, width="stretch")

    tab_pending, tab_party, tab_paid, tab_log = st.tabs([
        f"💰 To collect ({len(due)})", "🏢 By party", f"🏁 Fully paid ({int((orders['status'] == 'Received').sum())})",
        f"📒 Payments received ({len(payments)})"])

    # ------------------------------------------------------------ to collect
    with tab_pending:
        if due.empty:
            st.success("No balances to collect.")
        else:
            f1, f2, f3, f4 = st.columns([1.4, 1, 1, 1])
            with f1:
                q = st.text_input("Search", placeholder="Client, company, order or phone", key="col_q").strip().lower()
            with f2:
                age_f = st.selectbox("Age", ["All"] + [b[2] for b in AGEING_BUCKETS], key="col_age")
            with f3:
                fu_f = st.selectbox("Follow-up", ["All", "Overdue", "Today", "Scheduled", "Not set"], key="col_fu")
            with f4:
                sp_f = st.selectbox("Salesperson", ["All"] + sorted(due["sales_person"].dropna().unique()), key="col_sp")
            view = due
            if q:
                hay = (view["client_name"].astype(str) + " " + view["company_name"].fillna("").astype(str) + " "
                       + view["order_id"].astype(str) + " " + view["phone_number"].astype(str)).str.lower()
                view = view[hay.str.contains(q, regex=False)]
            if age_f != "All":
                view = view[view["ageing"] == age_f]
            if fu_f != "All":
                view = view[view["follow_up"] == fu_f]
            if sp_f != "All":
                view = view[view["sales_person"] == sp_f]
            view = view.sort_values(["days_outstanding"], ascending=False)

            table = view[["order_id", "client_name", "company_name", "phone_number", "sales_person", "order_value",
                          "received", "balance", "status", "days_outstanding", "ageing", "next_collection_date",
                          "follow_up", "collection_remarks"]].copy()
            for c in ("order_value", "received", "balance"):
                table[c] = table[c].map(inr)
            st.dataframe(table.rename(columns={
                "order_id": "Order", "client_name": "Client", "company_name": "Company", "phone_number": "Phone",
                "sales_person": "Salesperson", "order_value": "Order value", "received": "Received",
                "balance": "Balance", "status": "Status", "days_outstanding": "Days", "ageing": "Age",
                "next_collection_date": "Next follow-up", "follow_up": "Follow-up", "collection_remarks": "Last remark"}),
                width="stretch", hide_index=True)

            if not view.empty:
                st.markdown("##### Work on a party")
                labels = dict(zip(view["order_id"] + " · " + view["client_name"] + " · balance " + view["balance"].map(inr),
                                  view["order_id"]))
                pick = st.selectbox("Order", list(labels.keys()), key="col_pick")
                _order_panel(db_adapter, view[view["order_id"] == labels[pick]].iloc[0], payments, current_user)

    # ------------------------------------------------------------ by party
    with tab_party:
        party = orders.groupby(["client_id", "client_name", "company_name"], dropna=False).agg(
            orders=("order_id", "count"), order_value=("order_value", "sum"), received=("received", "sum"),
            balance=("balance", "sum"), oldest_days=("days_outstanding", "max"),
            last_payment=("last_payment_on", "max")).reset_index()
        party["balance"] = party["balance"].clip(lower=0)
        party["Status"] = [payment_status(v, r) for v, r in zip(party["order_value"], party["received"])]
        party = party.sort_values("balance", ascending=False)
        only_due = st.toggle("Only parties with a balance", value=True)
        if only_due:
            party = party[party["balance"] > 0.5]
        show = party.copy()
        for c in ("order_value", "received", "balance"):
            show[c] = show[c].map(inr)
        st.dataframe(show.rename(columns={"client_id": "Client ID", "client_name": "Client", "company_name": "Company",
                                          "orders": "Orders", "order_value": "Total sales", "received": "Received",
                                          "balance": "Left to collect", "oldest_days": "Oldest (days)",
                                          "last_payment": "Last payment"}),
                     width="stretch", hide_index=True)
        st.download_button("Download party-wise outstanding (CSV)", party.to_csv(index=False).encode("utf-8"),
                           file_name=f"party_outstanding_{today}.csv", mime="text/csv")

    # ------------------------------------------------------------ paid
    with tab_paid:
        paid = orders[orders["status"] == "Received"]
        if paid.empty:
            st.info("No fully paid orders yet.")
        else:
            show = paid[["order_id", "client_name", "company_name", "sales_person", "order_value", "received",
                         "payments_count", "last_payment_on"]].copy()
            show["order_value"] = show["order_value"].map(inr)
            show["received"] = show["received"].map(inr)
            st.dataframe(show, width="stretch", hide_index=True)

    # ------------------------------------------------------------ payment log
    with tab_log:
        if payments.empty:
            st.info("No payments recorded yet.")
        else:
            d1, d2 = st.columns(2)
            with d1:
                start = st.date_input("From", value=today.replace(day=1), key="pl_from")
            with d2:
                end = st.date_input("To", value=today, key="pl_to")
            p = payments[(payments["paid_on"].astype(str) >= str(start)) & (payments["paid_on"].astype(str) <= str(end))]
            render_kpi_cards([
                {"label": "Received in range", "value": inr(p["amount"].sum()), "tone": "green", "icon": "💵"},
                {"label": "Payments", "value": len(p), "tone": "blue", "icon": "🧾"},
                {"label": "Parties paid", "value": p["client_id"].nunique(), "tone": "teal", "icon": "🏢"},
            ])
            by_mode = p.groupby("mode", as_index=False)["amount"].sum()
            if not by_mode.empty:
                st.caption("By mode: " + " · ".join(f"{m} {inr(a)}" for m, a in zip(by_mode["mode"], by_mode["amount"])))
            show = p[["payment_id", "paid_on", "order_id", "client_name", "amount", "mode", "reference", "notes",
                      "recorded_by_name"]].copy()
            show["amount"] = show["amount"].map(inr)
            st.dataframe(show.sort_values("paid_on", ascending=False), width="stretch", hide_index=True)
            if st.download_button("Download payments (CSV)", p.to_csv(index=False).encode("utf-8"),
                                  file_name=f"payments_{start}_to_{end}.csv", mime="text/csv"):
                db_adapter.log_event("EXPORT", "payments", None, None, {"rows": len(p)})


def _order_panel(db_adapter, order, payments, current_user):
    oid = order["order_id"]
    st.markdown(f"""
    <div class='saas-card'>
      <div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;'>
        <span style='font-weight:800; color:#184B9C; font-size:17px;'>{html.escape(str(order['client_name']))}
          <span style='color:#64748B; font-weight:600; font-size:13.5px;'>· {html.escape(str(order.get('company_name') or ''))} · {html.escape(oid)}</span></span>
        <span class='pill' style='background:#FDE7EA; color:#BE123C;'>Balance {inr(order['balance'])}</span>
      </div>
      <div style='margin-top:6px; color:#334155; font-size:14px;'>
        Order {inr(order['order_value'])} · received {inr(order['received'])} · {order['days_outstanding']} days since order ·
        {html.escape(str(order['product']))} × {order['qty']} · sales: {html.escape(str(order.get('sales_person') or '—'))}
      </div>
      {contact_links(order.get('phone_number'), None, str(order['client_name']))}
    </div>""", unsafe_allow_html=True)

    hist = payments[payments["order_id"] == oid] if not payments.empty else payments
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Record a payment")
        with st.form(f"pay_{oid}", clear_on_submit=True):
            a1, a2 = st.columns(2)
            with a1:
                amount = st.number_input("Amount received (₹) *", min_value=0.0,
                                         value=float(max(order["balance"], 0)), step=1000.0)
                mode = st.selectbox("Mode *", PAYMENT_MODES)
            with a2:
                paid_on = st.date_input("Received on *", value=today_ist())
                ref = st.text_input("UTR / cheque no.")
            notes = st.text_input("Notes")
            if st.form_submit_button("Save payment"):
                if amount <= 0:
                    st.error("Enter the amount received.")
                elif paid_on > today_ist():
                    st.error("The received date can't be in the future.")
                elif amount > float(order["balance"]) + 1:
                    st.error(f"That is more than the balance ({inr(order['balance'])}). Check the amount or the order value.")
                else:
                    pid = db_adapter.insert_row("payments", {
                        "payment_id": db_adapter.next_payment_id(), "order_id": oid, "amount": float(amount),
                        "paid_on": str(paid_on), "mode": mode, "reference": ref.strip() or None,
                        "notes": notes.strip() or None, "recorded_by": current_user["employee_id"],
                        "created_at": now_str()})
                    if pid is None:
                        st.error(db_adapter.last_error)
                    else:
                        new_received = float(order["received"]) + float(amount)
                        status = payment_status(order["order_value"], new_received)
                        updates = {"payment_status": status, "updated_at": now_str()}
                        if status == "Received":
                            updates["next_collection_date"] = None
                        db_adapter.update_row("orders", "order_id", oid, updates)
                        st.toast(f"{inr(amount)} recorded for {order['client_name']}. Status: {status}.", icon="✅")
                        st.rerun()
    with c2:
        st.markdown("###### Payment follow-up")
        with st.form(f"fu_{oid}"):
            nxt = st.date_input("Next follow-up date", value=today_ist() + datetime.timedelta(days=3))
            remark = st.text_area("What did the client say?", value="",
                                  placeholder="e.g. Accounts head will release 50% on Friday")
            if st.form_submit_button("Save follow-up"):
                if not remark.strip():
                    st.error("Add a short remark.")
                elif db_adapter.update_row("orders", "order_id", oid, {
                        "next_collection_date": str(nxt),
                        "collection_remarks": f"{today_ist().strftime('%d %b')}: {remark.strip()}",
                        "updated_at": now_str()}):
                    st.toast(f"Next payment follow-up set for {nxt.strftime('%d %b')}.", icon="✅")
                    st.rerun()
                else:
                    st.error(db_adapter.last_error)

    st.markdown("###### Payment history")
    if hist.empty:
        st.caption("No payments yet for this order.")
    else:
        h = hist[["paid_on", "amount", "mode", "reference", "notes", "recorded_by_name"]].copy()
        h["amount"] = h["amount"].map(inr)
        st.dataframe(h, width="stretch", hide_index=True)
