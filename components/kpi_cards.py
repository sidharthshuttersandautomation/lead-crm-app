"""
components/kpi_cards.py - KPI tiles.

Each item: {"label", "value", optional "help", "icon", "tone", "sub", "delta", "delta_good"}
  tone:  blue | green | red | amber | navy | teal  (accent colour)
  delta: number compared with the previous period; shown as ▲/▼ with "sub" text.
"""
import html

import streamlit as st

TONES = {
    "blue": ("#184B9C", "#E8EFFB"), "green": ("#00A859", "#E3F6EC"), "red": ("#BE123C", "#FDE7EA"),
    "amber": ("#B45309", "#FEF3C7"), "navy": ("#0E2C68", "#E2E8F4"), "teal": ("#0E7490", "#E0F4F8"),
}


def _delta_html(item):
    delta = item.get("delta")
    sub = html.escape(str(item.get("sub") or ""))
    if delta is None or delta == 0:
        return f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    good_when_up = item.get("delta_good", "up") == "up"
    up = delta > 0
    cls = "up" if up == good_when_up else "down"
    arrow = "▲" if up else "▼"
    shown = f"{abs(delta):,.0f}" if isinstance(delta, (int, float)) else html.escape(str(delta))
    return f"<div class='kpi-sub'><span class='{cls}'>{arrow} {shown}</span> {sub}</div>"


def render_kpi_cards(kpi_data: list, columns: int = None):
    if not kpi_data:
        return
    cols = st.columns(columns or len(kpi_data))
    for i, item in enumerate(kpi_data):
        tone, soft = TONES.get(item.get("tone", "blue"), TONES["blue"])
        icon = item.get("icon")
        icon_html = f"<div class='kpi-icon'>{icon}</div>" if icon else ""
        title = html.escape(str(item.get("help") or ""), quote=True)
        with cols[i % len(cols)]:
            st.markdown(
                f"<div class='kpi' style='--tone:{tone}; --tone-soft:{soft}; animation-delay:{i * 40}ms' title='{title}'>"
                f"<div class='kpi-top'><div class='kpi-label'>{html.escape(str(item.get('label', '')))}</div>{icon_html}</div>"
                f"<div class='kpi-value' style='font-size:{22 if len(str(item.get('value', ''))) > 10 else 26}px;'>"
                f"{html.escape(str(item.get('value', '')))}</div>"
                f"{_delta_html(item)}</div>",
                unsafe_allow_html=True,
            )


def page_title(text: str, caption: str = None):
    st.markdown(f"<h2 style='font-weight:800; margin:0 0 2px;'>{html.escape(text)}</h2>", unsafe_allow_html=True)
    if caption:
        st.caption(caption)
