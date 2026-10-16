"""components/time_picker.py - Unambiguous 12-hour time entry (hour, minute, AM/PM)."""
import datetime

import streamlit as st

HOURS = [str(h) for h in range(1, 13)]
MINUTES = ["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55"]


def time_12h(label: str, key: str, default: datetime.time = datetime.time(11, 0)) -> datetime.time:
    """Three dropdowns: hour (1-12), minute, AM/PM. Returns a datetime.time."""
    h12 = default.hour % 12 or 12
    minute = f"{(default.minute // 5) * 5:02d}"
    ampm = "AM" if default.hour < 12 else "PM"
    st.markdown(f"<div style='font-size:14px; margin-bottom:-6px;'>{label}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1.1])
    with c1:
        hour = st.selectbox("Hour", HOURS, index=HOURS.index(str(h12)), key=f"{key}_h", label_visibility="collapsed")
    with c2:
        mins = st.selectbox("Minute", MINUTES, index=MINUTES.index(minute), key=f"{key}_m", label_visibility="collapsed")
    with c3:
        period = st.segmented_control("AM/PM", ["AM", "PM"], default=ampm, key=f"{key}_p",
                                      label_visibility="collapsed") or ampm
    hour24 = int(hour) % 12 + (12 if period == "PM" else 0)
    return datetime.time(hour24, int(mins))


def fmt_12h(value) -> str:
    """'2026-10-15 17:30:00' -> '15 Oct, 05:30 PM'."""
    from utils.time_utils import parse_ts
    ts = parse_ts(value)
    return ts.strftime("%d %b, %I:%M %p") if ts else "—"
