import streamlit as st

def init_session_auth():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user" not in st.session_state:
        st.session_state["user"] = None

def login_user(db_adapter, email, password):
    users_df = db_adapter.fetch_table("users")
    if not users_df.empty:
        match = users_df[(users_df["email"] == email) & (users_df["password_hash"] == password)]
        if not match.empty:
            st.session_state["authenticated"] = True
            st.session_state["user"] = match.iloc[0].to_dict()
            return True
    return False

def logout_user():
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.rerun()