"""
components/styles.py - Brand theme: royal blue + emerald, Inter type,
pill navigation, KPI tiles and gentle interaction feedback.
"""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --navy: #0E2C68; --blue: #184B9C; --blue-soft: #E8EFFB; --green: #00A859;
  --green-dark: #008F4C; --red: #BE123C; --amber: #B45309; --ink: #0E2C68;
  --muted: #64748B; --line: rgba(24, 75, 156, 0.16); --surface: #FFFFFF; --page: #F4F7FC;
}

html, body, .stApp { font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important; }
.stApp { background: var(--page) !important; color: var(--ink); }
.block-container { padding-top: 1.6rem !important; padding-bottom: 3rem !important; max-width: 1400px; }
h1, h2, h3, h4, h5, h6 { color: var(--navy) !important; letter-spacing: -0.01em; }

/* ---------- sidebar & pill navigation ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #184B9C 0%, #0E2C68 100%) !important;
  border-right: 1px solid rgba(255,255,255,0.08) !important;
}
[data-testid="stSidebar"] * { color: #FFFFFF !important; }
[data-testid="stSidebar"] img { border-radius: 12px; background: #FFFFFF; padding: 8px; }
[data-testid="stSidebar"] [data-testid="stRadio"], [data-testid="stSidebar"] [data-testid="stRadio"] > div,
[data-testid="stSidebar"] div:has(> [data-testid="stRadioOption"]) { width: 100% !important; }
[data-testid="stSidebar"] div:has(> [data-testid="stRadioOption"]) { display: flex; flex-direction: column; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] {
  width: 100% !important; box-sizing: border-box; padding: 9px 12px; border-radius: 10px; margin: 1px 0 !important;
  transition: background 0.15s ease, transform 0.15s ease;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div > div:first-child:not([data-testid]) { display: none !important; }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover { background: rgba(255,255,255,0.10); transform: translateX(2px); }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) {
  background: #FFFFFF; box-shadow: 0 4px 14px rgba(0,0,0,0.18);
}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) * { color: var(--navy) !important; font-weight: 700; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] p { font-size: 14.5px; }

/* ---------- inputs (Streamlit 1.6x test ids) ---------- */
[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"],
[data-testid="stTextAreaRootElement"], [data-testid="stDateInputField"] {
  background-color: #FFFFFF !important; border: 1.5px solid #C9D6EE !important; border-radius: 10px !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
[data-testid="stTextInputRootElement"]:focus-within, [data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stTextAreaRootElement"]:focus-within, [data-testid="stDateInputField"]:focus-within {
  border-color: var(--blue) !important; box-shadow: 0 0 0 3px rgba(24,75,156,0.15) !important;
}
[data-testid="stTextInputRootElement"] input:disabled, .stTextInput input:disabled {
  background-color: #EEF3FB !important; color: var(--navy) !important; -webkit-text-fill-color: var(--navy) !important;
  font-weight: 700 !important; opacity: 1 !important;
}

/* ---------- buttons ---------- */
div.stButton > button, div[data-testid="stFormSubmitButton"] button, div.stDownloadButton > button {
  background: linear-gradient(135deg, #00A859 0%, #008F4C 100%) !important; color: #FFFFFF !important;
  border: none !important; border-radius: 10px !important; font-weight: 700 !important;
  padding: 0.55rem 1.2rem !important; box-shadow: 0 4px 14px rgba(0,168,89,0.28) !important;
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease !important;
}
div.stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover, div.stDownloadButton > button:hover {
  transform: translateY(-1px); box-shadow: 0 8px 20px rgba(0,168,89,0.35) !important; filter: brightness(1.04);
}
div.stButton > button:active, div[data-testid="stFormSubmitButton"] > button:active { transform: translateY(0); }
div.stButton > button:disabled { background: #CBD5E1 !important; box-shadow: none !important; }
div.stButton > button:focus-visible { outline: 3px solid rgba(24,75,156,0.45) !important; outline-offset: 2px; }

/* ---------- tabs, expanders, tables ---------- */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: 8px 16px; font-weight: 600; color: var(--muted); }
.stTabs [aria-selected="true"] { color: var(--blue) !important; background: var(--blue-soft); }
[data-testid="stExpander"] details { border: 1px solid var(--line) !important; border-radius: 12px !important; background: #FFFFFF; }
[data-testid="stExpander"] summary:hover { color: var(--blue) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #FFFFFF; }
[data-testid="stForm"] { background: #FFFFFF; border: 1px solid var(--line) !important; border-radius: 14px; }

/* ---------- cards ---------- */
.saas-card {
  background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px; padding: 18px 22px;
  box-shadow: 0 2px 10px rgba(14,44,104,0.05); margin-bottom: 14px;
  transition: box-shadow 0.18s ease, border-color 0.18s ease;
}
.saas-card:hover { border-color: rgba(24,75,156,0.35); box-shadow: 0 8px 24px rgba(14,44,104,0.10); }

/* ---------- KPI tiles ---------- */
.kpi {
  position: relative; background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px;
  padding: 14px 16px 13px 18px; min-height: 104px; overflow: hidden; margin-bottom: 12px;
  box-shadow: 0 2px 10px rgba(14,44,104,0.05);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  animation: kpi-in 0.45s ease both;
}
.kpi:hover { transform: translateY(-2px); box-shadow: 0 10px 26px rgba(14,44,104,0.12); }
.kpi::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--tone); }
.kpi .kpi-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.kpi .kpi-label { color: var(--muted); font-size: 13px; font-weight: 600; line-height: 1.3; }
.kpi .kpi-icon { width: 30px; height: 30px; border-radius: 9px; display: flex; align-items: center;
  justify-content: center; font-size: 15px; background: var(--tone-soft); flex-shrink: 0; }
.kpi .kpi-value { color: var(--navy); font-size: 26px; font-weight: 800; line-height: 1.15; margin-top: 6px;
  font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kpi .kpi-sub { font-size: 12.5px; color: var(--muted); margin-top: 4px; }
.kpi .up { color: #047857; font-weight: 700; } .kpi .down { color: var(--red); font-weight: 700; }
@keyframes kpi-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* ---------- call links ---------- */
.call-btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 20px;
  font-weight: 700; font-size: 13px; text-decoration: none !important; margin-right: 6px;
  transition: transform 0.15s ease, box-shadow 0.15s ease; }
.call-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(14,44,104,0.15); }
.call-btn.phone { background: var(--blue); color: #FFFFFF !important; }
.call-btn.wa { background: #E7F8EF; color: #047857 !important; border: 1px solid #A7E3C3; }
.call-btn.mail { background: var(--blue-soft); color: var(--blue) !important; }

.pill { display: inline-block; padding: 3px 11px; border-radius: 20px; font-weight: 700; font-size: 12px;
  margin-left: 6px; white-space: nowrap; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
"""


def apply_custom_theme():
    st.markdown(CSS, unsafe_allow_html=True)
