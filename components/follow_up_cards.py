"""
Card Component with 3-Day Default Reminders & Remark Histories.
"""
import streamlit as st
from datetime import datetime, timedelta
from config.settings import IST

def render_follow_up_card(db_adapter, client_id: str, client_name: str, address: str, city: str, product: str, last_price: float, followups_count: int, remarks_history: list, current_user_name: str, key: str):
    with st.container():
        st.markdown(f"""
            <div class='saas-card'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                    <span style='color: #184B9C; font-size: 16px; font-weight: 800;'>👤 {client_name} <small style='color: #64748B;'>({client_id})</small></span>
                    <span style='background: rgba(0, 168, 89, 0.12); color: #00A859; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 12px;'>
                        {followups_count} Follow-ups Taken
                    </span>
                </div>
                <div style='color: #475569; font-size: 13.5px; line-height: 1.6;'>
                    📍 <b>Address & City:</b> {address}, {city} &nbsp;|&nbsp; 📦 <b>Product:</b> {product}<br>
                    💰 <b>Last Price Quoted:</b> ₹{last_price:,.2f}
                </div>
            </div>
        """, unsafe_allow_html=True)

        with st.expander(f"🔍 View History & Log Follow-up for {client_name}"):
            if remarks_history:
                st.markdown("**📜 Chronological Follow-up Remarks History:**")
                for idx, r in enumerate(remarks_history, start=1):
                    st.markdown(f"- **Remark #{idx}:** {r}")
            else:
                st.info("No previous follow-up remarks recorded.")

            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                new_status = st.selectbox("Update Status", ["CallBack Scheduled", "In Discussion", "Under Finalization", "Done / Won", "Cold / Not Interested"], key=f"status_{key}")
                callback_schedule = st.selectbox(
                    "Next Callback Schedule",
                    ["Auto-Reminder (3 Days Later)", "Today at 5:00 PM", "In 5 Days", "Custom Date / Time"],
                    key=f"call_{key}"
                )
                scheduled_time_str = str(datetime.now(IST) + timedelta(days=3))
                if callback_schedule == "Custom Date / Time":
                    c_date = st.date_input("Select Reminder Date", key=f"cust_d_{key}")
                    c_time = st.time_input("Select Reminder Time", key=f"cust_t_{key}")
                    scheduled_time_str = f"{c_date} {c_time}"

            with c2:
                new_remark = st.text_area("Log Follow-up Remark", placeholder="Enter specific client response details...", key=f"rem_{key}")
                
                if st.button("💾 Save Follow-up Entry", key=f"btn_{key}"):
                    if new_remark.strip():
                        today_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M")
                        formatted_entry = f"[{today_str} by {current_user_name}]: {new_remark.strip()}"
                        
                        updated_history = remarks_history + [formatted_entry] if remarks_history else [formatted_entry]
                        history_str = " || ".join(updated_history)
                        
                        db_adapter.update_row(
                            "followup_tracker",
                            "client_id",
                            client_id,
                            {
                                "total_followups": followups_count + 1,
                                "notes": history_str,
                                "followup_status": new_status,
                                "last_followed_by": current_user_name,
                                "scheduled_call_time": scheduled_time_str
                            }
                        )
                        st.toast(f"✅ Follow-up logged for {client_name}! Total: {followups_count + 1}", icon="🎉")
                        st.rerun()
                    else:
                        st.warning("Please enter a remark before saving.")