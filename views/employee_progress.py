"""views/employee_progress.py - My progress: KPIs, clear charts, product prices and filterable records."""
import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.kpi_cards import page_title, render_kpi_cards
from components.target_gauges import render_target_gauges
from components.time_picker import fmt_12h
from config.settings import LEAD_STAGES, REPORTING_WINDOWS, STAGE_LOST, STAGE_WON
from utils.metrics import delta_kpi, filter_by_window, inr, latest_quotes
from utils.queues import my_clients
from utils.time_utils import today_ist, window_start

BLUE, NAVY, GREEN, RED, AMBER, TEAL = "#184B9C", "#0E2C68", "#00A859", "#BE123C", "#B45309", "#0E7490"
STAGE_COLORS = {"Done": GREEN, "Cancled": RED, "Pending": "#94A3B8", "In Discussion": BLUE,
                "CallBack": "#0284C7", "Not Responed": AMBER, "Under Finalization": TEAL,
                "Approved": GREEN, "Rejected": RED, "Under Review": "#0284C7"}
ACTIVITY_COLORS = {"Leads added": BLUE, "Quotations": TEAL, "Calls": AMBER, "Payments": GREEN}


def _layout(fig, h=300):
    fig.update_layout(height=h, margin=dict(t=10, b=10, l=10, r=40), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", legend_title_text="", legend=dict(orientation="h", y=1.12),
                      xaxis_title="", yaxis_title="", hoverlabel=dict(bgcolor=NAVY, font_color="#FFFFFF"))
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0", zeroline=False)
    fig.update_yaxes(showgrid=False)
    return fig


