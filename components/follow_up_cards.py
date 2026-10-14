"""
components/follow_up_cards.py - Interactive Follow-up Workday Engine with Date & Time Slot Filtering.
"""
import datetime
import pandas as pd
import streamlit as st

TIME_SLOTS = [
    "🌅 Morning (09:00 AM - 11:00 AM)",
    "☀️ Midday (11:00 AM - 01:00 PM)",
    "🌤️ Afternoon (01:00 PM - 04:00 PM)",
    "🌆 Evening (04:00 PM - 06:00 PM)",
    "🌙 Late Evening (After 06:00 PM)",
]

def get_time_slot_label(time_obj: datetime.time) -> str:
    """Categorizes a time object into a designated operational time slot bucket."""
    hour = time_obj.hour
    if 9 <= hour < 11:
        return "🌅 Morning (09:00 AM - 11:00 AM)"
    elif 11 <= hour < 13:
        return "☀️ Midday (11:00 AM - 01:00 PM)"
    elif 13 <= hour < 16:
        return "🌤️ Afternoon (01:00 PM - 04:00 PM)"
    elif 16 <= hour < 18:
        return "🌆 Evening (04:00 PM - 06:00 PM)"
    elif hour >= 18:
        return "🌙 Late Evening (After 06:00 PM)"
    else:
        return "🌅 Morning (09:00 AM - 11:00 AM)"


def render_time_slot_workday_queue(db_adapter, active_queue, df_logs, current_user_name, ist_now):
    """Renders follow-up cards with search filtering, today's schedule logic, and time slot badges."""
    
    st.markdown("##### 🔍 Search & Date Filter Workstation")
    
    # 1. Multi-Attribute Search Bar (Client ID, Name, Company Name)
    search_query = st.text_input(
        "🔍 Search Follow-up Queue:",
        placeholder="Type Client ID (e.g. BID-Oct-26-005), Client Name, or Company Name...",
        key="fol_queue_search_bar"
    ).strip().lower()

    # 2. Date Filtering Tabs
    date_filter = st.radio(
        "Select Date Window:",
        ["📅 Today's Scheduled Calls", "⚠️ Overdue Calls", "📆 Upcoming Calls", "📋 View All Active Queue"],
        horizontal=True,
        key="fol_queue_date_filter"
    )

    # 3. Time Slot Window Filter
    current_slot = get_time_slot_label(ist_now.time())
    st.info(f"🕒 **Current System Date & Time:** `{ist_now.strftime('%d %B %Y | %I:%M %p')}` | **Active Slot:** `{current_slot}`")

    slot_filter = st.radio(
        "Filter by Time Slot Window:",
        ["🔥 All Slots Today", "🌅 Morning (9-11 AM)", "☀️ Midday (11 AM-1 PM)", "🌤️ Afternoon (1-4 PM)", "🌆 Evening (4-6 PM)", "🌙 Late Evening (> 6 PM)"],
        horizontal=True,
        key="fol_queue_slot_filter"
    )

    st.markdown("---")

    today_date = ist_now.date()
    rendered_count = 0

    for idx, row in active_queue.iterrows():
        lead_id = row.get("lead_id")
        cid = str(row.get("client_id", "N/A"))
        cname = str(row.get("client_name", "Client"))
        comp = str(row.get("company_name", "N/A"))
        addr = str(row.get("address", "N/A"))
        cty = str(row.get("city", "N/A"))
        prod = str(row.get("product", "Automation"))

        # Search Query Filtering Logic
        if search_query:
            match_cid = search_query in cid.lower()
            match_cname = search_query in cname.lower()
            match_comp = search_query in comp.lower()
            if not (match_cid or match_cname or match_comp):
                continue

        # Fetch past interaction logs
        past_logs = df_logs[df_logs["lead_id"] == lead_id] if not df_logs.empty else pd.DataFrame()
        log_count = len(past_logs) if not past_logs.empty else 1
        history_remarks = list(past_logs["notes"].astype(str)) if not past_logs.empty else ["Initial contact logged"]

        # Parse scheduled call time & date
        sched_time_str = str(past_logs.iloc[-1].get("scheduled_call_time", "")) if not past_logs.empty else ""
        card_date = today_date
        card_time = datetime.time(17, 0)
        display_call_badge = "Today @ 05:00 PM"
        card_slot = "🌆 Evening (04:00 PM - 06:00 PM)"

        if sched_time_str and " " in sched_time_str:
            try:
                parsed_dt = datetime.datetime.strptime(sched_time_str, "%Y-%m-%d %H:%M:%S")
                card_date = parsed_dt.date()
                card_time = parsed_dt.time()
                card_slot = get_time_slot_label(card_time)
                
                if card_date == today_date:
                    display_call_badge = f"Today @ {parsed_dt.strftime('%I:%M %p')}"
                else:
                    display_call_badge = f"{card_date.strftime('%d %b')} @ {parsed_dt.strftime('%I:%M %p')}"
            except Exception:
                pass

        # Apply Date Filter Logic
        if date_filter == "📅 Today's Scheduled Calls" and card_date != today_date:
            continue
        elif date_filter == "⚠️ Overdue Calls" and card_date >= today_date:
            continue
        elif date_filter == "📆 Upcoming Calls" and card_date <= today_date:
            continue

        # Apply Time Slot Filter Logic
        if slot_filter == "🌅 Morning (9-11 AM)" and card_slot != "🌅 Morning (09:00 AM - 11:00 AM)":
            continue
        elif slot_filter == "☀️ Midday (11 AM-1 PM)" and card_slot != "☀️ Midday (11:00 AM - 01:00 PM)":
            continue
        elif slot_filter == "🌤️ Afternoon (1-4 PM)" and card_slot != "🌤️ Afternoon (01:00 PM - 04:00 PM)":
            continue
        elif slot_filter == "🌆 Evening (4-6 PM)" and card_slot != "🌆 Evening (04:00 PM - 06:00 PM)":
            continue
        elif slot_filter == "🌙 Late Evening (> 6 PM)" and card_slot != "🌙 Late Evening (After 06:00 PM)":
            continue

        rendered_count += 1
        render_follow_up_card(
            db_adapter=db_adapter,
            client_id=cid,
            client_name=cname,
            address=addr,
            city=cty,
            product=prod,
            last_price=50000.0,
            followups_count=log_count,
            remarks_history=history_remarks,
            current_user_name=current_user_name,
            card_slot=card_slot,
            display_call_badge=display_call_badge,
            key=f"slot_card_{lead_id}"
        )

    if rendered_count == 0:
        st.success(f"🎉 No follow-up reminders matching your search/filter criteria (`{date_filter}`).")


