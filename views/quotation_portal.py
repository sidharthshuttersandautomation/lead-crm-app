"""
Quotation Specialist Desk.
"""
import datetime
import pandas as pd
import streamlit as st
from config.settings import TEAM_MEMBERS, IST

def render_quotation_portal(db_adapter, current_user):
    st.markdown("<h2 style='color:#0E2C68; font-weight:800;'>📝 Quotation Specialist Desk Portal</h2>", unsafe_allow_html=True)
    qs_id = current_user.get("employee_id", "EMP-102")
    qs_name = current_user.get("name") or "QS Specialist"
    is_admin = current_user.get("role", "").upper() == "ADMIN"

    df_leads = db_adapter.fetch_all("leads_master")
    df_quotes = db_adapter.fetch_all("quotations_master")

    unassigned = df_leads[df_leads["claimed_qs_id"] == "Unassigned"] if not df_leads.empty else pd.DataFrame()
    if not unassigned.empty:
        st.warning(f"🔔 **Inbound Ticket Alert:** {len(unassigned)} new lead(s) require quotation generation!")

    t1, t2, t3 = st.tabs([
        "📈 Performance & Progress Control",
        "📄 Quotation Generator & Convert",
        "📝 Detailed Quotation Form Entry"
    ])

    with t1:
        st.markdown("##### 📈 Quotation Output Analytics")
        total_quotes = len(df_quotes) if not df_quotes.empty else 0
        approved_quotes = len(df_quotes[df_quotes["quotation_status"] == "Approved"]) if not df_quotes.empty else 0
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total System Quotations", total_quotes)
        with c2:
            st.metric("Approved Quotations", approved_quotes)
        with c3:
            if not is_admin:
                my_cnt = len(df_quotes[df_quotes["quotation_shared_by"] == qs_name]) if not df_quotes.empty else 0
                st.metric("Quotations Prepared by You", my_cnt)
            else:
                st.metric("Quotation Approval Rate", f"{round((approved_quotes/total_quotes*100), 1) if total_quotes > 0 else 0}%")

        st.markdown("---")
        if st.button("📋 Click to Display / Hide Master Quotation Sheet"):
            st.dataframe(df_quotes, use_container_width=True, hide_index=True)

    with t2:
        st.markdown("##### 🔔 Inbound Unassigned Quotation Queue")
        if not unassigned.empty:
            for idx, row in unassigned.iterrows():
                cid = row.get("client_id")
                cname = row.get("client_name")
                prod = row.get("product")
                lead_id = row.get("lead_id")

                st.markdown(f"""
                <div class='saas-card'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <span style='color:#184B9C; font-weight:800; font-size:16px;'>👤 {cname} ({cid})</span>
                        <span style='background:rgba(24, 75, 156, 0.1); color:#184B9C; padding:4px 12px; border-radius:20px; font-weight:700;'>Unassigned Ticket</span>
                    </div>
                    <div style='margin-top:6px; color:#475569; font-size:13.5px;'>
                        📦 <b>Product:</b> {prod} (Qty: {row.get('qty')})
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"🔒 Claim & Assign Ticket {cid} to Me", key=f"claim_{lead_id}"):
                    db_adapter.update_row("leads_master", "lead_id", str(lead_id), {"claimed_qs_id": qs_id, "quotation_status": "Under Process"})
                    st.toast(f"✅ Ticket {cid} claimed by {qs_name}!", icon="🎉")
                    st.rerun()
        else:
            st.info("🎉 No pending unassigned leads in queue.")

    with t3:
        st.markdown("##### 📝 Create / Update Detailed Quotation Record")
        if df_leads.empty:
            st.info("No lead records available.")
        else:
            client_options = list(df_leads["client_id"].unique())
            selected_cid = st.selectbox("Select Client ID to Auto-Fetch Lead Details:", client_options)

            lead_row = df_leads[df_leads["client_id"] == selected_cid].iloc[0]
            now_dt = datetime.datetime.now(IST)

            with st.form("detailed_quotation_form"):
                st.markdown("###### 🔄 Auto-Fetched Details from Lead Sheet")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.text_input("Client ID", value=selected_cid, disabled=True)
                    st.text_input("Date Stamp", value=str(lead_row.get("ingestion_date", "")), disabled=True)
                    st.text_input("Client Name", value=str(lead_row.get("client_name", "")), disabled=True)
                    st.text_input("Company Name", value=str(lead_row.get("company_name", "")), disabled=True)
                with c2:
                    st.text_input("Customer Contact Number", value=str(lead_row.get("phone_number", "")), disabled=True)
                    st.text_input("Product", value=str(lead_row.get("product", "")), disabled=True)
                    st.number_input("Quantity", value=int(lead_row.get("qty", 1)), disabled=True)
                    st.text_input("City", value=str(lead_row.get("city", "")), disabled=True)
                with c3:
                    st.text_input("Source", value=str(lead_row.get("source", "")), disabled=True)
                    st.text_input("Assigned Salesperson", value=str(lead_row.get("assigned_salesperson", "")), disabled=True)

                st.markdown("---")
                st.markdown("###### ✍️ Manual & Operational Quotation Inputs")
                m1, m2, m3 = st.columns(3)
                with m1:
                    q_num = st.text_input("Quotation Number *", value=f"SSAPL/2026-27/{len(df_quotes)+841}")
                    q_amount = st.number_input("Qut. Amount (INR) *", min_value=0.0, value=50000.0)
                    revised = st.selectbox("Revised", ["No", "Yes - R1", "Yes - R2"])
                    q_status = st.selectbox("Quotation Status", ["Approved", "Under Review", "Rejected"])
                with m2:
                    follow_req = st.selectbox("Follow Up Required", ["Yes", "No"])
                    app_by = st.selectbox("Qut. Status Approved By", ["Jitendra Sir", "Jeevan Sharma", "Sidharth Jain", "Deepak Sethiya"])
                    follow_status = st.selectbox("Follow Up Status", ["Under Discussion", "Won", "Lost", "CallBack"])
                    drive_link = st.text_input("Link (Folder Link)", value="https://drive.google.com")
                with m3:
                    q_shared_by = st.selectbox("Quotation Shared By", TEAM_MEMBERS, index=1 if qs_name == "Pooja" else 0)
                    approved_date = st.date_input("Approved Date", value=now_dt.date())
                    comp_name_1 = st.text_input("Company Name-1", value=str(lead_row.get("company_name", "")))
                    approved_month = st.text_input("Approved Month", value=now_dt.strftime("%B"))

                submit_q_btn = st.form_submit_button("💾 Save & Dispatch Quotation")

                if submit_q_btn:
                    q_record = {
                        "quotation_id": f"QUO-{len(df_quotes)+1:04d}",
                        "lead_id": int(lead_row.get("lead_id")),
                        "client_id": selected_cid,
                        "quotation_number": q_num,
                        "revised": revised,
                        "qut_amount": q_amount,
                        "quotation_status": q_status,
                        "follow_up_required": follow_req,
                        "claimed_qs_id": qs_id,
                        "approved_by_id": "EMP-106",
                        "shared_by_id": qs_id,
                        "folder_link": drive_link,
                        "company_name_1": comp_name_1,
                        "approved_date": str(approved_date),
                        "approved_month": approved_month
                    }
                    db_adapter.insert_row("quotations_master", q_record)
                    db_adapter.update_row("leads_master", "lead_id", str(lead_row.get("lead_id")), {"quotation_status": "Sent", "claimed_qs_id": qs_id})

                    st.toast(f"🎉 Quotation {q_num} saved & lead marked as Sent!", icon="✅")
                    st.rerun()