"""
views/employee_report.py - Employee report card (admin).

Targets: admins set monthly targets; gauges show achieved vs target, with a marker
for where they should be by today. Below that, a role-specific in-depth report.
"""
import datetime
import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.kpi_cards import page_title, render_kpi_cards
from components.target_gauges import render_target_gauges
from config.settings import REPORTING_WINDOWS, ROLE_DESCRIPTIONS, STAGE_LOST, STAGE_WON, TARGET_METRICS
from utils.metrics import filter_by_window, inr, latest_quotes
from utils.targets import actual, gauge, get_targets, load_data, metrics_for, month_key, save_targets
from utils.time_utils import parse_ts, today_ist, window_start
from views.employee_progress import AMBER, BLUE, GREEN, TEAL, _hbar, _layout

ROLE_NAMES = {"SAM": "Salesperson", "QS": "Quotation Specialist", "LGE": "Lead Generation", "PO": "PO & PI Team", "ACCOUNTS": "Accounts",
              "OPERATIONS": "Operations", "ADMIN": "Admin"}


def months_back(n=6):
    d = today_ist().replace(day=1)
    out = []
    for _ in range(n):
        out.append(d.strftime("%Y-%m"))
        d = (d - datetime.timedelta(days=1)).replace(day=1)
    return out


def month_name(m):
    return datetime.date(int(m[:4]), int(m[5:]), 1).strftime("%B %Y")


def render_employee_report(db_adapter, current_user):
    page_title("Employee report card", "Targets, results and the detail behind them.")
    emp = db_adapter.fetch_all("employees")
    emp = emp[emp["is_active"] == 1] if not emp.empty else emp
    if emp.empty:
        st.info("No active employees.")
        return
    emp = emp.assign(_o=emp["role"].map({"SAM": 0, "QS": 1, "LGE": 2, "PO": 3, "ACCOUNTS": 4, "OPERATIONS": 5, "ADMIN": 6})) \
        .sort_values(["_o", "full_name"])
    c1, c2, c3 = st.columns([2, 1.1, 1.1])
    with c1:
        labels = dict(zip(emp["full_name"] + " — " + emp["role"].map(ROLE_NAMES).fillna(emp["role"]), emp["employee_id"]))
        emp_id = labels[st.selectbox("Employee", list(labels.keys()), key="er_emp")]
    with c2:
        month = st.selectbox("Target month", months_back(6), format_func=month_name, key="er_month")
    with c3:
        window = st.selectbox("Report period", list(REPORTING_WINDOWS.keys()), index=0, key="er_window")
    e = emp[emp["employee_id"] == emp_id].iloc[0]
    role = e["role"]
    start = window_start(REPORTING_WINDOWS[window])
    data = load_data(db_adapter)
    data["_employees"] = emp

    st.markdown(f"<div style='background:linear-gradient(135deg,#0E2C68 0%,#184B9C 100%); color:#fff; padding:18px 24px; "
                f"border-radius:16px; margin:6px 0 16px; display:flex; justify-content:space-between; align-items:center; "
                f"flex-wrap:wrap; gap:8px;'><div><div style='font-size:22px; font-weight:800;'>{html.escape(e['full_name'])}</div>"
                f"<div style='color:#D6E2F7; font-size:13.5px; margin-top:3px;'>{html.escape(e['employee_id'])} · "
                f"{html.escape(e['email'])}</div></div><div style='background:#00874A; padding:7px 18px; border-radius:22px; "
                f"font-weight:800; font-size:13px;'>{html.escape(ROLE_DESCRIPTIONS.get(role, role))}</div></div>",
                unsafe_allow_html=True)

    # ------------------------------------------------------------------ targets
    st.markdown(f"##### 🎯 Targets — {month_name(month)}")
    targets = render_target_gauges(db_adapter, emp_id, role, month, data)
    keys = metrics_for(role)
    if keys and current_user["role"] == "ADMIN":
        with st.expander(f"✏️ Set {e['full_name']}'s targets for {month_name(month)}", expanded=not targets):
            with st.form(f"tg_{emp_id}_{month}"):
                vals = {}
                tc = st.columns(min(3, len(keys)))
                for i, k in enumerate(keys):
                    label, _, unit = TARGET_METRICS[k]
                    with tc[i % len(tc)]:
                        vals[k] = st.number_input(label, min_value=0.0, value=float(targets.get(k) or 0),
                                                  step=50000.0 if unit == "money" else 1.0, key=f"tv_{emp_id}_{month}_{k}")
                b1, b2 = st.columns(2)
                with b1:
                    save = st.form_submit_button("Save targets", type="primary")
                with b2:
                    copy = st.form_submit_button("Copy the previous month's targets")
                if save:
                    n = save_targets(db_adapter, emp_id, month, vals, current_user["employee_id"])
                    st.toast(f"Targets saved ({n} changed).", icon="🎯")
                    st.rerun()
                if copy:
                    all_m = months_back(12)
                    prev = all_m[all_m.index(month) + 1] if month in all_m and all_m.index(month) + 1 < len(all_m) else None
                    last = get_targets(db_adapter, emp_id, prev) if prev else {}
                    if not last:
                        st.warning("No targets were set the month before.")
                    else:
                        save_targets(db_adapter, emp_id, month, last, current_user["employee_id"])
                        st.toast("Copied the previous month's targets.", icon="🎯")
                        st.rerun()

    st.markdown("---")
    if role == "SAM":
        _sam_report(emp_id, data, start, window)
    elif role == "QS":
        _qs_report(emp_id, data, start, window)
    elif role == "ACCOUNTS":
        _accounts_report(emp_id, data, start)
    elif role == "PO":
        from views.employee_progress import _po_progress
        st.markdown(f"##### 🧾 PO & payment report — {window.lower()}")
        _po_progress(db_adapter, emp_id, start, REPORTING_WINDOWS[window])
    else:
        _lge_report(emp_id, data, start)


