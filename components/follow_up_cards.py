"""
components/follow_up_cards.py - Interactive Follow-up Card Component.
"""
import datetime
import streamlit as st

def render_follow_up_card(db_adapter, client_id, client_name, address, city, product, last_price, followups_count, remarks_history, current_user_name, key):
    st.markdown(f"""
    <div class='saas-card'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <span style='color: #184B9C; font-weight: 800; font-size: 17px;'>👤 {client_name}</span>
                <span style='color: #64748B; font-weight: 600; font-size: 13.5px; margin-left: 10px;'>({client_id})</span>
            </div>
            <span style='background: #E0F2FE; color: #0369A1; padding: 4px 14px; border-radius: 20px; font-weight: 800; font-size: 12.5px;'>
                Follow-up #{followups_count}
            </span>
        </div>
        <div style='margin-top: 8px; color: #334155; font-size: 14px;'>
            📍 <b>Location:</b> {city}, {address} &nbsp;|&nbsp; 📦 <b>Product:</b> {product} &nbsp;|&nbsp; 💰 <b>Last Price:</b> ₹{last_price:,.0f}
        </div>
        <div style='margin-top: 8px; background: #F1F5F9; padding: 10px; border-radius: 8px; font-size: 13px; color: #475569;'>
            <b>📝 Recent Note:</b> {remarks_history[-1] if remarks_history else "Initial Contact"}
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander(f"📞 Log Follow-up & Update Call Details for {client_name}", expanded=False):
        with st.form(key=f"form_{key}"):
            f_status = st.selectbox("Call Outcome / Status *", ["Choose...", "Under Discussion", "Callback Scheduled", "Won / Order Confirmed", "Lost / Cancelled"], index=0, key=f"stat_{key}")
            f_notes = st.text_area("Client Conversation Notes *", placeholder="Enter call details, client response...", key=f"notes_{key}")
            
            c1, c2 = st.columns(2)
            with c1:
                next_date = st.date_input("Next Follow-up Date", value=datetime.date.today() + datetime.timedelta(days=3), key=f"date_{key}")
            with c2:
                next_time = st.time_input("Next Follow-up Time", value=datetime.time(12, 0), key=f"time_{key}")

            submit_fol = st.form_submit_button("✅ Follow-up Done")

            if submit_fol:
                if f_status == "Choose...":
                    st.error("Please select a valid Call Outcome / Status.")
                else:
                    df_leads = db_adapter.fetch_all("leads_master")
                    matched_lead = df_leads[df_leads["client_id"] == client_id]
                    
                    if not matched_lead.empty:
                        lead_id = int(matched_lead.iloc[0]["lead_id"])
                        sched_ts = f"{next_date} {next_time}"

                        log_record = {
                            "lead_id": lead_id,
                            "employee_id": current_user_name,
                            "followup_sequence_no": followups_count + 1,
                            "followup_status": f_status,
                            "scheduled_call_time": sched_ts,
                            "notes": f_notes if f_notes else "Follow-up logged."
                        }
                        db_adapter.insert_row("followup_logs", log_record)

                        if f_status in ["Won / Order Confirmed", "Lost / Cancelled"]:
                            new_stat = "Done" if f_status == "Won / Order Confirmed" else "Cancled"
                            db_adapter.update_row("leads_master", "lead_id", str(lead_id), {"final_status": new_stat})

                        st.toast(f"✅ Follow-up logged for {client_name}! Reminder set for {sched_ts}.", icon="🎉")
                        st.rerun()