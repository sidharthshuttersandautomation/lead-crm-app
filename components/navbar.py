"""
Header Component.
"""
import streamlit as st

def render_navbar(current_user: dict):
    user_name = current_user.get("name") or current_user.get("full_name") or "User"
    user_email = current_user.get("email", "user@company.com")
    
    st.markdown(f"""
        <div style='background: linear-gradient(90deg, #184B9C 0%, #0E2C68 100%); padding: 14px 24px; border-radius: 12px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 16px rgba(14, 44, 104, 0.12);'>
            <div>
                <span style='color: #FFFFFF; font-weight: 800; font-size: 18px; letter-spacing: -0.01em;'>SIDHARTH SHUTTER & AUTOMATION</span>
                <span style='color: #00A859; font-weight: 700; font-size: 13px; margin-left: 10px; text-transform: uppercase;'>Enterprise Lead CRM</span>
            </div>
            <div style='background: rgba(255, 255, 255, 0.12); border: 1px solid rgba(255, 255, 255, 0.2); padding: 6px 14px; border-radius: 20px; color: #FFFFFF; font-size: 13px; font-weight: 600;'>
                👤 {user_name} ({user_email})
            </div>
        </div>
    """, unsafe_allow_html=True)