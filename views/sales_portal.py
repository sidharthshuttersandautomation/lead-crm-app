"""views/sales_portal.py - Sales pipeline. Salespeople see only their own clients.
Click any bar to open the clients behind it."""
import pandas as pd
import plotly.express as px
import streamlit as st

from components.kpi_cards import page_title, render_kpi_cards
from components.time_picker import fmt_12h
from config.settings import CLOSED_STAGES, LEAD_STAGES, REPORTING_WINDOWS, STAGE_LOST, STAGE_WON
from utils.metrics import filter_by_window, inr, latest_quotes, open_leads
from utils.queues import my_clients
from utils.time_utils import window_start

STAGE_COLORS = {"Done": "#00A859", "Cancled": "#BE123C", "Pending": "#94A3B8", "In Discussion": "#184B9C",
                "CallBack": "#0284C7", "Not Responed": "#B45309", "Under Finalization": "#0E7490"}
GROUP_COLORS = {"Open": "#184B9C", "Done": "#00A859", "Cancled": "#BE123C"}


def _clicked(event, field="y"):
    try:
        pts = event.selection.points
        return pts[0].get(field) if pts else None
    except Exception:
        return None


def _layout(fig, h):
    fig.update_layout(height=h, margin=dict(t=10, b=10, l=10, r=30), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", legend_title_text="", legend=dict(orientation="h", y=1.08),
                      xaxis=dict(showgrid=True, gridcolor="#E2E8F0", zeroline=False), yaxis_title="", xaxis_title="",
                      hoverlabel=dict(bgcolor="#0E2C68", font_color="#FFFFFF"), clickmode="event+select")
    return fig


def _details(df, title):
    st.markdown(f"##### {title} — {len(df)} client(s)")
    show = pd.DataFrame({
        "Client ID": df["client_id"], "Client": df["client_name"], "Company": df["company_name"],
        "Phone": df["phone_number"], "Product": df["product"] + " × " + df["qty"].astype(str),
        "Stage": df["final_status"], "Quotation": df["quotation_ref"].fillna("—"),
        "Final price": df["final_price"].map(lambda v: inr(v) if pd.notna(v) else "—"),
        "Next call": df["next_followup_at"].map(fmt_12h), "Salesperson": df["assigned_salesperson"].fillna("—"),
    })
    st.dataframe(show, width="stretch", hide_index=True)