# ====================================================================== salesperson
def sam_metrics(emp_id, data, start):
    """Every number counts the event in the period: leads by received date, deals by close date,
    quotations by creation date, payments by payment date, calls by call date."""
    L, Q, G, O, P = data["leads"], data["quotes"], data["logs"], data["orders"], data["payments"]
    allm = L[L["assigned_sam_id"] == emp_id] if not L.empty else L
    ids = set(allm["lead_id"])
    assigned = filter_by_window(allm, "ingested_at", start)
    closed = filter_by_window(allm[allm["final_status"].isin([STAGE_WON, STAGE_LOST])], "closed_at", start)
    done, lost = closed[closed["final_status"] == STAGE_WON], closed[closed["final_status"] == STAGE_LOST]
    lq_all = latest_quotes(Q[Q["lead_id"].isin(ids)]) if not Q.empty else Q
    price = dict(zip(lq_all["lead_id"], lq_all["qut_amount"])) if not lq_all.empty else {}
    q_period = filter_by_window(Q[Q["lead_id"].isin(ids)], "created_at", start) if not Q.empty else Q
    open_ = allm[~allm["final_status"].isin([STAGE_WON, STAGE_LOST])]
    orders = O[O["lead_id"].isin(ids)] if not O.empty else O
    pays = filter_by_window(P[P["order_id"].isin(orders["order_id"])], "paid_on", start) if not P.empty and not orders.empty else P.iloc[0:0] if not P.empty else P
    calls = filter_by_window(G[G["lead_id"].isin(ids)], "logged_at", start) if not G.empty else G
    done_val = float(sum(price.get(i, 0) for i in done["lead_id"]))
    return {
        "assigned": len(assigned), "converted": len(done), "lost": len(lost),
        "win_rate": (len(done) / (len(done) + len(lost)) * 100) if (len(done) + len(lost)) else None,
        "approved": int((q_period["quotation_status"] == "Approved").sum()) if len(q_period) else 0,
        "revisions": int((q_period["revision_no"] > 0).sum()) if len(q_period) else 0,
        "clients_revised": int(q_period[q_period["revision_no"] > 0]["lead_id"].nunique()) if len(q_period) else 0,
        "done_value": done_val, "avg_deal": done_val / len(done) if len(done) else 0.0,
        "pipeline": float(sum(price.get(i, 0) for i in open_["lead_id"])), "open": len(open_),
        "collected": float(pays["amount"].sum()) if len(pays) else 0.0,
        "discount": float(q_period["discount_percent"].astype(float).mean()) if len(q_period) else None,
        "calls": len(calls),
        "_frames": {"all": allm, "assigned": assigned, "done": done, "lost": lost, "lq": lq_all, "orders": orders,
                    "q_period": q_period},
    }


