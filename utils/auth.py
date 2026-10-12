import streamlit as st

def init_session_auth():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["user"] = None

def login_user(db_adapter, user_name: str, role: str) -> bool:
    st.session_state["authenticated"] = True
    st.session_state["user"] = {
        "name": user_name,
        "role": role,
    }
    return True

def logout_user():
    st.session_state["authenticated"] = False
    st.session_state["user"] = None

def get_current_user() -> dict:
    return st.session_state.get("user", {"name": "Guest", "role": "LGE"})