def _hbar(df, col, title, empty="Nothing in this period."):
    st.markdown(f"###### {title}")
    if df is None or df.empty or col not in df:
        st.info(empty)
        return
    vc = df[col].fillna("—").value_counts().reset_index()
    vc.columns = [col, "Count"]
    total = vc["Count"].sum()
    vc["label"] = [f"{c}  ({c / total * 100:.0f}%)" for c in vc["Count"]]
    vc = vc.sort_values("Count")
    seq = [BLUE, TEAL, AMBER, GREEN, NAVY, RED, "#7C3AED"]
    colors = [STAGE_COLORS.get(v, seq[i % len(seq)]) for i, v in enumerate(vc[col])]
    fig = go.Figure(go.Bar(x=vc["Count"], y=vc[col].astype(str), orientation="h", marker_color=colors, text=vc["label"],
                           textposition="outside", cliponaxis=False, hovertemplate="<b>%{y}</b>: %{x}<extra></extra>"))
    fig.update_layout(showlegend=False, bargap=0.3)
    fig.update_xaxes(range=[0, vc["Count"].max() * 1.35], dtick=max(1, int(vc["Count"].max() // 5)))
    st.plotly_chart(_layout(fig, 70 + 42 * len(vc)), width="stretch")


def _journey(base, title):
    st.markdown(f"###### {title}")
    if base.empty:
        st.info("Nothing in this period.")
        return
    n = len(base)
    steps = [("Received", n, BLUE), ("Quotation sent", int(base["quote_sent_at"].notna().sum()), TEAL),
             ("Done (won)", int((base["final_status"] == STAGE_WON).sum()), GREEN),
             ("Cancled", int((base["final_status"] == STAGE_LOST).sum()), RED)]
    rows = "".join(f"""
      <div style='margin:10px 0;'>
        <div style='display:flex; justify-content:space-between; font-size:13.5px; color:#334155; font-weight:600;'>
          <span>{html.escape(label)}</span><span>{v} <span style='color:#94A3B8;'>· {v / n * 100:.0f}%</span></span></div>
        <div style='background:#EEF3FB; border-radius:8px; height:12px; margin-top:4px; overflow:hidden;'>
          <div style='width:{max(v / n * 100, 1.5):.1f}%; background:{c}; height:100%; border-radius:8px;'></div></div>
      </div>""" for label, v, c in steps)
    st.markdown(f"<div class='saas-card'>{rows}</div>", unsafe_allow_html=True)


def _price_table(quotes_scope, leads_all):
    """Per product: quoted and sold price per unit (final price ÷ quantity), latest revision per client."""
    if quotes_scope.empty:
        return pd.DataFrame(), pd.DataFrame()
    q = latest_quotes(quotes_scope).copy()
    stage = dict(zip(leads_all["lead_id"], leads_all["final_status"]))       # current stage of the client
    q["final_status"] = q["lead_id"].map(stage).fillna(q["final_status"])
    qty = pd.to_numeric(q["qty"], errors="coerce").fillna(1).clip(lower=1)
    q["unit"] = pd.to_numeric(q["qut_amount"], errors="coerce") / qty
    q = q[q["unit"] > 0]
    q["sold"] = q["final_status"] == STAGE_WON
    rows = []
    for prod, g in q.groupby("product"):
        sold = g[g["sold"]]
        rows.append({"Product": prod, "Quotations": len(g), "Done deals": len(sold),
                     "Highest sold / unit": sold["unit"].max() if len(sold) else None,
                     "Lowest sold / unit": sold["unit"].min() if len(sold) else None,
                     "Highest quoted / unit": g["unit"].max(), "Lowest quoted / unit": g["unit"].min(),
                     "Average quoted / unit": g["unit"].mean(), "Total quoted": g["qut_amount"].sum()})
    return pd.DataFrame(rows).sort_values("Quotations", ascending=False), q


def _records(title, df, columns, key, date_col=None):
    """A clean table with search, a status filter, column choice and download."""
    st.markdown(f"###### {title} ({len(df)})")
    if df.empty:
        st.info("No records with these filters.")
        return
    view = df[[c for c in columns if c in df.columns]].copy()
    f1, f2, f3 = st.columns([1.4, 1, 1.4])
    with f1:
        q = st.text_input("Search", placeholder="Any text in the row", key=f"{key}_q").strip().lower()
    status_col = next((c for c in ["Stage", "Outcome", "Status", "Mode"] if c in view.columns), None)
    with f2:
        stat = st.multiselect(status_col or "Status", sorted(view[status_col].dropna().astype(str).unique()) if status_col else [],
                              key=f"{key}_s", placeholder="All", disabled=status_col is None)
    with f3:
        cols = st.multiselect("Columns", list(view.columns), default=list(view.columns), key=f"{key}_c")
    if q:
        view = view[view.astype(str).apply(lambda r: q in " ".join(r).lower(), axis=1)]
    if stat:
        view = view[view[status_col].astype(str).isin(stat)]
    view = view[cols] if cols else view
    st.dataframe(view, width="stretch", hide_index=True)
    st.download_button("Download these rows (CSV)", view.to_csv(index=False).encode("utf-8"),
                       file_name=f"{key}.csv", mime="text/csv", key=f"{key}_dl")


def render_my_progress_report(db_adapter, current_user):
    page_title("My progress", f"{current_user['name']} · your work at a glance.")
    emp_id, role = current_user["employee_id"], current_user["role"]

    window = st.segmented_control("Period", list(REPORTING_WINDOWS.keys()), default="This month", key="mp_window") \
        or "This month"
    days = REPORTING_WINDOWS[window]
    start = window_start(days)

    if role == "PO":
        from utils.targets import get_targets, load_data, month_key
        if get_targets(db_adapter, emp_id, month_key()):
            st.markdown("##### 🎯 My targets this month")
            render_target_gauges(db_adapter, emp_id, role, month_key(), load_data(db_adapter), key_prefix="mp",
                                 only_with_target=True)
        _po_progress(db_adapter, emp_id, start, days)
        return

    leads_all = db_adapter.fetch_all("leads_master")
    quotes_all = db_adapter.fetch_all("quotations_master")
    logs_all = db_adapter.fetch_all("followup_logs")
    pays_all = db_adapter.fetch_all("payments") if role in ("ACCOUNTS", "ADMIN") else pd.DataFrame()
    empty = pd.DataFrame()

    # ---------------- what "mine" means for each role
    if role == "SAM":
        lead_scope = my_clients(leads_all, current_user)
    elif role == "QS":
        lead_scope = leads_all[(leads_all["claimed_qs_id"] == emp_id) | (leads_all["handled_by_lge_id"] == emp_id)] \
            if not leads_all.empty else empty
    else:
        lead_scope = leads_all[leads_all["handled_by_lge_id"] == emp_id] if not leads_all.empty else empty
    if role in ("QS", "ADMIN"):
        quote_scope = quotes_all[quotes_all["created_by"] == emp_id] if not quotes_all.empty else empty
    else:
        quote_scope = quotes_all[quotes_all["lead_id"].isin(lead_scope["lead_id"])] if not quotes_all.empty and not lead_scope.empty else empty
    calls_scope = logs_all[logs_all["employee_id"] == emp_id] if not logs_all.empty else empty
    pays_scope = pays_all[pays_all["recorded_by"] == emp_id] if not pays_all.empty else empty

    # ---------------- filters
    with st.expander("🔎 Filters", expanded=False):
        f1, f2, f3 = st.columns(3)
        prods = sorted(set(lead_scope["product"].dropna()) | set(quote_scope["product"].dropna())) if not lead_scope.empty or not quote_scope.empty else []
        with f1:
            p_sel = st.multiselect("Product", prods, placeholder="All products", key="mp_prod")
        with f2:
            s_sel = st.multiselect("Source", sorted(leads_all["source"].dropna().unique()) if not leads_all.empty else [],
                                   placeholder="All sources", key="mp_src")
        with f3:
            st_sel = st.multiselect("Stage", LEAD_STAGES, placeholder="All stages", key="mp_stage")
    keep = leads_all
    if not keep.empty:
        if p_sel:
            keep = keep[keep["product"].isin(p_sel)]
        if s_sel:
            keep = keep[keep["source"].isin(s_sel)]
        if st_sel:
            keep = keep[keep["final_status"].isin(st_sel)]
    keep_ids = set(keep["lead_id"]) if not keep.empty else set()
    filt = lambda d: d[d["lead_id"].isin(keep_ids)] if not d.empty else d
    lead_scope, quote_scope, calls_scope = filt(lead_scope), filt(quote_scope), filt(calls_scope)

    leads_p = filter_by_window(lead_scope, "ingested_at", start)
    quotes_p = filter_by_window(quote_scope, "created_at", start)
    calls_p = filter_by_window(calls_scope, "logged_at", start)
    pays_p = filter_by_window(pays_scope, "paid_on", start)

    # ---------------- KPIs
    tiles = []
    if role in ("LGE", "QS", "ADMIN"):
        tiles.append(delta_kpi("Leads added" if role != "QS" else "My leads", lead_scope, "ingested_at", days, icon="📥", tone="blue"))
    if role in ("QS", "ADMIN"):
        tiles.append(delta_kpi("Quotations created", quote_scope, "created_at", days, icon="📄", tone="teal"))
        appr = int((quotes_p["quotation_status"] == "Approved").sum()) if len(quotes_p) else 0
        tiles.append({"label": "Approval rate", "icon": "✅", "tone": "green",
                      "value": f"{appr / len(quotes_p) * 100:.0f}%" if len(quotes_p) else "—",
                      "sub": f"{appr} of {len(quotes_p)} approved"})
        tiles.append({"label": "Value quoted", "icon": "💰", "tone": "navy",
                      "value": inr(latest_quotes(quotes_p)["qut_amount"].sum()) if len(quotes_p) else "₹0",
                      "sub": "latest revision per client"})
    if role == "SAM":
        won = leads_p[leads_p["final_status"] == STAGE_WON] if len(leads_p) else leads_p
        lost = leads_p[leads_p["final_status"] == STAGE_LOST] if len(leads_p) else leads_p
        lq = latest_quotes(quotes_all)
        won_val = float(lq[lq["lead_id"].isin(won["lead_id"])]["qut_amount"].sum()) if len(won) and not lq.empty else 0
        closed = len(won) + len(lost)
        tiles += [{"label": "My clients", "value": len(leads_p), "icon": "🗂️", "tone": "blue"},
                  {"label": "Done", "value": len(won), "icon": "🏆", "tone": "green", "sub": inr(won_val)},
                  {"label": "Win rate", "value": f"{len(won) / closed * 100:.0f}%" if closed else "—",
                   "icon": "🎯", "tone": "teal", "sub": f"{closed} closed"}]
    if role == "ACCOUNTS":
        tiles.append({"label": "Collected (recorded by me)", "value": inr(pays_p["amount"].sum()) if len(pays_p) else "₹0",
                      "icon": "💵", "tone": "green", "sub": f"{len(pays_p)} payments"})
    tiles.append(delta_kpi("Calls logged", calls_scope, "logged_at", days, icon="📞", tone="amber"))
    render_kpi_cards(tiles[:5])

    # ---------------- targets set by the admin (this month)
    from utils.targets import get_targets, load_data, month_key
    if get_targets(db_adapter, emp_id, month_key()):
        st.markdown("##### 🎯 My targets this month")
        render_target_gauges(db_adapter, emp_id, role, month_key(), load_data(db_adapter), key_prefix="mp",
                             only_with_target=True)

    tab_over, tab_prod, tab_rec = st.tabs(["📈 Overview", "📦 Products & prices", "📋 Records"])

    # ---------------- overview
    with tab_over:
        frames = []
        for d, col, name in [(leads_p, "ingested_at", "Leads added"), (quotes_p, "created_at", "Quotations"),
                             (calls_p, "logged_at", "Calls"), (pays_p, "paid_on", "Payments")]:
            if len(d):
                frames.append(pd.DataFrame({"date": pd.to_datetime(d[col].astype(str).str[:10], errors="coerce"), "Activity": name}))
        st.markdown("###### Am I on track? — running total for the period")
        if not frames:
            st.info("No activity in this period yet. Charts fill in as you work.")
        else:
            act = pd.concat(frames).dropna()
            first = pd.Timestamp(start) if start else act["date"].min()
            days = pd.date_range(first, pd.Timestamp(today_ist()), freq="D")
            daily = act.groupby(["date", "Activity"]).size().unstack(fill_value=0).reindex(days, fill_value=0)
            cum = daily.cumsum()
            fig = go.Figure()
            for name in cum.columns:
                color = ACTIVITY_COLORS.get(name, BLUE)
                fig.add_scatter(x=cum.index, y=cum[name], name=name, mode="lines", line=dict(color=color, width=3, shape="spline"),
                                hovertemplate="%{x|%d %b}: %{y} so far<extra>" + name + "</extra>")
                fig.add_scatter(x=[cum.index[-1]], y=[cum[name].iloc[-1]], mode="markers+text", showlegend=False,
                                marker=dict(size=11, color=color), text=[f"  {int(cum[name].iloc[-1])} {name.lower()}"],
                                textposition="middle right", textfont=dict(color=color, size=13), hoverinfo="skip")
            fig.update_xaxes(range=[days[0], days[-1] + pd.Timedelta(days=max(3, len(days) // 5))])
            st.plotly_chart(_layout(fig, 320), width="stretch")
            # a quick daily strip: which days were busy
            busy = daily.sum(axis=1)
            strip = go.Figure(go.Bar(x=busy.index, y=busy.values, marker_color=[GREEN if v else "#E2E8F0" for v in busy.values],
                                     hovertemplate="%{x|%a %d %b}: %{y} actions<extra></extra>"))
            strip.update_yaxes(visible=False)
            st.caption("Actions per day")
            st.plotly_chart(_layout(strip, 120), width="stretch")

        c1, c2 = st.columns(2)
        with c1:
            _hbar(calls_p, "followup_status", "Outcome of my calls")
        with c2:
            if role in ("QS", "ADMIN"):
                _hbar(quotes_p, "quotation_status", "My quotation results")
            elif role == "SAM":
                _hbar(leads_p, "final_status", "Where my clients stand")
            elif role == "ACCOUNTS":
                _hbar(pays_p, "mode", "Payments by mode")
            else:
                _hbar(leads_p, "source", "Where my leads come from")
        c3, c4 = st.columns(2)
        with c3:
            _journey(leads_p, "Journey of " + ("my clients" if role == "SAM" else "my leads"))
        with c4:
            _hbar(leads_p, "source", "Lead sources") if role != "LGE" else _hbar(leads_p, "final_status", "Stage of my leads")

    # ---------------- products & prices
    with tab_prod:
        if quotes_p.empty:
            st.info("No quotations in this period with these filters.")
        else:
            lqp = latest_quotes(quotes_p)
            by_p = lqp.groupby("product").agg(Quotations=("quotation_id", "count"), Value=("qut_amount", "sum")).reset_index()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("###### Products quoted (number)")
                fig = px.bar(by_p.sort_values("Quotations"), x="Quotations", y="product", orientation="h", text="Quotations",
                             color_discrete_sequence=[BLUE])
                fig.update_traces(textposition="outside", cliponaxis=False)
                fig.update_xaxes(range=[0, by_p["Quotations"].max() * 1.25], dtick=max(1, int(by_p["Quotations"].max() // 6)))
                st.plotly_chart(_layout(fig, 60 + 34 * len(by_p)), width="stretch")
            with c2:
                st.markdown("###### Products quoted (value)")
                fig = px.bar(by_p.sort_values("Value"), x="Value", y="product", orientation="h",
                             text=by_p.sort_values("Value")["Value"].map(inr), color_discrete_sequence=[TEAL])
                fig.update_traces(textposition="outside", cliponaxis=False, hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>")
                fig.update_xaxes(range=[0, by_p["Value"].max() * 1.35])
                st.plotly_chart(_layout(fig, 60 + 34 * len(by_p)), width="stretch")

            st.markdown("###### Price per unit by product")
            st.caption("Final price ÷ quantity, from the latest revision. 'Sold' means the client's stage is Done.")
            table, unit = _price_table(quotes_p, leads_all)
            if table.empty:
                st.info("No priced quotations yet.")
                st.stop()
            show = table.copy()
            for c in [c for c in show.columns if "/ unit" in c or c == "Total quoted"]:
                show[c] = show[c].map(lambda v: inr(v) if pd.notna(v) else "—")
            st.dataframe(show, width="stretch", hide_index=True)

            prod_pick = st.selectbox("See every quoted price for a product", table["Product"].tolist(), key="mp_pp")
            pts = unit[unit["product"] == prod_pick].copy()
            pts["Stage"] = pts["final_status"]
            pts["When"] = pd.to_datetime(pts["created_at"], errors="coerce")
            fig = px.scatter(pts, x="When", y="unit", color="Stage", color_discrete_map=STAGE_COLORS, size_max=14,
                             hover_data={"client_name": True, "quotation_ref": True, "unit": ":,.0f"})
            fig.update_traces(marker=dict(size=13, line=dict(width=1, color="#FFFFFF")))
            fig.update_yaxes(title="₹ per unit", tickprefix="₹")
            st.plotly_chart(_layout(fig, 300), width="stretch")

    # ---------------- records
    with tab_rec:
        sets = []
        if len(leads_p):
            sets.append(("Leads", pd.DataFrame({
                "Client ID": leads_p["client_id"], "Client": leads_p["client_name"], "Company": leads_p["company_name"],
                "Phone": leads_p["phone_number"], "Product": leads_p["product"], "Qty": leads_p["qty"],
                "Source": leads_p["source"], "Stage": leads_p["final_status"], "Quotation": leads_p["quotation_status"],
                "Salesperson": leads_p["assigned_salesperson"], "Received": leads_p["ingested_at"].map(fmt_12h),
                "Next call": leads_p["next_followup_at"].map(fmt_12h)}), "leads"))
        if len(quotes_p):
            sets.append(("Quotations", pd.DataFrame({
                "Client ID": quotes_p["client_id"], "Client": quotes_p["client_name"], "Quotation": quotes_p["quotation_ref"],
                "Product": quotes_p["product"], "Qty": quotes_p["qty"], "List price": quotes_p["gross_amount"].map(inr),
                "Discount": quotes_p["discount_amount"].map(lambda v: inr(v) if v else "—"),
                "Final price": quotes_p["qut_amount"].map(inr), "Status": quotes_p["quotation_status"],
                "Created": quotes_p["created_at"].map(fmt_12h)}), "quotes"))
        if len(calls_p):
            sets.append(("Calls", pd.DataFrame({
                "Client ID": calls_p["client_id"], "Client": calls_p["client_name"], "When": calls_p["logged_at"].map(fmt_12h),
                "Outcome": calls_p["followup_status"], "Notes": calls_p["notes"],
                "Next call": calls_p["scheduled_call_time"].map(fmt_12h)}), "calls"))
        if len(pays_p):
            sets.append(("Payments", pd.DataFrame({
                "Client": pays_p["client_name"], "Order": pays_p["order_id"], "Received on": pays_p["paid_on"],
                "Amount": pays_p["amount"].map(inr), "Mode": pays_p["mode"], "Reference": pays_p["reference"]}), "pays"))
        if not sets:
            st.info("No records in this period with these filters.")
        else:
            for tab, (title, df, key) in zip(st.tabs([f"{t} ({len(d)})" for t, d, _ in sets]), sets):
                with tab:
                    _records(title, df, list(df.columns), f"mp_{key}")



def _po_progress(db, emp_id, start, days):
    """My progress for the PO & PI team: verification, collection and payment calls."""
    from utils.payment_plan import current_milestone, stage_label
    from utils.time_utils import today_ist as _today
    O = db.fetch_all("orders")
    P = db.fetch_all("payments")
    F = db.fetch_all("payment_followups")
    mine = O[(O["po_owner_id"] == emp_id) | O["po_owner_id"].isna()] if not O.empty else O
    ids = set(mine["order_id"]) if not mine.empty else set()
    pays_all = P[P["order_id"].isin(ids) | (P["recorded_by"] == emp_id)] if not P.empty else P
    calls_all = F[(F["logged_by"] == emp_id) & (F["outcome"] != "Payment received")] if not F.empty else F
    verified_all = mine[mine["po_verified_by"] == emp_id] if not mine.empty else mine
    pays, calls = filter_by_window(pays_all, "paid_on", start), filter_by_window(calls_all, "logged_at", start)
    today = _today()
    due_now = 0.0
    stages = []
    for _, o in mine.iterrows():
        m = current_milestone(o)
        stages.append({"Stage": stage_label(o), "Milestone": m["name"] if m else "Fully paid", "Due": m["balance"] if m else 0.0,
                       "Overdue": bool(m and m["due"] and m["due"] < today)})
        if m and m["due"] and m["due"] <= today:
            due_now += m["balance"]
    sdf = pd.DataFrame(stages)

    coll = {"label": "Collected", "value": inr(pays["amount"].sum()) if len(pays) else "₹0", "icon": "💵", "tone": "green",
            "sub": f"{len(pays)} payments"}
    render_kpi_cards([
        coll,
        delta_kpi("POs verified", verified_all, "po_verified_at", days, icon="🧾", tone="blue"),
        delta_kpi("Payment calls logged", calls_all, "logged_at", days, icon="📞", tone="amber"),
        {"label": "Due now", "value": inr(due_now), "icon": "⏳", "tone": "red",
         "sub": f"{int(sdf['Overdue'].sum()) if not sdf.empty else 0} orders overdue"},
        {"label": "Orders handled", "value": len(mine), "icon": "📦", "tone": "navy",
         "sub": f"{int((sdf['Stage'] == 'Fully paid').sum()) if not sdf.empty else 0} fully paid"},
    ])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Money collected — running total")
        if pays.empty:
            st.info("No payments in this period yet.")
        else:
            d = pays.assign(day=pd.to_datetime(pays["paid_on"].astype(str).str[:10])).groupby("day")["amount"].sum()
            first = pd.Timestamp(start) if start else d.index.min()
            d = d.reindex(pd.date_range(first, pd.Timestamp(today), freq="D"), fill_value=0).cumsum()
            fig = go.Figure(go.Scatter(x=d.index, y=d.values, mode="lines", line=dict(color=GREEN, width=3, shape="spline"),
                                       fill="tozeroy", fillcolor="rgba(0,168,89,0.12)",
                                       hovertemplate="%{x|%d %b}: ₹%{y:,.0f}<extra></extra>", showlegend=False))
            fig.add_scatter(x=[d.index[-1]], y=[d.values[-1]], mode="markers+text", text=[f"  {inr(d.values[-1])}"],
                            textposition="middle right", marker=dict(size=11, color=GREEN), showlegend=False, hoverinfo="skip")
            fig.update_xaxes(range=[d.index[0], d.index[-1] + pd.Timedelta(days=max(3, len(d) // 4))])
            fig.update_yaxes(tickprefix="₹")
            st.plotly_chart(_layout(fig, 300), width="stretch")
    with c2:
        _hbar(sdf.rename(columns={"Stage": "stage"}) if not sdf.empty else sdf, "stage", "Where my orders are")
    c3, c4 = st.columns(2)
    with c3:
        _hbar(calls, "outcome", "Outcome of my payment calls")
    with c4:
        dl = calls[calls["delay_reason"].notna()] if len(calls) else calls
        _hbar(dl, "delay_reason", "Why payments were delayed", "No delays recorded in this period. 🎉")

    st.markdown("###### Records")
    t1, t2 = st.tabs([f"Payments ({len(pays)})", f"Payment calls ({len(calls)})"])
    with t1:
        if len(pays):
            _records("Payments", pd.DataFrame({"Client": pays["client_id"] + " · " + pays["client_name"], "Order": pays["order_id"],
                                               "Received on": pays["paid_on"], "Amount": pays["amount"].map(inr),
                                               "Mode": pays["mode"], "For": pays["notes"].fillna("—")}),
                     ["Client", "Order", "Received on", "Amount", "Mode", "For"], "po_pays")
        else:
            st.info("No payments in this period.")
    with t2:
        if len(calls):
            _records("Payment calls", pd.DataFrame({"Client": calls["client_id"] + " · " + calls["client_name"],
                                                    "When": calls["logged_at"].map(fmt_12h), "Stage": calls["milestone"],
                                                    "Outcome": calls["outcome"], "Delay reason": calls["delay_reason"].fillna("—"),
                                                    "Notes": calls["notes"], "Next call": calls["next_call_at"].map(fmt_12h)}),
                     ["Client", "When", "Stage", "Outcome", "Delay reason", "Notes", "Next call"], "po_calls")
        else:
            st.info("No payment calls in this period.")