def _team_avg(data, start, role, fn, keys):
    emp = data.get("_employees")
    peers = emp[(emp["role"] == role) & (emp["is_active"] == 1)]["employee_id"] if emp is not None else []
    vals = [fn(e, data, start) for e in peers]
    out = {}
    for k in keys:
        xs = [v[k] for v in vals if v.get(k) is not None]
        out[k] = sum(xs) / len(xs) if xs else None
    return out, len(vals)


def _vs(value, avg, money=False, pct=False):
    if avg is None:
        return ""
    fmt = (lambda v: inr(v)) if money else ((lambda v: f"{v:.0f}%") if pct else (lambda v: f"{v:.1f}".rstrip("0").rstrip(".")))
    return f"team avg {fmt(avg)}"


def _sam_report(emp_id, data, start, window):
    m = sam_metrics(emp_id, data, start)
    keys = ["assigned", "converted", "win_rate", "approved", "clients_revised", "done_value", "pipeline", "collected",
            "discount", "calls"]
    avg, n = _team_avg(data, start, "SAM", sam_metrics, keys)
    f = m["_frames"]
    mine_all, mine, done, lost, lq = f["all"], f["assigned"], f["done"], f["lost"], f["lq"]
    my_orders = f["orders"]

    st.markdown(f"##### 💼 Sales report — {window.lower()}")
    st.caption(f"Each figure is compared with the average of all {n} salespeople for the same period.")
    render_kpi_cards([
        {"label": "Leads assigned", "value": m["assigned"], "icon": "📥", "tone": "blue", "sub": _vs(m["assigned"], avg["assigned"])},
        {"label": "Deals converted (Done)", "value": m["converted"], "icon": "🏆", "tone": "green",
         "sub": _vs(m["converted"], avg["converted"])},
        {"label": "Win rate", "value": f"{m['win_rate']:.0f}%" if m["win_rate"] is not None else "—", "icon": "🎯",
         "tone": "teal", "sub": f"{m['converted']} done · {m['lost']} cancled · " + _vs(0, avg["win_rate"], pct=True)},
        {"label": "Quotations approved", "value": m["approved"], "icon": "✅", "tone": "green", "sub": _vs(0, avg["approved"])},
        {"label": "Clients needing revisions", "value": m["clients_revised"], "icon": "🔁", "tone": "amber",
         "sub": f"{m['revisions']} revisions · " + _vs(0, avg["clients_revised"])},
    ])
    render_kpi_cards([
        {"label": "Done value", "value": inr(m["done_value"]), "icon": "💰", "tone": "green", "sub": _vs(0, avg["done_value"], money=True)},
        {"label": "Open pipeline", "value": inr(m["pipeline"]), "icon": "💼", "tone": "blue",
         "sub": f"{m['open']} open clients · " + _vs(0, avg["pipeline"], money=True)},
        {"label": "Collected", "value": inr(m["collected"]), "icon": "💵", "tone": "teal", "sub": _vs(0, avg["collected"], money=True)},
        {"label": "Average discount", "value": f"{m['discount']:.1f}%" if m["discount"] is not None else "—", "icon": "🏷️",
         "tone": "amber", "sub": _vs(0, avg["discount"], pct=True)},
        {"label": "Calls on these clients", "value": m["calls"], "icon": "📞", "tone": "navy", "sub": _vs(0, avg["calls"])},
    ])
    with st.expander("ℹ️ How these numbers are counted"):
        st.markdown(
            "- **Leads assigned**: leads assigned to this person and *received* in the period.\n"
            "- **Deals converted / cancled**: deals *closed* in the period, whenever the lead arrived — so a deal won this "
            "month from last month's lead counts this month.\n"
            "- **Win rate**: converted ÷ (converted + cancled) in the period.\n"
            "- **Quotations approved / revisions**: quotations *created* in the period for this person's clients.\n"
            "- **Done value**: latest final price of each converted deal. **Open pipeline**: all clients still open, any date.\n"
            "- **Collected**: payments *received* in the period on this person's orders.\n"
            "- **Team average**: the same calculation for every active salesperson, then averaged.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Assigned vs converted, month by month")
        if mine_all.empty:
            st.info("No leads assigned yet.")
        else:
            a = mine_all.assign(month=mine_all["ingested_at"].astype(str).str[:7]).groupby("month").size().rename("Assigned")
            dd = mine_all[mine_all["final_status"] == STAGE_WON]
            c_ = dd.assign(month=dd["closed_at"].astype(str).str[:7]).groupby("month").size().rename("Converted")
            agg = pd.concat([a, c_], axis=1).fillna(0).astype(int).reset_index().rename(columns={"index": "month"}).sort_values("month").tail(6)
            agg = agg[agg["month"].str.match(r"\d{4}-\d{2}")]
            agg["month"] = agg["month"].map(lambda m: datetime.date(int(m[:4]), int(m[5:7]), 1).strftime("%b %Y"))
            fig = go.Figure()
            fig.add_bar(x=agg["month"], y=agg["Assigned"], name="Assigned", marker_color="#C9D6EE", text=agg["Assigned"],
                        textposition="outside", cliponaxis=False)
            fig.add_bar(x=agg["month"], y=agg["Converted"], name="Converted", marker_color=GREEN, text=agg["Converted"],
                        textposition="outside", cliponaxis=False)
            fig.update_layout(barmode="group", bargap=0.35)
            fig.update_xaxes(type="category")
            st.plotly_chart(_layout(fig, 300), width="stretch")
    with c2:
        _hbar(mine, "final_status", "Where the clients stand now")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("###### How many times quotations were revised")
        if lq.empty:
            st.info("No quotations yet.")
        else:
            rv = lq["revision_no"].astype(int).map(lambda r: "No revision" if r == 0 else f"R{r}").value_counts().reset_index()
            rv.columns = ["Revision", "Clients"]
            rv["o"] = rv["Revision"].map(lambda r: 0 if r == "No revision" else int(r[1:]))
            fig = px.bar(rv.sort_values("o"), x="Revision", y="Clients", text="Clients", color_discrete_sequence=[AMBER])
            fig.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(_layout(fig, 280), width="stretch")
    with c4:
        lost_r = lost.assign(reason=lost["lost_reason"].fillna("No reason given")) if not lost.empty else lost
        _hbar(lost_r, "reason", "Why deals were cancelled", "No cancelled deals in this period. 🎉")

    st.markdown("###### Products — value quoted vs value done")
    if lq.empty:
        st.info("No quotations yet.")
    else:
        lqd = lq.assign(done_amt=lq["qut_amount"].where(lq["lead_id"].isin(done["lead_id"]), 0))
        pv = lqd.groupby("product").agg(Quoted=("qut_amount", "sum"), Done=("done_amt", "sum")).reset_index().sort_values("Quoted")
        fig = go.Figure()
        fig.add_bar(y=pv["product"], x=pv["Quoted"], orientation="h", name="Quoted", marker_color="#C9D6EE")
        fig.add_bar(y=pv["product"], x=pv["Done"], orientation="h", name="Done", marker_color=GREEN)
        fig.update_layout(barmode="overlay")
        fig.update_traces(hovertemplate="%{y}: ₹%{x:,.0f}<extra>%{fullData.name}</extra>")
        st.plotly_chart(_layout(fig, 70 + 32 * len(pv)), width="stretch")

    if not my_orders.empty:
        from components.cards import flat
        from utils.payment_plan import stage_label, tracker_html
        st.markdown("###### Orders and payment progress")
        st.markdown("".join(flat(f"""<div class='saas-card' style='padding:12px 18px;'><b style='color:#0E2C68;'>
            {html.escape(str(o['client_id']))} · {html.escape(str(o['client_name']))}</b>
            <span style='color:#64748B;'> · {inr(o['received'])} of {inr(o['order_value'])} · {html.escape(stage_label(o))}</span>
            <div style='margin-top:8px;'>{tracker_html(o, compact=True)}</div></div>""") for _, o in my_orders.iterrows()),
            unsafe_allow_html=True)