def render_sales_portal(db_adapter, current_user):
    page_title("Sales pipeline", "Click any bar to open the clients behind it.")
    labels = list(REPORTING_WINDOWS.keys())
    window = st.segmented_control("Period (by lead received date)", labels, default="This month", key="sp_window") or "This month"
    start = window_start(REPORTING_WINDOWS[window])
    df = filter_by_window(db_adapter.fetch_all("leads_master"), "ingested_at", start)
    if current_user["role"] == "SAM":
        df = my_clients(df, current_user)
        st.caption("Showing only your own clients.")
    if df.empty:
        st.info("No leads in this period. Try a longer period.")
        return

    lq = latest_quotes(db_adapter.fetch_all("quotations_master"))
    df = df.copy()
    df["quotation_ref"] = df["lead_id"].map(dict(zip(lq["lead_id"], lq["quotation_ref"])) if not lq.empty else {})
    df["final_price"] = df["lead_id"].map(dict(zip(lq["lead_id"], lq["qut_amount"])) if not lq.empty else {})
    df["quote_status"] = df["lead_id"].map(dict(zip(lq["lead_id"], lq["quotation_status"])) if not lq.empty else {})
    df["group"] = df["final_status"].map(lambda s: s if s in CLOSED_STAGES else "Open")

    won, lost, active = df[df["final_status"] == STAGE_WON], df[df["final_status"] == STAGE_LOST], open_leads(df)
    closed = len(won) + len(lost)
    pipeline = df[(df["group"] == "Open") & (df["quote_status"] == "Approved")]["final_price"].sum()
    render_kpi_cards([
        {"label": "Leads", "value": len(df), "icon": "📥", "tone": "blue", "sub": window.lower()},
        {"label": "Quoted", "value": int(df["quotation_ref"].notna().sum()), "icon": "📄", "tone": "teal",
         "sub": f"{df['quotation_ref'].notna().mean() * 100:.0f}% of leads"},
        {"label": "Done / Cancled", "value": f"{len(won)} / {len(lost)}", "icon": "🏁", "tone": "navy"},
        {"label": "Win rate", "value": f"{len(won) / closed * 100:.0f}%" if closed else "—", "icon": "🎯",
         "tone": "green", "sub": "of closed deals"},
        {"label": "Open pipeline", "value": inr(pipeline), "icon": "💼", "tone": "amber",
         "help": "Latest approved final price of every open lead"},
        {"label": "Done value", "value": inr(won["final_price"].sum()), "icon": "🏆", "tone": "green"},
    ], columns=3)

    # ---------------- demand by product (stacked open / done / cancled, value in label)
    st.markdown("##### Demand by product")
    prod = df.groupby(["product", "group"]).size().reset_index(name="Leads")
    totals = df.groupby("product").agg(Leads=("lead_id", "count"), Value=("final_price", "sum")).reset_index()
    order = totals.sort_values("Leads")["product"].tolist()[-12:]
    prod = prod[prod["product"].isin(order)]
    fig = px.bar(prod, x="Leads", y="product", color="group", orientation="h", color_discrete_map=GROUP_COLORS,
                 category_orders={"product": order[::-1], "group": ["Open", "Done", "Cancled"]}, custom_data=["product"])
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{x} lead(s)<extra></extra>",
                      marker_line_width=0)
    t = totals[totals["product"].isin(order)]
    fig.add_scatter(x=t["Leads"], y=t["product"], mode="text", showlegend=False, hoverinfo="skip",
                    text=[f"  {n} · {inr(v)}" if v else f"  {n}" for n, v in zip(t["Leads"], t["Value"])],
                    textposition="middle right", textfont=dict(color="#0E2C68", size=12))
    fig.update_layout(barmode="stack", bargap=0.35)
    fig.update_xaxes(range=[0, totals["Leads"].max() * 1.45], dtick=max(1, int(totals["Leads"].max() // 6)))
    ev = st.plotly_chart(_layout(fig, 70 + 34 * len(order)), width="stretch", on_select="rerun",
                         selection_mode="points", key="sp_prod")
    picked_product = _clicked(ev, "y")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Leads by stage")
        stages = df["final_status"].value_counts().reindex(LEAD_STAGES).dropna().reset_index()
        stages.columns = ["Stage", "Leads"]
        fig2 = px.bar(stages, x="Leads", y="Stage", orientation="h", color="Stage", color_discrete_map=STAGE_COLORS,
                      text="Leads", category_orders={"Stage": LEAD_STAGES})
        fig2.update_traces(textposition="outside", hovertemplate="<b>%{y}</b>: %{x} lead(s)<extra></extra>",
                           cliponaxis=False)
        fig2.update_layout(showlegend=False, bargap=0.3, barmode="overlay")
        fig2.update_xaxes(range=[0, stages["Leads"].max() * 1.25])
        ev2 = st.plotly_chart(_layout(fig2, 320), width="stretch", on_select="rerun", selection_mode="points",
                              key="sp_stage")
        picked_stage = _clicked(ev2, "y")
    with c2:
        st.markdown("##### Why deals were cancelled")
        reasons = lost["lost_reason"].dropna()
        picked_reason = None
        if reasons.empty:
            st.info("No cancelled deals with a recorded reason in this period.")
        else:
            rc = reasons.value_counts().reset_index()
            rc.columns = ["Reason", "Deals"]
            fig3 = px.bar(rc.sort_values("Deals"), x="Deals", y="Reason", orientation="h", text="Deals",
                          color_discrete_sequence=["#BE123C"])
            fig3.update_traces(textposition="outside", cliponaxis=False,
                               hovertemplate="<b>%{y}</b>: %{x} deal(s)<extra></extra>")
            ev3 = st.plotly_chart(_layout(fig3, 320), width="stretch", on_select="rerun", selection_mode="points",
                                  key="sp_reason")
            picked_reason = _clicked(ev3, "y")

    render_order_progress(db_adapter, set(df["lead_id"]) if current_user["role"] != "SAM"
                          else set(my_clients(db_adapter.fetch_all("leads_master"), current_user)["lead_id"]))

    # ---------------- details for whatever was clicked
    st.markdown("---")
    if picked_product:
        _details(df[df["product"] == picked_product], f"📦 {picked_product}")
    if picked_stage:
        _details(df[df["final_status"] == picked_stage], f"🏷️ Stage: {picked_stage}")
    if picked_reason:
        _details(lost[lost["lost_reason"] == picked_reason], f"✖️ Cancelled for: {picked_reason}")
    if not (picked_product or picked_stage or picked_reason):
        pick = st.selectbox("Or open a list", ["—", "All open leads", "All Done deals", "All Cancled deals"],
                            key="sp_list")
        if pick == "All open leads":
            _details(df[df["group"] == "Open"], "Open leads")
        elif pick == "All Done deals":
            _details(won, "Done deals")
        elif pick == "All Cancled deals":
            _details(lost, "Cancled deals")


def render_order_progress(db, lead_ids, title="Orders & payment progress"):
    """Payment tracker for the orders of these clients (used by salespeople and admins)."""
    from components.cards import flat
    from utils.payment_plan import current_milestone, stage_label, tracker_html
    O = db.fetch_all("orders")
    O = O[O["lead_id"].isin(lead_ids)] if not O.empty else O
    st.markdown(f"##### 🧾 {title}")
    if O.empty:
        st.caption("No orders yet for these clients.")
        return
    parts = []
    for _, o in O.sort_values("created_at", ascending=False).iterrows():
        m = current_milestone(o)
        nxt = f"Next: {m['name']} — {inr(m['balance'])}" if m else "Fully paid 🎉"
        parts.append(flat(f"""<div class='saas-card' style='padding:12px 18px;'>
          <div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px;'>
            <div><b style='color:#184B9C;'>{o['client_id']}</b> · <b style='color:#0E2C68;'>{o['client_name']}</b>
              <span style='color:#64748B;'> · {o['order_id']}</span></div>
            <div style='font-weight:800; color:#0E2C68;'>{inr(o['received'])} <span style='color:#64748B; font-weight:600;'>of {inr(o['order_value'])}</span></div>
          </div>
          <div style='font-size:13px; color:#475569; margin:4px 0 8px;'>{stage_label(o)} · {nxt}
            {" · delivery " + str(o['expected_delivery_date']) if o.get('expected_delivery_date') and not o.get('dispatched_at') else ""}</div>
          {tracker_html(o, compact=True)}</div>"""))
    st.markdown("".join(parts), unsafe_allow_html=True)
