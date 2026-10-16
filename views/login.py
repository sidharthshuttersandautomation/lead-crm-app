"""
views/login.py - Sign-in screen: brand panel on the left, sign-in card on the right.
On phones the brand panel hides and the logo moves into the card.
"""
import base64
from pathlib import Path

import streamlit as st

from config.settings import LOGO_PATH
from database.factory import secrets_status
from utils.auth import login_user

APP_VERSION = "3.1"

LOGIN_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], header[data-testid="stHeader"] { display: none !important; }
.stApp { background:
    radial-gradient(1200px 500px at 10% -10%, rgba(24,75,156,0.10), transparent 60%),
    radial-gradient(900px 400px at 110% 110%, rgba(0,168,89,0.08), transparent 60%), #F4F7FC !important; }
.block-container { max-width: 1060px !important; padding-top: 7vh !important; }

/* brand panel */
.login-brand {
  min-height: 600px; border-radius: 20px; padding: 32px 36px; color: #FFFFFF; position: relative; overflow: hidden;
  background: linear-gradient(150deg, #184B9C 0%, #0E2C68 70%);
  box-shadow: 0 20px 50px rgba(14,44,104,0.22); display: flex; flex-direction: column;
}
.login-brand::after { content: ""; position: absolute; width: 360px; height: 360px; right: -120px; bottom: -140px;
  border-radius: 50%; background: radial-gradient(circle, rgba(0,168,89,0.35), transparent 70%); }
.login-brand .logo-chip { background: #FFFFFF; border-radius: 14px; padding: 12px 16px; width: 230px; }
.login-brand .logo-chip img { width: 100%; display: block; }
.login-brand h1 { color: #FFFFFF !important; font-size: 30px; line-height: 1.2; font-weight: 800; margin: 34px 0 10px; letter-spacing: -0.02em; }
.login-brand p.lead { color: #D6E2F7; font-size: 15px; line-height: 1.6; margin: 0 0 26px; max-width: 400px; }
.login-brand .feat { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 14px; position: relative; z-index: 1; }
.login-brand .feat .ic { width: 36px; height: 36px; border-radius: 10px; background: rgba(255,255,255,0.12);
  display: flex; align-items: center; justify-content: center; font-size: 17px; flex-shrink: 0; }
.login-brand .feat b { display: block; font-size: 14.5px; color: #FFFFFF; }
.login-brand .feat span { display: block; font-size: 13px; line-height: 1.45; color: #B9CBEA; margin-top: 2px; }
.login-brand .feat b { line-height: 1.3; }
.login-brand .foot { margin-top: auto; font-size: 12px; color: #9FB4DA; position: relative; z-index: 1; }

/* sign-in card */
.st-key-login_card {
  background: #FFFFFF; border: 1px solid rgba(24,75,156,0.14); border-radius: 20px; padding: 40px 38px 26px !important;
  min-height: 600px; box-shadow: 0 20px 50px rgba(14,44,104,0.10); justify-content: center;
}
.st-key-login_card [data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }
.st-key-login_card label p { font-size: 13.5px !important; font-weight: 600 !important; color: #0E2C68 !important; }
.st-key-login_card [data-testid="stTextInputRootElement"] {
  background: #F8FAFC !important; border: 1.5px solid #CBD5E1 !important; border-radius: 11px !important; min-height: 48px;
}
.st-key-login_card [data-testid="stTextInputRootElement"]:focus-within { border-color: #184B9C !important;
  background: #FFFFFF !important; box-shadow: 0 0 0 4px rgba(24,75,156,0.12) !important; }
.st-key-login_card input { font-size: 15px !important; color: #0E2C68 !important; }
.st-key-login_card [data-testid="stFormSubmitButton"], .st-key-login_card [data-testid="stFormSubmitButton"] > div { width: 100% !important; }
.st-key-login_card [data-testid="stFormSubmitButton"] button { width: 100% !important; min-height: 48px; font-size: 15.5px !important;
  margin-top: 6px; }
.login-eyebrow { font-size: 12px; font-weight: 800; letter-spacing: 0.12em; color: #00A859; text-transform: uppercase; }
.login-title { font-size: 26px; font-weight: 800; color: #0E2C68; margin: 6px 0 4px; letter-spacing: -0.02em; }
.login-sub { font-size: 14px; color: #64748B; margin-bottom: 22px; }
.login-help { border-top: 1px solid #E2E8F0; margin-top: 18px; padding-top: 14px; font-size: 13px; color: #64748B;
  display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.login-mobile-logo { display: none; margin-bottom: 18px; }
.login-mobile-logo img { width: 190px; }

@media (max-width: 760px) {
  .login-brand { display: none; }
  .login-mobile-logo { display: block; }
  .st-key-login_card { min-height: 0; padding: 28px 22px 20px !important; }
  .block-container { padding-top: 3vh !important; }
}
</style>
"""


@st.cache_data(show_spinner=False)
def _logo_data_uri(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


def render_login(db_adapter, root_dir: Path):
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    logo = _logo_data_uri(str(root_dir / LOGO_PATH))
    logo_img = f"<img src='{logo}' alt='Sidharth Shutter & Automation'>" if logo else "<b style='color:#184B9C;'>SIDHARTH</b>"

    brand, card = st.columns([1.08, 1], gap="medium")
    with brand:
        st.markdown(f"""
        <div class='login-brand'>
          <div class='logo-chip'>{logo_img}</div>
          <h1>Every lead, quote<br>and payment in one place.</h1>
          <p class='lead'>The CRM and operations portal for Sidharth Shutter &amp; Automation.</p>
          <div class='feat'><div class='ic'>📥</div><div><b>Capture and assign leads</b>
            <span>Every enquiry reaches the right specialist the moment it's saved.</span></div></div>
          <div class='feat'><div class='ic'>📄</div><div><b>Quote, revise and follow up</b>
            <span>Revisions, discounts and call reminders tracked to the minute.</span></div></div>
          <div class='feat'><div class='ic'>💰</div><div><b>Orders and collections</b>
            <span>See what's sold, what's received and who still has to pay.</span></div></div>
          <div class='foot'>© Sidharth Shutter &amp; Automation · Internal use only</div>
        </div>""", unsafe_allow_html=True)

    with card:
        with st.container(key="login_card"):
            st.markdown(f"""
            <div class='login-mobile-logo'>{logo_img}</div>
            <div class='login-eyebrow'>Welcome back</div>
            <div class='login-title'>Sign in to your account</div>
            <div class='login-sub'>Use your username, work email or employee ID.</div>""", unsafe_allow_html=True)

            if db_adapter.count_rows("employees") == 0:
                st.error("No accounts exist yet, so the first admin can't be created.\n\n"
                         + (secrets_status() or "Secrets look correct. Refresh this page.")
                         + "\n\nSee README.md → Run locally / Deploy.")
                st.stop()

            with st.form("login_form", border=False):
                username = st.text_input("Username or email", placeholder="e.g. pooja or pooja@sidharth.com")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
            if submitted:
                with st.spinner("Signing you in..."):
                    ok, message = login_user(db_adapter, username.strip(), password)
                if ok:
                    st.rerun()
                st.error(message)

            st.markdown(f"""
            <div class='login-help'>
              <span>Forgot your password? Ask your administrator to reset it.</span>
              <span>Version {APP_VERSION}</span>
            </div>""", unsafe_allow_html=True)