# ====================================================================== quotation specialist
def qs_metrics(emp_id, data, start):
    L, Q, G = data["leads"], data["quotes"], data["logs"]
    mine = L[L["claimed_qs_id"] == emp_id] if not L.empty else L
    claimed = filter_by_window(mine, "claimed_at", start)
    sent = filter_by_window(mine[mine["quote_sent_at"].notna()], "quote_sent_at", start)
    quotes = filter_by_window(Q[Q["created_by"] == emp_id], "created_at", start) if not Q.empty else Q
    calls = filter_by_window(G[G["employee_id"] == emp_id], "logged_at", start) if not G.empty else G
    turn = []
    for a, b in zip(sent["claimed_at"], sent["quote_sent_at"]):
        a, b = parse_ts(a), parse_ts(b)
        if a and b and b >= a:
            turn.append((b - a).total_seconds() / 3600)
    return {
        "claimed": len(claimed), "sent": len(sent),
        "revisions": int((quotes["revision_no"] > 0).sum()) if len(quotes) else 0,
        "on_time": (sent["quote_sent_at"].astype(str).str[:10] <= sent["sla_due_date"].astype(str)).mean() * 100 if len(sent) else None,
        "turnaround": sum(turn) / len(turn) if turn else None,
        "value": float(latest_quotes(quotes)["qut_amount"].sum()) if len(quotes) else 0.0,
        "approved": int((quotes["quotation_status"] == "Approved").sum()) if len(quotes) else 0,
        "sent_back": int(((quotes["revision_requested"] == 1) | (quotes["quotation_status"] == "Rejected")).sum()) if len(quotes) else 0,
        "calls": len(calls),
        "_frames": {"sent": sent, "quotes": quotes, "turn": turn},
    }