def render_follow_up_card(db_adapter, client_id, client_name, address, city, product, last_price, followups_count, remarks_history, current_user_name, card_slot, display_call_badge, key):
    """Renders an individual follow-up card with time badges and action logging form."""
    st.markdown(f"""
    <div class='saas-card'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <span style='color: #184B9C; font-weight: 800; font-size: 17px;'>👤 {client_name}</span>
                <span style='color: #64748B; font-weight: 600; font-size: 13.5px; margin-left: 10px;'>({client_id})</span>
            </div>
            <div>
                <span style='background: #FEF3C7; color: #D97706; padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 12px; margin-right: 6px;'>
                    ⏰ Call: {display_call_badge}
                </span>
                <span style='background: #E0F2FE; color: #0369A1; padding: 4px 14px; border-radius: 20px; font-weight: 800; font-size: 12.5px;'>
                    Follow-up #{followups_count}
                </span>
            </div>
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
            f_notes = st.text_area("Client Conversation Notes *", placeholder="e.g. Client requested callback today at 5 PM...", key=f"notes_{key}")
            
            c1, c2 = st.columns(2)
            with c1:
                next_date = st.date_input("Next Follow-up Date *", value=datetime.date.today(), key=f"date_{key}")
            with c2:
                next_time = st.time_input("Next Follow-up Time *", value=datetime.time(17, 0), key=f"time_{key}")

            submit_fol = st.form_submit_button("✅ Follow-up Done")

            if submit_fol:
                if f_status == "Choose...":
                    st.error("Please select a valid Call Outcome / Status.")
                else:
                    df_leads = db_adapter.fetch_all("leads_master")
                    matched_lead = df_leads[df_leads["client_id"] == client_id]
                    
                    if not matched_lead.empty:
                        lead_id = int(matched_lead.iloc[0]["lead_id"])
                        sched_ts = f"{next_date} {next_time.strftime('%H:%M:%S')}"

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

                        st.toast(f"✅ Follow-up logged for {client_name}! Next call set for {sched_ts}.", icon="🎉")
                        st.rerun()