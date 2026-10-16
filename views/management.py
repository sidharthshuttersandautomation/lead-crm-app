"""
views/management.py - Management modules (admin):
  1. Business tower: funnel, revenue, bottlenecks
  2. Team performance: QS load, LGE scorecard, SAM win/loss
  3. Reassign & escalate: reassignment, priority, revision governance
  4. Master export & governance: 360° export, audit export, backup
"""
import datetime
import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.kpi_cards import render_kpi_cards
from config.settings import (HIGH_REVISION_ALERT, REPORTING_WINDOWS, STAGE_PROBABILITY, STALE_FOLLOWUP_DAYS,
                             UNCLAIMED_ALERT_WORK_HOURS, UNDER_REVIEW_ALERT_HOURS)
from utils import analytics as an
from utils.governance import reassign_leads, set_priority
from utils.metrics import filter_by_window, inr, latest_quotes, open_leads
from utils.time_utils import now_ist, today_ist, window_start

BLUE, NAVY, GREEN, RED, AMBER = "#184B9C", "#0E2C68", "#00A859", "#BE123C", "#B45309"


def _title(text, caption=None):
    st.markdown(f"<h2 style='color:{NAVY}; font-weight:800; margin-bottom:0;'>{text}</h2>", unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def _period(key, default="Last 30 days"):
    labels = list(REPORTING_WINDOWS.keys())
    choice = st.selectbox("Period (by lead received date)", labels, index=labels.index(default), key=key)
    return choice, window_start(REPORTING_WINDOWS[choice])


def _now():
    return now_ist().replace(tzinfo=None)


def _show(df, cols, rename=None, money=()):
    view = df[[c for c in cols if c in df.columns]].copy()
    for c in money:
        if c in view.columns:
            view[c] = view[c].map(inr)
    if rename:
        view = view.rename(columns=rename)
    st.dataframe(view, width="stretch", hide_index=True)


# ====================================================================== 1
def render_business_tower(db_adapter, current_user):
    _title("Business tower", "Live funnel, revenue and the places where work is stuck.")
    period, start = _period("tower_period")

    all_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_logs = db_adapter.fetch_all("followup_logs")
    if all_leads.empty:
        st.info("No leads yet.")
        return
    leads = filter_by_window(all_leads, "ingested_at", start)
    now = _now()

    # --- funnel
    sla = an.dispatch_sla(leads)
    under_process = int((open_leads(leads)["quotation_status"] == "Under Process").sum()) if not leads.empty else 0
    render_kpi_cards([
        {"label": "Leads received", "value": len(leads), "icon": "📥", "tone": "blue"},
        {"label": "Quotes in progress", "value": under_process, "help": "Claimed, quotation not yet sent",
         "icon": "📝", "tone": "amber"},
        {"label": "Sent within cutoff", "value": f"{sla['rate'] * 100:.0f}%" if sla["rate"] is not None else "—",
         "help": f"{sla['on_time']} of {sla['sent']} quotations sent by their 5:30 PM SLA date",
         "icon": "⏱️", "tone": "teal", "sub": f"{sla['on_time']} of {sla['sent']} on time"},
        {"label": "Done", "value": int((leads["final_status"] == "Done").sum()) if not leads.empty else 0,
         "icon": "🏆", "tone": "green"},
        {"label": "Cancled", "value": int((leads["final_status"] == "Cancled").sum()) if not leads.empty else 0,
         "icon": "✖️", "tone": "red"},
    ])

    c1, c2 = st.columns([1, 1.3])
    with c1:
        st.markdown("##### Conversion funnel")
        f = an.funnel(leads)
        if f.empty or f["Leads"].sum() == 0:
            st.info("No leads in this period.")
        else:
            fig = go.Figure(go.Funnel(y=f["Stage"], x=f["Leads"], textinfo="value+percent initial",
                                      marker={"color": [BLUE, "#2D68C4", "#0284C7", GREEN]}))
            fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, width="stretch")

    # --- revenue (whole pipeline, not period-limited)
    with c2:
        st.markdown("##### Revenue (₹)")
        rev = an.revenue_summary(all_leads, df_quotes)
        render_kpi_cards([
            {"label": "Active quotations", "value": inr(rev["active_value"]),
             "help": "Latest revision of every open lead, excluding rejected"},
            {"label": "Approved & open", "value": inr(rev["approved_value"])},
            {"label": "Expected realization", "value": inr(rev["expected_value"]),
             "help": "Active value × stage probability: " +
                     ", ".join(f"{k} {int(v * 100)}%" for k, v in STAGE_PROBABILITY.items())},
        ])
        mr = an.monthly_revenue(all_leads, df_quotes)
        if mr.empty:
            st.info("No approved or won value yet.")
        else:
            fig = px.bar(mr, x="Month", y="Value", color="Series", barmode="group",
                         color_discrete_map={"Approved quotations": BLUE, "Done deals": GREEN})
            fig.update_layout(height=250, margin=dict(t=10, b=10, l=10, r=10), legend_title_text="",
                              yaxis_title="₹", xaxis_title="")
            st.plotly_chart(fig, width="stretch")

    # --- sales & collections
    orders = db_adapter.fetch_all("orders")
    if not orders.empty:
        st.markdown("##### Sales & collections")
        booked, received = float(orders["order_value"].sum()), float(orders["received"].sum())
        render_kpi_cards([
            {"label": "Total sales booked", "value": inr(booked), "icon": "🧾", "tone": "blue",
             "sub": f"{len(orders)} orders"},
            {"label": "Payment received", "value": inr(received), "icon": "✅", "tone": "green",
             "sub": f"{received / booked * 100:.0f}% collected" if booked else ""},
            {"label": "Left to collect", "value": inr(orders["balance"].clip(lower=0).sum()), "icon": "⏳", "tone": "red",
             "sub": f"{int((orders['balance'] > 0.5).sum())} orders · details in Sales & collections"},
        ])

    # --- bottlenecks (live, all leads)
    st.markdown("---")
    st.markdown("##### Bottlenecks right now")
    unclaimed = an.unclaimed_bottlenecks(all_leads, now)
    stale = an.stale_followups(all_leads, df_logs, now)
    pending = an.pending_dispatches(df_quotes, now)
    render_kpi_cards([
        {"label": f"Unclaimed > {UNCLAIMED_ALERT_WORK_HOURS} working hrs", "value": len(unclaimed)},
        {"label": f"No calls for > {STALE_FOLLOWUP_DAYS} days", "value": len(stale)},
        {"label": "Quotes under review", "value": len(pending),
         "help": f"{int(pending['overdue'].sum()) if not pending.empty else 0} waiting more than {UNDER_REVIEW_ALERT_HOURS} h"},
        {"label": "Reminders snoozed today", "icon": "😴", "tone": "amber",
         "value": int((db_adapter.fetch_all("call_snoozes").get("snoozed_at", pd.Series(dtype=str)).astype(str).str[:10]
                       == str(today_ist())).sum()),
         "sub": "details in Team performance"},
    ])
    t1, t2, t3 = st.tabs([f"Unclaimed tickets ({len(unclaimed)})", f"Stale follow-ups ({len(stale)})",
                          f"Pending dispatch ({len(pending)})"])
    with t1:
        if unclaimed.empty:
            st.success("No ticket has waited too long.")
        else:
            _show(unclaimed, ["client_id", "client_name", "company_name", "product", "priority", "source",
                              "ingested_at", "waiting_work_hours", "sla_due_date"],
                  {"waiting_work_hours": "Waiting (working hrs)"})
            st.caption("Reassign these from Reassign & escalate.")
    with t2:
        if stale.empty:
            st.success("Every quoted lead has recent call activity.")
        else:
            _show(stale, ["client_id", "client_name", "company_name", "followup_owner_name", "final_status",
                          "last_activity", "days_silent", "next_followup_at"],
                  {"followup_owner_name": "Owner", "days_silent": "Days silent"})
    with t3:
        if pending.empty:
            st.success("No quotation is waiting for approval.")
        else:
            _show(pending, ["quotation_ref", "client_name", "qut_amount", "claimed_qs_name",
                            "assigned_salesperson", "created_at", "hours_waiting", "overdue"],
                  {"claimed_qs_name": "QS", "hours_waiting": "Hours waiting"}, money=("qut_amount",))


