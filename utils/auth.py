"""
Authentication & Session Governance Engine for Sidharth Shutter CRM.
Handles database verification with automatic hardcoded fallbacks.
"""
import streamlit as st

# Hardcoded fallback registry to guarantee instant login regardless of DB state
DEFAULT_CREDENTIALS = {
    "admin": {"password": "admin123", "role": "ADMIN", "name": "System Administrator", "email": "admin@sidharth.com", "user_id": "U108"},
    "admin@sidharth.com": {"password": "admin123", "role": "ADMIN", "name": "System Administrator", "email": "admin@sidharth.com", "user_id": "U108"},
    "albert": {"password": "albert123", "role": "LGE", "name": "Albert Singh", "email": "albert@sidharth.com", "user_id": "U101"},
    "albert@sidharth.com": {"password": "albert123", "role": "LGE", "name": "Albert Singh", "email": "albert@sidharth.com", "user_id": "U101"},
    "pooja": {"password": "pooja123", "role": "QS", "name": "Pooja", "email": "pooja@sidharth.com", "user_id": "U102"},
    "pooja@sidharth.com": {"password": "pooja123", "role": "QS", "name": "Pooja", "email": "pooja@sidharth.com", "user_id": "U102"},
    "anjali": {"password": "anjali123", "role": "QS", "name": "Anjali", "email": "anjali@sidharth.com", "user_id": "U103"},
    "anjali@sidharth.com": {"password": "anjali123", "role": "QS", "name": "Anjali", "email": "anjali@sidharth.com", "user_id": "U103"},
    "dolly": {"password": "dolly123", "role": "QS", "name": "Dolly", "email": "dolly@sidharth.com", "user_id": "U104"},
    "dolly@sidharth.com": {"password": "dolly123", "role": "QS", "name": "Dolly", "email": "dolly@sidharth.com", "user_id": "U104"},
    "jeevan": {"password": "jeevan123", "role": "SAM", "name": "Jeevan Sharma", "email": "jeevan@sidharth.com", "user_id": "U105"},
    "jeevan@sidharth.com": {"password": "jeevan123", "role": "SAM", "name": "Jeevan Sharma", "email": "jeevan@sidharth.com", "user_id": "U105"},
    "jitendra": {"password": "jitendra123", "role": "SAM", "name": "Jitendra Sharma", "email": "jitendra@sidharth.com", "user_id": "U106"},
    "jitendra@sidharth.com": {"password": "jitendra123", "role": "SAM", "name": "Jitendra Sharma", "email": "jitendra@sidharth.com", "user_id": "U106"},
    "deepak": {"password": "deepak123", "role": "SAM", "name": "Deepak Sethiya", "email": "deepak@sidharth.com", "user_id": "U107"},
    "deepak@sidharth.com": {"password": "deepak123", "role": "SAM", "name": "Deepak Sethiya", "email": "deepak@sidharth.com", "user_id": "U107"},
}


def init_session_auth():
    """Initializes authentication flags in Streamlit session state."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["user"] = None


def login_user(db_adapter, identifier: str, password: str) -> bool:
    """
    Validates login credentials against Supabase database with fallback to default profiles.
    Matches across username, email, user_id, or full_name.
    """
    if not identifier or not password:
        return False

    clean_id = str(identifier).strip().lower()
    clean_pwd = str(password).strip()

    # 1. First check hardcoded fallback map for instantaneous sign-in
    if clean_id in DEFAULT_CREDENTIALS:
        account = DEFAULT_CREDENTIALS[clean_id]
        if account["password"] == clean_pwd:
            st.session_state["authenticated"] = True
            st.session_state["user"] = {
                "name": account["name"],
                "email": account["email"],
                "role": account["role"],
                "user_id": account["user_id"],
            }
            return True

    # 2. Database verification via active Supabase adapter
    try:
        df_users = db_adapter.fetch_all("users")
        if df_users is not None and not df_users.empty:
            for _, row in df_users.iterrows():
                u_id = str(row.get("user_id", "")).strip().lower()
                u_email = str(row.get("email", "")).strip().lower()
                u_name = str(row.get("full_name", "")).strip().lower()
                u_pwd = str(row.get("password", "")).strip()

                # Flexible check matching user_id, email, or full name
                if (clean_id in [u_id, u_email, u_name]) and clean_pwd == u_pwd:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = {
                        "name": row.get("full_name", row.get("user_id", "User")),
                        "email": row.get("email", ""),
                        "role": str(row.get("role", "LGE")).upper(),
                        "user_id": row.get("user_id", ""),
                    }
                    return True
    except Exception as e:
        st.error(f"Database authentication query error: {e}")

    return False


def logout_user():
    """Clears authentication session state."""
    st.session_state["authenticated"] = False
    st.session_state["user"] = None


def get_current_user() -> dict:
    """Returns current logged in user details dictionary."""
    return st.session_state.get("user", {"name": "Guest", "role": "LGE", "email": "", "user_id": ""})