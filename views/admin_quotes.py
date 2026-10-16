"""
views/admin_quotes.py - Quotation insights for admins (owners), instead of the specialist work screens.

  render_admin_quote_desk : who is working on what, speed, SLA, value, team load
  render_quote_register   : every quotation with filters, discounts and revisions
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.kpi_cards import page_title, render_kpi_cards
from components.time_picker import fmt_12h
from config.settings import QUOTE_COMPANIES, REPORTING_WINDOWS
from utils.metrics import filter_by_window, inr, latest_quotes, open_leads
from utils.time_utils import parse_ts, today_ist, window_start
from views.employee_progress import BLUE, GREEN, RED, TEAL, _layout

PALETTE = ["#184B9C", "#00A859", "#0E7490", "#B45309", "#7C3AED", "#BE123C", "#0284C7"]


def _hours(a, b):
    a, b = parse_ts(a), parse_ts(b)
    return (b - a).total_seconds() / 3600 if a and b and b >= a else None


def render_admin_quote_desk(db_adapter, current_user):
    page_title("Quotation desk — team insight", "Who is working on what, how fast, and how much is being quoted.")
    window = st.segmented_control("Period", list(REPORTING_WINDOWS.keys()), default="This month", key="aq_window") or "This month"
    start = window_start(REPORTING_WINDOWS[window])
    L, Q, E = db_adapter.fetch_all("leads_master"), db_adapter.fetch_all("quotations_master"), db_adapter.fetch_all("employees")
    if L.empty:
        st.info("No leads yet.")
        return
    today = str(today_ist())
    active = open_leads(L)
    waiting = active[active["quotation_status"] != "Sent"]
    unclaimed = waiting[waiting["claimed_qs_id"].isna()]
    sent = filter_by_window(L[L["quote_sent_at"].notna()], "quote_sent_at", start)
    qp = filter_by_window(Q, "created_at", start)
    lq = latest_quotes(Q)
    turn = [h for h in (_hours(a, b) for a, b in zip(sent["claimed_at"], sent["quote_sent_at"])) if h is not None]
    on_time = (sent["quote_sent_at"].astype(str).str[:10] <= sent["sla_due_date"].astype(str)).mean() * 100 if len(sent) else None
    under_review = lq[(lq["quotation_status"] == "Under Review")] if not lq.empty else lq
    sent_back = lq[(lq["revision_requested"] == 1) & ~lq["final_status"].isin(["Done", "Cancled"])] if not lq.empty else lq

    render_kpi_cards([
        {"label": "Waiting for a quotation", "value": len(waiting), "icon": "📥", "tone": "amber",
         "sub": f"{len(unclaimed)} unclaimed · {int((waiting['sla_due_date'].astype(str) < today).sum())} past SLA"},
        {"label": f"Quotations sent ({window.lower()})", "value": len(sent), "icon": "📤", "tone": "green"},
        {"label": "Sent on time", "value": f"{on_time:.0f}%" if on_time is not None else "—", "icon": "⏱️", "tone": "teal",
         "sub": "within the 5:30 PM SLA"},
        {"label": "Average turnaround", "value": f"{sum(turn) / len(turn):.1f} h" if turn else "—", "icon": "⚡", "tone": "navy",
         "sub": "claim → sent"},
        {"label": "Value quoted", "value": inr(latest_quotes(qp)["qut_amount"].sum()) if len(qp) else "₹0", "icon": "💰", "tone": "blue",
         "sub": f"{len(qp)} quotations & revisions"},
    ])
    render_kpi_cards([
        {"label": "Waiting for salesperson approval", "value": len(under_review), "icon": "🖊️", "tone": "teal"},
        {"label": "Sent back for revision", "value": len(sent_back), "icon": "↩️", "tone": "red"},
        {"label": "Revisions made", "value": int((qp["revision_no"] > 0).sum()) if len(qp) else 0, "icon": "🔁", "tone": "amber"},
        {"label": "Average discount", "value": f"{qp['discount_percent'].astype(float).mean():.1f}%" if len(qp) else "—",
         "icon": "🏷️", "tone": "navy"},
    ])

    # ---------------- per specialist
    qs = E[(E["role"] == "QS") & (E["is_active"] == 1)]
    rows = []
    for _, e in qs.iterrows():
        me = e["employee_id"]
        my_wait = waiting[waiting["claimed_qs_id"] == me]
        my_sent = sent[sent["claimed_qs_id"] == me]
        my_q = qp[qp["created_by"] == me]
        t = [h for h in (_hours(a, b) for a, b in zip(my_sent["claimed_at"], my_sent["quote_sent_at"])) if h is not None]
        ot = (my_sent["quote_sent_at"].astype(str).str[:10] <= my_sent["sla_due_date"].astype(str)).mean() * 100 if len(my_sent) else None
        rows.append({"Specialist": e["full_name"] + (" ⭐" if int(e.get("is_team_lead") or 0) else ""),
                     "Open tickets": len(my_wait), "Past SLA": int((my_wait["sla_due_date"].astype(str) < today).sum()),
                     "Sent": len(my_sent), "Revisions": int((my_q["revision_no"] > 0).sum()) if len(my_q) else 0,
                     "Turnaround (h)": round(sum(t) / len(t), 1) if t else None,
                     "On time %": round(ot) if ot is not None else None,
                     "Value quoted": latest_quotes(my_q)["qut_amount"].sum() if len(my_q) else 0.0})
    team = pd.DataFrame(rows)
    st.markdown("##### Team at a glance")
    if team.empty:
        st.info("No active quotation specialists.")
    else:
        show = team.copy()
        show["Value quoted"] = show["Value quoted"].map(inr)
        st.dataframe(show, width="stretch", hide_index=True,
                     column_config={"On time %": st.column_config.ProgressColumn("On time %", min_value=0, max_value=100, format="%d%%"),
                                    "Open tickets": st.column_config.ProgressColumn("Open tickets", min_value=0,
                                                                                   max_value=max(1, int(team["Open tickets"].max())),
                                                                                   format="%d")})
        st.caption("⭐ = team lead")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("###### Quotations sent per day, by specialist")
        if sent.empty:
            st.info("None in this period.")
        else:
            d = sent.assign(day=pd.to_datetime(sent["quote_sent_at"].astype(str).str[:10]),
                            who=sent["claimed_qs_name"].fillna("Unassigned")).groupby(["day", "who"]).size().reset_index(name="Sent")
            fig = px.bar(d, x="day", y="Sent", color="who", color_discrete_sequence=PALETTE)
            fig.update_layout(barmode="stack", bargap=0.25)
            st.plotly_chart(_layout(fig, 300), width="stretch")
    with c2:
        st.markdown("###### Turnaround by specialist (hours)")
        tt = pd.DataFrame([{"Specialist": n, "Hours": _hours(a, b)} for n, a, b in
                           zip(sent["claimed_qs_name"].fillna("—"), sent["claimed_at"], sent["quote_sent_at"])]).dropna()
        if tt.empty:
            st.info("None in this period.")
        else:
            fig = px.box(tt, x="Hours", y="Specialist", points="all", color="Specialist", color_discrete_sequence=PALETTE)
            fig.update_layout(showlegend=False)
            st.plotly_chart(_layout(fig, 300), width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("###### Value quoted by company")
        if qp.empty:
            st.info("None in this period.")
        else:
            lqp = latest_quotes(qp)
            co = lqp.assign(Company=lqp["quotation_number"].str.split("/").str[0]).groupby("Company")["qut_amount"].sum().reset_index()
            fig = px.pie(co, values="qut_amount", names="Company", hole=0.55, color_discrete_sequence=[BLUE, GREEN, TEAL])
            fig.update_traces(textinfo="label+percent", hovertemplate="%{label}: ₹%{value:,.0f}<extra></extra>")
            st.plotly_chart(_layout(fig, 280), width="stretch")
    with c4:
        st.markdown("###### Tickets waiting, by age")
        if waiting.empty:
            st.success("Nothing is waiting.")
        else:
            age = waiting.assign(days=waiting["ingested_at"].map(lambda v: (today_ist() - parse_ts(v).date()).days if parse_ts(v) else 0))
            age["Age"] = pd.cut(age["days"], [-1, 0, 1, 3, 7, 10_000], labels=["Today", "1 day", "2–3 days", "4–7 days", "Over a week"])
            ag = age.groupby(["Age", age["claimed_qs_id"].isna().map({True: "Unclaimed", False: "Claimed"})], observed=False).size().reset_index(name="Tickets")
            ag.columns = ["Age", "State", "Tickets"]
            fig = px.bar(ag, x="Age", y="Tickets", color="State", text="Tickets",
                         color_discrete_map={"Unclaimed": RED, "Claimed": BLUE})
            fig.update_layout(barmode="stack")
            st.plotly_chart(_layout(fig, 280), width="stretch")
            st.caption("Move stuck tickets from 🔀 Reassign & escalate.")


def render_quote_register(db_adapter, current_user):
    page_title("Quotation register", "Every quotation and revision — filter, compare and export.")
    Q = db_adapter.fetch_all("quotations_master")
    if Q.empty:
        st.info("No quotations yet.")
        return
    window = st.segmented_control("Period", list(REPORTING_WINDOWS.keys()), default="This month", key="qr_window") or "This month"
    q = filter_by_window(Q, "created_at", window_start(REPORTING_WINDOWS[window]))
    f1, f2, f3, f4 = st.columns([1.5, 1, 1, 1])
    with f1:
        s = st.text_input("Search", placeholder="Client ID, client, company or quotation no.", key="qr_q").strip().lower()
    with f2:
        who = st.multiselect("Specialist", sorted(Q["claimed_qs_name"].dropna().unique()), placeholder="All", key="qr_who")
    with f3:
        comp = st.multiselect("Quoting company", list(QUOTE_COMPANIES.keys()), placeholder="All", key="qr_co")
    with f4:
        stat = st.multiselect("Status", ["Approved", "Under Review", "Rejected"], placeholder="All", key="qr_st")
    only_latest = st.toggle("Show only the latest revision per client", value=True, key="qr_latest")
    if only_latest:
        q = latest_quotes(q)
    if s:
        hay = (q["client_id"].astype(str) + " " + q["client_name"].astype(str) + " " + q["company_name"].fillna("").astype(str)
               + " " + q["quotation_ref"].astype(str)).str.lower()
        q = q[hay.str.contains(s, regex=False)]
    if who:
        q = q[q["claimed_qs_name"].isin(who)]
    if comp:
        q = q[q["quotation_number"].str.split("/").str[0].isin(comp)]
    if stat:
        q = q[q["quotation_status"].isin(stat)]

    render_kpi_cards([
        {"label": "Quotations", "value": len(q), "icon": "📄", "tone": "blue", "sub": f"{q['client_id'].nunique()} clients"},
        {"label": "Total final value", "value": inr(q["qut_amount"].sum()), "icon": "💰", "tone": "green"},
        {"label": "Discount given", "value": inr(q["discount_amount"].astype(float).sum()), "icon": "🏷️", "tone": "amber",
         "sub": f"avg {q['discount_percent'].astype(float).mean():.1f}%" if len(q) else ""},
        {"label": "Approved", "value": f"{(q['quotation_status'] == 'Approved').mean() * 100:.0f}%" if len(q) else "—",
         "icon": "✅", "tone": "teal"},
    ])
    q = q.sort_values("created_at", ascending=False)
    table = pd.DataFrame({
        "Client ID": q["client_id"], "Client": q["client_name"], "Company": q["company_name"], "Quotation": q["quotation_ref"],
        "Product": q["product"] + " × " + q["qty"].astype(str), "List price": q["gross_amount"].map(inr),
        "Discount": [f"{inr(a)} ({p:.1f}%)" if a else "—" for a, p in zip(q["discount_amount"].astype(float), q["discount_percent"].astype(float))],
        "Final price": q["qut_amount"].map(inr), "Status": q["quotation_status"], "Client stage": q["final_status"],
        "Specialist": q["claimed_qs_name"].fillna("—"), "Salesperson": q["assigned_salesperson"].fillna("—"),
        "Created": q["created_at"].map(fmt_12h)})
    st.dataframe(table, width="stretch", hide_index=True, height=460)
    st.download_button("Download (CSV)", table.to_csv(index=False).encode("utf-8"), file_name="quotation_register.csv",
                       mime="text/csv")
