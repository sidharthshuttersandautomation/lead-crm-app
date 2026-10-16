"""
utils/auth.py - Login against the employees table (hashed passwords only).

There are no built-in fallback accounts. The first admin is created from
secrets.toml ([bootstrap]) when the database is empty.
"""
import time

import streamlit as st

from utils.security import verify_password

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


def init_session_auth():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("failed_logins", 0)
    st.session_state.setdefault("locked_until", 0.0)


def login_user(db_adapter, identifier: str, password: str):
    """Returns (success, message)."""
    if time.time() < st.session_state.get("locked_until", 0):
        wait = int(st.session_state["locked_until"] - time.time()) // 60 + 1
        return False, f"Too many failed attempts. Try again in {wait} minute(s)."

    if not identifier or not password:
        return False, "Enter your username or email and your password."

    record = db_adapter.get_login_record(identifier)
    ok = bool(record) and int(record.get("is_active", 0)) == 1 and verify_password(password, record.get("password_hash", ""))

    if not ok:
        st.session_state["failed_logins"] += 1
        db_adapter.set_actor(record.get("employee_id") if record else None)
        db_adapter.log_event("LOGIN_FAILED", "employees", record.get("employee_id") if record else None,
                             None, {"identifier": str(identifier)[:80]})
        if st.session_state["failed_logins"] >= MAX_FAILED_ATTEMPTS:
            st.session_state["locked_until"] = time.time() + LOCKOUT_SECONDS
            st.session_state["failed_logins"] = 0
        if record and int(record.get("is_active", 0)) != 1:
            return False, "This account is deactivated. Ask an admin to reactivate it."
        return False, "Username or password is incorrect."

    st.session_state["failed_logins"] = 0
    st.session_state["authenticated"] = True
    st.session_state["user"] = {
        "employee_id": record["employee_id"],
        "name": record["full_name"],
        "email": record["email"],
        "role": str(record["role"]).upper(),
        "is_team_lead": int(record.get("is_team_lead") or 0) == 1,
    }
    db_adapter.set_actor(record["employee_id"])
    db_adapter.log_event("LOGIN", "employees", record["employee_id"])
    return True, "Signed in."


def logout_user(db_adapter=None):
    user = st.session_state.get("user") or {}
    if db_adapter is not None and user:
        db_adapter.set_actor(user.get("employee_id"))
        db_adapter.log_event("LOGOUT", "employees", user.get("employee_id"))
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_auth()


def get_current_user():
    return st.session_state.get("user")