def _qs_report(emp_id, data, start, window):
    m = qs_metrics(emp_id, data, start)
    keys = ["claimed", "sent", "revisions", "on_time", "turnaround", "value", "approved", "sent_back", "calls"]
    avg, n = _team_avg(data, start, "QS", qs_metrics, keys)
    sent, quotes, turn = m["_frames"]["sent"], m["_frames"]["quotes"], m["_frames"]["turn"]
    st.markdown(f"##### 📄 Quotation report — {window.lower()}")
    st.caption(f"Each figure is compared with the average of all {n} quotation specialists for the same period.")
    render_kpi_cards([
        {"label": "Tickets claimed", "value": m["claimed"], "icon": "📥", "tone": "blue", "sub": _vs(0, avg["claimed"])},
        {"label": "Quotations sent", "value": m["sent"], "icon": "📤", "tone": "green", "sub": _vs(0, avg["sent"])},
        {"label": "Revisions made", "value": m["revisions"], "icon": "🔁", "tone": "amber", "sub": _vs(0, avg["revisions"])},
        {"label": "Sent on time (SLA)", "value": f"{m['on_time']:.0f}%" if m["on_time"] is not None else "—", "icon": "⏱️",
         "tone": "teal", "sub": _vs(0, avg["on_time"], pct=True)},
        {"label": "Average turnaround", "value": f"{m['turnaround']:.1f} h" if m["turnaround"] is not None else "—", "icon": "⚡",
         "tone": "navy", "sub": ("claim → sent · " + (f"team avg {avg['turnaround']:.1f} h" if avg["turnaround"] is not None else ""))},
    ])
    render_kpi_cards([
        {"label": "Value quoted", "value": inr(m["value"]), "icon": "💰", "tone": "blue", "sub": _vs(0, avg["value"], money=True)},
        {"label": "Approved", "value": m["approved"], "icon": "✅", "tone": "green", "sub": _vs(0, avg["approved"])},
        {"label": "Sent back by sales", "value": m["sent_back"], "icon": "↩️", "tone": "red", "sub": _vs(0, avg["sent_back"])},
        {"label": "Calls logged", "value": m["calls"], "icon": "📞", "tone": "amber", "sub": _vs(0, avg["calls"])},
    ])
    with st.expander("ℹ️ How these numbers are counted"):
        st.markdown(
            "- **Tickets claimed**: tickets this person claimed (or was assigned) in the period.\n"
            "- **Quotations sent**: tickets whose first quotation went to the client in the period.\n"
            "- **On time**: sent on or before the SLA date (5:30 PM cutoff rule). **Turnaround**: hours from claim to sent.\n"
            "- **Revisions / approved / sent back / value**: quotations this person created in the period "
            "(value = latest revision per client).\n"
            "- **Team average**: the same calculation for every active quotation specialist.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Quotations sent per day")
        if sent.empty:
            st.info("None in this period.")
        else:
            d = sent.assign(day=pd.to_datetime(sent["quote_sent_at"].astype(str).str[:10])).groupby("day").size().reset_index(name="Sent")
            fig = px.bar(d, x="day", y="Sent", text="Sent", color_discrete_sequence=[TEAL])
            fig.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(_layout(fig, 280), width="stretch")
    with c2:
        st.markdown("###### Turnaround (hours from claim to sent)")
        if not turn:
            st.info("No quotations sent in this period.")
        else:
            fig = px.histogram(pd.DataFrame({"Hours": turn}), x="Hours", nbins=10, color_discrete_sequence=[BLUE])
            fig.update_layout(bargap=0.1)
            st.plotly_chart(_layout(fig, 280), width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        _hbar(quotes, "quotation_status", "Quotation results")
    with c4:
        _hbar(latest_quotes(quotes) if len(quotes) else quotes, "product", "Products quoted")


# ====================================================================== others
def _lge_report(emp_id, data, start):
    L = data["leads"]
    mine = filter_by_window(L[L["handled_by_lge_id"] == emp_id], "ingested_at", start) if not L.empty else L
    render_kpi_cards([
        {"label": "Leads added", "value": len(mine), "icon": "📥", "tone": "blue"},
        {"label": "Reached quotation", "value": f"{mine['quote_sent_at'].notna().mean() * 100:.0f}%" if len(mine) else "—",
         "icon": "📤", "tone": "teal"},
        {"label": "Done", "value": int((mine["final_status"] == STAGE_WON).sum()) if len(mine) else 0, "icon": "🏆", "tone": "green"},
    ])
    c1, c2 = st.columns(2)
    with c1:
        _hbar(mine, "source", "Lead sources")
    with c2:
        _hbar(mine, "final_status", "Stage of these leads")


def _accounts_report(emp_id, data, start):
    P = filter_by_window(data["payments"], "paid_on", start)
    mine = P[P["recorded_by"] == emp_id] if not P.empty else P
    render_kpi_cards([
        {"label": "Collected", "value": inr(mine["amount"].sum()) if len(mine) else "₹0", "icon": "💵", "tone": "green"},
        {"label": "Payments recorded", "value": len(mine), "icon": "🧾", "tone": "blue"},
    ])
    _hbar(mine, "mode", "Payments by mode")
