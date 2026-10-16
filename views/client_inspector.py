"""views/client_inspector.py - Search every client and export filtered lists."""
import datetime
import io

import pandas as pd
import streamlit as st

from config.settings import EXPORT_ROLES, LEAD_ADDER_ROLES
from components.kpi_cards import page_title, render_kpi_cards
from utils.time_utils import today_ist

FRONT_COLS = ["client_id", "client_name", "company_name", "phone_number", "product", "qty", "city",
              "source", "final_status", "quotation_status", "priority", "leads_handled_by",
              "assigned_salesperson", "claimed_qs_name", "ingested_at"]
HIDDEN_COLS = {"product_id", "handled_by_lge_id", "assigned_sam_id", "claimed_qs_id", "followup_owner_id"}


def render_client_inspector(db_adapter, current_user):
    if current_user["role"] == "SAM":
        from views.sam_clients import render_sam_clients
        render_sam_clients(db_adapter, current_user)
        return
    page_title("Client inspector", "Search every client, filter, and export.")
    df = db_adapter.fetch_all("leads_master")
    df_emp = db_adapter.fetch_all("employees")
    if df.empty:
        st.info("No clients yet.")
        return

    search = st.text_input("Search", placeholder="Client ID, name, company or phone").strip().lower()

    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        sources = st.multiselect("Source", sorted(df["source"].dropna().unique()), placeholder="All sources")
    with f2:
        stage = st.selectbox("Stage", ["All"] + sorted(df["final_status"].dropna().unique()))
    with f3:
        q_status = st.selectbox("Quotation", ["All"] + sorted(df["quotation_status"].dropna().unique()))
    with f4:
        adders = df_emp[df_emp["role"].isin(LEAD_ADDER_ROLES)] if not df_emp.empty else df_emp
        adder_names = sorted(set(adders["full_name"]) | set(df["leads_handled_by"].dropna()))
        role_of = dict(zip(df_emp["full_name"], df_emp["role"])) if not df_emp.empty else {}
        lge_label = st.selectbox("Added by", ["All"] + [f"{n} ({role_of.get(n, '—')})" for n in adder_names])
        lge = "All" if lge_label == "All" else lge_label.rsplit(" (", 1)[0]
    with f5:
        sam = st.selectbox("Salesperson", ["All"] + sorted(df["assigned_salesperson"].dropna().unique()))

    today = today_ist()
    d1, d2 = st.columns(2)
    with d1:
        start = st.date_input("From", value=today.replace(day=1))
    with d2:
        end = st.date_input("To", value=today)

    out = df.copy()
    if search:
        hay = (out["client_id"].astype(str) + " " + out["client_name"].astype(str) + " "
               + out["company_name"].fillna("").astype(str) + " " + out["phone_number"].astype(str)).str.lower()
        out = out[hay.str.contains(search, regex=False)]
    if sources:
        out = out[out["source"].isin(sources)]
    for col, val in [("final_status", stage), ("quotation_status", q_status),
                     ("leads_handled_by", lge), ("assigned_salesperson", sam)]:
        if val != "All":
            out = out[out[col] == val]
    if not search:      # a search looks through all dates, so an older client is still found
        dates = pd.to_datetime(out["ingestion_date"], errors="coerce").dt.date
        out = out[(dates >= start) & (dates <= end)]

    cols = [c for c in FRONT_COLS if c in out.columns] + \
           [c for c in out.columns if c not in FRONT_COLS and c not in HIDDEN_COLS]
    out = out[cols]

    render_kpi_cards([
        {"label": "Matching clients", "value": len(out), "icon": "🔎", "tone": "blue"},
        {"label": "Open", "value": int((~out["final_status"].isin(["Done", "Cancled"])).sum()) if len(out) else 0,
         "icon": "🟡", "tone": "amber"},
        {"label": "Done", "value": int((out["final_status"] == "Done").sum()) if len(out) else 0, "icon": "🏆", "tone": "green"},
        {"label": "Cancled", "value": int((out["final_status"] == "Cancled").sum()) if len(out) else 0, "icon": "✖️", "tone": "red"},
    ])
    if search and 0 < len(out) <= 8:
        from components.client_card import render_client_card
        st.markdown("##### Client details")
        quotes, logs, orders = (db_adapter.fetch_all("quotations_master"), db_adapter.fetch_all("followup_logs"),
                                db_adapter.fetch_all("orders"))
        full = df.set_index("client_id")
        for cid in out["client_id"]:
            render_client_card(full.loc[cid].to_dict() | {"client_id": cid}, quotes, logs, orders, key=f"ci_{cid}")
        st.markdown("##### As a table")
    elif search and len(out) > 8:
        st.caption("Narrow the search to 8 or fewer clients to see them as detailed cards.")
    elif not search:
        st.caption("Tip: search a client ID, name, company or phone to see a detailed client card.")
    st.dataframe(out, width="stretch", hide_index=True)

    if current_user["role"] not in EXPORT_ROLES:
        st.caption("Downloads are limited to administrators.")
        return

    st.markdown("##### Export")
    chosen = st.multiselect("Columns", list(out.columns), default=[c for c in FRONT_COLS if c in out.columns][:10])
    export = out[chosen] if chosen else out
    name = f"clients_{start}_to_{end}"
    e1, e2 = st.columns(2)
    with e1:
        if st.download_button("Download CSV", export.to_csv(index=False).encode("utf-8"),
                              file_name=f"{name}.csv", mime="text/csv", width="stretch"):
            db_adapter.log_event("EXPORT", "leads_master", None, None, {"rows": len(export), "format": "csv"})
    with e2:
        buf = io.BytesIO()
        export.to_excel(buf, index=False, sheet_name="Clients")
        if st.download_button("Download Excel", buf.getvalue(), file_name=f"{name}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              width="stretch"):
            db_adapter.log_event("EXPORT", "leads_master", None, None, {"rows": len(export), "format": "xlsx"})
