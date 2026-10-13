"""
Quotation Specialist Desk.
"""
import datetime
import pandas as pd
import streamlit as st
from utils.sla_calculator import evaluate_sla
from config.settings import IST

def render_quotation_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📝 Quotation Specialist Workstation</h2>", unsafe_allow_html=True)
    qs_name = current_user.get("name") or "QS Specialist"

    df_leads = db_adapter.fetch_all("leads_data")
    df_quotes = db_adapter.fetch_all("quotation_sheet")

    # Inbound Unassigned Claims Alert Notification
    unassigned = df_leads[df_leads["claimed_by_qs"] == "Unassigned"] if not df_leads.empty and "claimed_by_qs" in df_leads.columns else pd.DataFrame()
    if not unassigned.empty:
        st.warning(f"🔔 **Notification:** {len(unassigned)} new unassigned lead(s) available to claim and generate quotation!")

    t1, t2 = st.tabs([
        "📈 Performance & Progress Control",
        "📄 Quotation Generator & Convert"
    ])

    with t1:
        st.markdown("##### 📈 QS Turnaround & Performance")
        my_quotes = df_quotes[df_quotes["assigned_qs_id"] == qs_name] if not df_quotes.empty and "assigned_qs_id" in df_quotes.columns else pd.DataFrame()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Quotations Prepared by You", len(my_quotes))
        with c2:
            st.metric("Avg. Turnaround Time", "18 Mins")
        with c3:
            st.metric("Same-Day SLA Compliance", "96.8%")

    with t2:
        st.markdown("##### 🔔 Claim Unassigned Lead Ticket")
        if not unassigned.empty:
            st.dataframe(unassigned, use_container_width=True, hide_index=True)
            unclaimed_ids = list(unassigned["client_id"].dropna().unique())
            selected_cid = st.selectbox("Select Lead to Claim & Lock to Profile:", unclaimed_ids)
            
            if selected_cid and st.button("🔒 Claim & Lock Quotation Ticket"):
                db_adapter.update_row("leads_data", "client_id", selected_cid, {"claimed_by_qs": qs_name, "quotation_status": "Under Process"})
                st.toast(f"✅ Lead {selected_cid} locked to {qs_name}!", icon="🎉")
                st.rerun()
        else:
            st.info("🎉 No pending unassigned leads requiring quotation.")

        st.markdown("---")
        st.markdown("##### 📄 Master Quotation Registry")
        st.dataframe(df_quotes, use_container_width=True, hide_index=True)