# ====================================================================== 2
def render_team_performance(db_adapter, current_user):
    _title("Team performance", "Workload today and results over the chosen period.")
    all_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_emp = db_adapter.fetch_all("employees")
    if all_leads.empty:
        st.info("No leads yet.")
        return

    st.markdown("##### Quotation desk load (live)")
    load = an.qs_load(all_leads, df_quotes, df_emp, today_ist())
    if load.empty:
        st.info("No active quotation specialists.")
    else:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            long = load.melt(id_vars="Specialist", value_vars=["Open tickets", "Under review", "Follow-ups owned"],
                             var_name="Work", value_name="Count")
            fig = px.bar(long, x="Specialist", y="Count", color="Work", barmode="group",
                         color_discrete_sequence=[BLUE, AMBER, GREEN])
            fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10), legend_title_text="")
            st.plotly_chart(fig, width="stretch")
        with c2:
            _show(load, ["Specialist", "Open tickets", "Past SLA", "Under review", "Sent today",
                         "Follow-ups owned", "Load"])
            over = load[load["Load"] == "Overloaded"]
            if not over.empty:
                st.warning("Overloaded: " + ", ".join(over["Specialist"]) +
                           ". Move tickets from Reassign & escalate.")

    _snooze_section(db_adapter)

    st.markdown("---")
    period, start = _period("team_period", "Last 3 months")
    leads = filter_by_window(all_leads, "ingested_at", start)
    if leads.empty:
        st.info("No leads in this period.")
        return

    st.markdown("##### Lead quality by who added the lead and source")
    from config.settings import LEAD_ADDER_ROLES
    lge = an.lge_scorecard(leads)
    emp = db_adapter.fetch_all("employees")
    adders = emp[emp["role"].isin(LEAD_ADDER_ROLES) & (emp["is_active"] == 1)]
    role_of = dict(zip(emp["full_name"], emp["role"]))
    names = sorted(set(adders["full_name"]) | set(lge["Added by"].dropna()))
    pick = st.selectbox("Added by", ["Everyone"] + [f"{n} ({role_of.get(n, '—')})" for n in names], key="lge_pick")
    who = None if pick == "Everyone" else pick.rsplit(" (", 1)[0]
    view = lge if who is None else lge[lge["Added by"] == who]
    if view.empty:
        st.info(f"{who} hasn't added any leads in this period.")
    else:
        by_source = view.groupby("Source", as_index=False)[["Leads", "Quoted", "Done"]].sum().sort_values("Leads")
        c1, c2 = st.columns([1, 1.2])
        with c1:
            tot = by_source[["Leads", "Quoted", "Done"]].sum()
            render_kpi_cards([
                {"label": "Leads added", "value": int(tot["Leads"]), "icon": "📥", "tone": "blue"},
                {"label": "Got a quotation", "value": f"{tot['Quoted'] / tot['Leads'] * 100:.0f}%" if tot["Leads"] else "—",
                 "icon": "📤", "tone": "teal", "sub": f"{int(tot['Quoted'])} leads"},
                {"label": "Became Done", "value": f"{tot['Done'] / tot['Leads'] * 100:.0f}%" if tot["Leads"] else "—",
                 "icon": "🏆", "tone": "green", "sub": f"{int(tot['Done'])} deals"},
            ], columns=1)
        with c2:
            st.markdown("###### By source: leads → quoted → done")
            fig = go.Figure()
            for col, color in [("Leads", "#C9D6EE"), ("Quoted", BLUE), ("Done", GREEN)]:
                fig.add_bar(y=by_source["Source"], x=by_source[col], name=col, orientation="h", marker_color=color,
                            text=by_source[col], textposition="outside", cliponaxis=False)
            fig.update_layout(barmode="group", bargap=0.25, height=90 + 70 * len(by_source),
                              margin=dict(t=10, b=10, l=10, r=30), legend=dict(orientation="h", y=1.08),
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
        with st.expander("Table by person and source"):
            st.dataframe(view, width="stretch", hide_index=True)

    st.markdown("##### Salesperson results")
    sam = an.sam_matrix(leads, df_quotes)
    if sam.empty:
        st.info("No salesperson data in this period.")
    else:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            st.markdown("###### Done, cancled and still open — per salesperson")
            ss = sam.sort_values("Leads")
            fig = go.Figure()
            for col, color in [("Done", GREEN), ("Cancled", RED), ("Open", "#C9D6EE")]:
                fig.add_bar(y=ss["Salesperson"], x=ss[col], name=col, orientation="h", marker_color=color,
                            text=ss[col].where(ss[col] > 0, ""), textposition="inside", insidetextanchor="middle")
            fig.update_layout(barmode="stack", bargap=0.3, height=90 + 55 * len(ss), margin=dict(t=10, b=10, l=10, r=10),
                              legend=dict(orientation="h", y=1.1), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
        with c2:
            st.markdown("###### Why deals were cancelled")
            lost = leads[leads["final_status"] == "Cancled"]
            if lost.empty:
                st.success("No cancelled deals in this period.")
            else:
                rc = lost.assign(Reason=lost["lost_reason"].fillna("No reason given")).groupby(["Reason", "assigned_salesperson"]) \
                    .size().reset_index(name="Deals")
                order = rc.groupby("Reason")["Deals"].sum().sort_values().index.tolist()
                fig = px.bar(rc, x="Deals", y="Reason", color="assigned_salesperson", orientation="h", text="Deals",
                             category_orders={"Reason": order[::-1]}, color_discrete_sequence=[BLUE, "#B45309", "#0E7490", "#7C3AED"])
                fig.update_layout(barmode="stack", height=90 + 45 * len(order), margin=dict(t=10, b=10, l=10, r=10),
                                  legend_title_text="", legend=dict(orientation="h", y=1.12),
                                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", yaxis_title="", xaxis_title="Deals")
                st.plotly_chart(fig, width="stretch")
        _show(sam.rename(columns={"Won value": "Done value"}), [c if c != "Won value" else "Done value" for c in sam.columns],
              money=("Done value", "Avg deal", "Biggest deal"))

    # ---------------- targets overview
    st.markdown("---")
    st.markdown("##### 🎯 Targets this month")
    from utils.targets import load_data, month_key, target_table
    tt = target_table(db_adapter, emp[emp["is_active"] == 1], month_key(), load_data(db_adapter))
    if tt.empty:
        st.info("No targets set for this month. Set them in 📈 Employee report card.")
    else:
        st.dataframe(tt, width="stretch", hide_index=True,
                     column_config={"Progress %": st.column_config.ProgressColumn("Progress %", min_value=0, max_value=100, format="%d%%"),
                                    "Expected by today %": st.column_config.NumberColumn(format="%d%%")})


# ====================================================================== 3
def render_reassign_escalate(db_adapter, current_user):
    _title("Reassign & escalate", "Move tickets between people, pin urgent leads, and review price negotiations.")
    all_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_logs = db_adapter.fetch_all("followup_logs")
    df_emp = db_adapter.fetch_all("employees")
    if all_leads.empty:
        st.info("No leads yet.")
        return
    active_emp = df_emp[df_emp["is_active"] == 1]
    now = _now()

    tab_move, tab_prio, tab_rev = st.tabs(["Reassign tickets", "Priority", "Revision governance"])

    # ---------------- reassign
    with tab_move:
        scope = st.segmented_control("Show", ["Stuck unclaimed", "Past SLA", "Stale follow-ups", "All open"],
                                     default="Stuck unclaimed", key="ra_scope")
        active = open_leads(all_leads)
        if scope == "Stuck unclaimed":
            pool = an.unclaimed_bottlenecks(all_leads, now)
        elif scope == "Past SLA":
            pool = active[(active["quotation_status"] != "Sent") &
                          (active["sla_due_date"].astype(str) < str(today_ist()))]
        elif scope == "Stale follow-ups":
            pool = an.stale_followups(all_leads, df_logs, now)
        else:
            pool = active

        if pool.empty:
            st.success("Nothing to reassign in this view.")
        else:
            table = pool[["lead_id", "client_id", "client_name", "product", "priority", "claimed_qs_name",
                          "assigned_salesperson", "followup_owner_name", "quotation_status", "final_status"]].copy()
            table.insert(0, "Select", False)
            edited = st.data_editor(
                table, hide_index=True, width="stretch", key=f"ra_table_{scope}",
                disabled=[c for c in table.columns if c != "Select"],
                column_config={"lead_id": None, "Select": st.column_config.CheckboxColumn(width="small"),
                               "claimed_qs_name": "QS", "assigned_salesperson": "SAM",
                               "followup_owner_name": "Calls by"})
            chosen = pool[pool["lead_id"].isin(edited.loc[edited["Select"], "lead_id"])]

            c1, c2, c3 = st.columns([1, 1.3, 1.6])
            with c1:
                move_opts = ["Quotation specialist", "Salesperson", "Follow-up calls"] if current_user["role"] == "ADMIN" \
                    else ["Quotation specialist", "Follow-up calls"]
                target = st.selectbox("Move", move_opts, key="ra_target")
            role_for = {"Quotation specialist": ["QS"], "Salesperson": ["SAM"],
                        "Follow-up calls": ["QS", "SAM", "LGE", "ADMIN"]}[target]
            people = active_emp[active_emp["role"].isin(role_for)]
            with c2:
                person = st.selectbox("To", list(people["full_name"] + " (" + people["employee_id"] + ")"), key="ra_person")
            with c3:
                reason = st.text_input("Reason *", placeholder="e.g. Pooja on leave today", key="ra_reason")

            if st.button(f"Reassign {len(chosen)} selected", disabled=chosen.empty, key="ra_go"):
                if not reason.strip():
                    st.error("Give a reason. It is saved in the audit trail.")
                else:
                    emp_id = person.split("(")[-1].rstrip(")")
                    key = {"Quotation specialist": "QS", "Salesperson": "SAM", "Follow-up calls": "FOLLOWUP"}[target]
                    moved, errors = reassign_leads(db_adapter, chosen, key, emp_id, reason.strip())
                    for e in errors:
                        st.error(e)
                    st.toast(f"Moved {moved} lead(s) to {person.split(' (')[0]}.", icon="✅")
                    st.rerun()

    # ---------------- priority
    with tab_prio:
        active = open_leads(all_leads)
        lq = latest_quotes(df_quotes)
        amounts = dict(zip(lq["lead_id"], lq["qut_amount"])) if not lq.empty else {}
        table = active[["lead_id", "client_id", "client_name", "company_name", "product", "priority",
                        "is_key_account", "final_status"]].copy()
        table["quote_value"] = table["lead_id"].map(lambda i: amounts.get(i, 0))
        min_value = st.number_input("Show leads with quotation value of at least (₹)", min_value=0, value=0, step=50000)
        table = table[table["quote_value"] >= min_value].sort_values("quote_value", ascending=False)
        table.insert(0, "Select", False)
        table["quote_value"] = table["quote_value"].map(inr)
        edited = st.data_editor(table, hide_index=True, width="stretch", key="prio_table",
                                disabled=[c for c in table.columns if c != "Select"],
                                column_config={"lead_id": None, "Select": st.column_config.CheckboxColumn(width="small"),
                                               "is_key_account": st.column_config.CheckboxColumn("Key account")})
        chosen = active[active["lead_id"].isin(edited.loc[edited["Select"], "lead_id"])]
        p1, p2, p3 = st.columns([1.6, 1, 1])
        with p1:
            reason = st.text_input("Reason *", placeholder="e.g. ₹8 lakh order, decision this week", key="prio_reason")
        with p2:
            up = st.button(f"Mark {len(chosen)} High priority", disabled=chosen.empty, key="prio_up")
        with p3:
            down = st.button(f"Set {len(chosen)} to Normal", disabled=chosen.empty, key="prio_down")
        if up or down:
            if not reason.strip():
                st.error("Give a reason. It is saved in the audit trail.")
            else:
                n = set_priority(db_adapter, chosen, "High" if up else "Normal", reason.strip())
                st.toast(f"Updated priority on {n} lead(s).", icon="✅")
                st.rerun()
        st.caption("High-priority leads are pinned to the top of the quotation desk and follow-up queues.")

    # ---------------- revision governance
    with tab_rev:
        gov = an.revision_governance(df_quotes)
        if gov.empty:
            st.info("No quotations yet.")
        else:
            flagged = gov[gov["Flag"] != ""]
            render_kpi_cards([
                {"label": "Quotations", "value": len(gov)},
                {"label": "Revised at least once", "value": int((gov["Revisions"] > 0).sum())},
                {"label": f"R{HIGH_REVISION_ALERT}+ (high negotiation)", "value": len(flagged)},
                {"label": "Average price change", "value": f"{gov['Change %'].dropna().mean():+.1f}%"},
            ])
            only_flagged = st.toggle(f"Only R{HIGH_REVISION_ALERT} and above", value=False)
            view = flagged if only_flagged else gov
            _show(view, [c for c in view.columns if c != "lead_id"], money=("R0 amount", "Latest amount"))

            pick = st.selectbox("Revision history for", list(view["Quotation"] + " · " + view["Client"]))
            number = pick.split(" · ")[0]
            hist = df_quotes[df_quotes["quotation_number"] == number].sort_values("revision_no")
            _show(hist, ["quotation_ref", "qut_amount", "quotation_status", "approved_by", "quotation_shared_by",
                         "revision_reason", "created_at"], money=("qut_amount",))
            if len(hist) > 1:
                fig = px.line(hist, x="quotation_ref", y="qut_amount", markers=True, color_discrete_sequence=[BLUE])
                fig.update_layout(height=240, margin=dict(t=10, b=10, l=10, r=10), xaxis_title="", yaxis_title="₹")
                st.plotly_chart(fig, width="stretch")


# ====================================================================== 4
def _lead_360(df_leads, df_quotes, df_logs, df_orders):
    """One row per lead: lead + latest quotation + call summary + order."""
    lq = latest_quotes(df_quotes)
    out = df_leads.copy()
    if not lq.empty:
        q = lq[["lead_id", "quotation_ref", "revision_no", "qut_amount", "quotation_status", "approved_by",
                "quotation_shared_by", "approved_date"]].rename(columns={
            "quotation_ref": "latest_quotation", "revision_no": "revisions", "qut_amount": "latest_amount",
            "quotation_status": "latest_quote_status", "approved_by": "quote_approved_by",
            "quotation_shared_by": "quote_shared_by", "approved_date": "quote_approved_date"})
        out = out.merge(q, on="lead_id", how="left")
    if not df_quotes.empty:
        first = df_quotes.sort_values("revision_no").groupby("lead_id").head(1)[["lead_id", "qut_amount"]]
        out = out.merge(first.rename(columns={"qut_amount": "first_amount"}), on="lead_id", how="left")
    if not df_logs.empty:
        calls = df_logs.sort_values("logged_at").groupby("lead_id").agg(
            calls_logged=("followup_id", "count"), last_call_at=("logged_at", "last"),
            last_call_outcome=("followup_status", "last"), last_call_note=("notes", "last"),
            last_call_by=("employee_name", "last")).reset_index()
        out = out.merge(calls, on="lead_id", how="left")
    if not df_orders.empty:
        o = df_orders[["lead_id", "order_id", "payment_status", "production_status", "dispatch_status"]]
        out = out.merge(o, on="lead_id", how="left")
    hidden = {"product_id", "handled_by_lge_id", "assigned_sam_id", "claimed_qs_id", "followup_owner_id"}
    return out[[c for c in out.columns if c not in hidden]]


def render_master_export(db_adapter, current_user):
    _title("Master export & governance", "Complete data downloads, activity history and backups.")
    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")
    df_logs = db_adapter.fetch_all("followup_logs")
    df_orders = db_adapter.fetch_all("orders")

    tab_exp, tab_activity, tab_backup, tab_clear = st.tabs(["360° export", "Login & change activity", "Backup",
                                                            "🧹 Clear all data"])
    with tab_clear:
        st.warning("This deletes every client, lead, quotation, call, order, payment, PO check, snooze and target. "
                   "Users, products and the audit trail are kept. Download a backup first.")
        counts = {t: db_adapter.count_rows(t) for t in ("leads_master", "quotations_master", "followup_logs", "orders", "payments")}
        st.caption(" · ".join(f"{k.replace('_master', '').replace('_', ' ')}: {v}" for k, v in counts.items()))
        word = st.text_input("Type CLEAR to confirm", key="clear_word")
        if st.button("Delete all lead data", key="clear_go", disabled=word.strip().upper() != "CLEAR"):
            done = db_adapter.clear_lead_data()
            st.success("Cleared: " + ", ".join(f"{v} {k}" for k, v in done.items()))
            st.caption("To stop demo data coming back after a restart, set seed_demo_data = \"false\" in Secrets.")


    with tab_exp:
        if df_leads.empty:
            st.info("No leads yet.")
        else:
            today = today_ist()
            d1, d2, d3 = st.columns([1, 1, 1.4])
            with d1:
                start = st.date_input("Leads received from", value=today - datetime.timedelta(days=30), key="mx_from")
            with d2:
                end = st.date_input("To", value=today, key="mx_to")
            with d3:
                shape = st.radio("Format", ["One row per lead", "Excel workbook, one sheet per table"],
                                 key="mx_shape", help="One row per lead shows the latest quotation and a call summary. "
                                                      "The workbook keeps every revision and every call.")
            dates = pd.to_datetime(df_leads["ingestion_date"], errors="coerce").dt.date
            leads = df_leads[(dates >= start) & (dates <= end)]
            ids = set(leads["lead_id"])
            quotes = df_quotes[df_quotes["lead_id"].isin(ids)] if not df_quotes.empty else df_quotes
            logs = df_logs[df_logs["lead_id"].isin(ids)] if not df_logs.empty else df_logs
            orders = df_orders[df_orders["lead_id"].isin(ids)] if not df_orders.empty else df_orders
            stem = f"crm_master_{start}_to_{end}"

            if shape == "One row per lead":
                wide = _lead_360(leads, quotes, logs, orders)
                default = [c for c in ["client_id", "client_name", "company_name", "phone_number", "product", "qty",
                                       "city", "source", "final_status", "assigned_salesperson", "claimed_qs_name",
                                       "latest_quotation", "latest_amount", "latest_quote_status", "revisions",
                                       "calls_logged", "last_call_at", "last_call_outcome", "order_id"]
                           if c in wide.columns]
                cols = st.multiselect("Columns", list(wide.columns), default=default, key="mx_cols")
                export = wide[cols] if cols else wide
                st.caption(f"{len(export)} lead(s) · {len(export.columns)} column(s)")
                st.dataframe(export.head(200), width="stretch", hide_index=True)
                e1, e2 = st.columns(2)
                with e1:
                    if st.download_button("Download CSV", export.to_csv(index=False).encode("utf-8"),
                                          file_name=f"{stem}.csv", mime="text/csv", width="stretch"):
                        db_adapter.log_event("EXPORT", "master_360", None, None, {"rows": len(export), "format": "csv"})
                with e2:
                    buf = io.BytesIO()
                    export.to_excel(buf, index=False, sheet_name="Leads 360")
                    if st.download_button("Download Excel", buf.getvalue(), file_name=f"{stem}.xlsx", width="stretch",
                                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
                        db_adapter.log_event("EXPORT", "master_360", None, None, {"rows": len(export), "format": "xlsx"})
            else:
                sheets = {"Leads": leads, "Quotations (all revisions)": quotes, "Follow-up calls": logs, "Orders": orders}
                st.caption(" · ".join(f"{k}: {len(v)} rows" for k, v in sheets.items()))
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as xw:
                    for name, df in sheets.items():
                        (df if not df.empty else pd.DataFrame({"info": ["No rows in this period"]})) \
                            .to_excel(xw, index=False, sheet_name=name[:31])
                if st.download_button("Download workbook", buf.getvalue(), file_name=f"{stem}.xlsx",
                                      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
                    db_adapter.log_event("EXPORT", "master_workbook", None, None,
                                         {k: len(v) for k, v in sheets.items()})

    with tab_activity:
        audit = db_adapter.fetch_all("audit_log")
        df_emp = db_adapter.fetch_all("employees")
        if audit.empty:
            st.info("No activity recorded yet.")
        else:
            names = dict(zip(df_emp["employee_id"], df_emp["full_name"])) if not df_emp.empty else {}
            audit["who"] = audit["actor_id"].map(lambda a: names.get(a, a or "—"))
            since = st.date_input("Since", value=today_ist() - datetime.timedelta(days=7), key="act_since")
            recent = audit[audit["at"].astype(str).str[:10] >= str(since)]
            logins = recent[recent["action"].isin(["LOGIN", "LOGIN_FAILED", "LOGOUT"])]
            summary = (logins.pivot_table(index="who", columns="action", values="audit_id", aggfunc="count", fill_value=0)
                       if not logins.empty else pd.DataFrame())
            last_seen = logins[logins["action"] == "LOGIN"].groupby("who")["at"].max() if not logins.empty else None
            c1, c2 = st.columns([1, 1.4])
            with c1:
                st.markdown("###### Sign-ins")
                if summary.empty:
                    st.info("No sign-ins in this period.")
                else:
                    if last_seen is not None:
                        summary["Last sign-in"] = last_seen
                    st.dataframe(summary, width="stretch")
                    failed = recent[recent["action"] == "LOGIN_FAILED"]
                    if len(failed) >= 5:
                        st.warning(f"{len(failed)} failed sign-in attempts in this period.")
            with c2:
                st.markdown("###### Changes by person")
                changes = recent[~recent["action"].isin(["LOGIN", "LOGIN_FAILED", "LOGOUT"])]
                if changes.empty:
                    st.info("No changes in this period.")
                else:
                    piv = changes.pivot_table(index="who", columns="action", values="audit_id",
                                              aggfunc="count", fill_value=0)
                    st.dataframe(piv, width="stretch")
            if st.download_button("Download activity log (CSV)",
                                  recent.drop(columns=["who"]).to_csv(index=False).encode("utf-8"),
                                  file_name=f"audit_since_{since}.csv", mime="text/csv"):
                db_adapter.log_event("EXPORT", "audit_log", None, None, {"rows": len(recent)})
            st.caption("Full record-level history is on the Audit trail page.")

    with tab_backup:
        st.caption("Downloads the complete database file. On Streamlit Cloud the database resets when the app "
                   "restarts, so download a backup at the end of every working day.")
        try:
            with open(db_adapter.db_path, "rb") as fh:
                data = fh.read()
            if st.download_button("Download backup", data, file_name=f"crm_backup_{today_ist()}.db",
                                  mime="application/octet-stream"):
                db_adapter.log_event("BACKUP_DOWNLOAD")
        except (OSError, AttributeError) as exc:
            st.error(f"Backup not available: {exc}")


def _snooze_section(db_adapter):
    """Admin-only view of how often call reminders are snoozed."""
    st.markdown("---")
    st.markdown("##### Snoozed call reminders")
    sn = db_adapter.fetch_all("call_snoozes")
    if sn.empty:
        st.caption("No reminders have been snoozed yet.")
        return
    today = today_ist()
    d7 = str(today - datetime.timedelta(days=7))
    day = sn["snoozed_at"].astype(str).str[:10]
    week = sn[day > d7]
    repeat = week.groupby(["lead_id", "scheduled_for"]).size()
    render_kpi_cards([
        {"label": "Snoozed today", "value": int((day == str(today)).sum()), "icon": "😴", "tone": "amber"},
        {"label": "Snoozed, last 7 days", "value": len(week), "icon": "🗓️", "tone": "blue"},
        {"label": "Calls snoozed 2+ times", "value": int((repeat >= 2).sum()), "icon": "🔁", "tone": "red",
         "help": "Same scheduled call snoozed more than once in the last 7 days"},
        {"label": "Minutes deferred (7 days)", "value": int(week["minutes"].sum()), "icon": "⏳", "tone": "navy"},
    ])
    who = week.groupby("employee_name").agg(Snoozes=("snooze_id", "count"), Minutes=("minutes", "sum"),
                                            Clients=("lead_id", "nunique")).reset_index() \
        .rename(columns={"employee_name": "Employee"}).sort_values("Snoozes", ascending=False)
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.dataframe(who, width="stretch", hide_index=True)
    with c2:
        recent = sn.sort_values("snoozed_at", ascending=False).head(50)
        st.dataframe(recent[["snoozed_at", "employee_name", "client_id", "client_name", "scheduled_for", "minutes"]]
                     .rename(columns={"snoozed_at": "Snoozed at", "employee_name": "Employee", "client_id": "Client ID",
                                      "client_name": "Client", "scheduled_for": "Call was due", "minutes": "Minutes"}),
                     width="stretch", hide_index=True)
