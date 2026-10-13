"""
utils/auth.py - Authentication Engine for Employees Relational Table
"""
import streamlit as st

# Emergency hardcoded fallback map to ensure immediate login
DEFAULT_CREDENTIALS = {
    "admin": {"password": "admin123", "role": "ADMIN", "name": "System Administrator", "email": "admin@sidharth.com", "employee_id": "EMP-108"},
    "admin@sidharth.com": {"password": "admin123", "role": "ADMIN", "name": "System Administrator", "email": "admin@sidharth.com", "employee_id": "EMP-108"},
    "albert": {"password": "albert123", "role": "LGE", "name": "Albert Singh", "email": "albert@sidharth.com", "employee_id": "EMP-101"},
    "albert@sidharth.com": {"password": "albert123", "role": "LGE", "name": "Albert Singh", "email": "albert@sidharth.com", "employee_id": "EMP-101"},
    "pooja": {"password": "pooja123", "role": "QS", "name": "Pooja", "email": "pooja@sidharth.com", "employee_id": "EMP-102"},
    "pooja@sidharth.com": {"password": "pooja123", "role": "QS", "name": "Pooja", "email": "pooja@sidharth.com", "employee_id": "EMP-102"},
    "anjali": {"password": "anjali123", "role": "QS", "name": "Anjali", "email": "anjali@sidharth.com", "employee_id": "EMP-103"},
    "anjali@sidharth.com": {"password": "anjali123", "role": "QS", "name": "Anjali", "email": "anjali@sidharth.com", "employee_id": "EMP-103"},
    "dolly": {"password": "dolly123", "role": "QS", "name": "Dolly", "email": "dolly@sidharth.com", "employee_id": "EMP-104"},
    "dolly@sidharth.com": {"password": "dolly123", "role": "QS", "name": "Dolly", "email": "dolly@sidharth.com", "employee_id": "EMP-104"},
    "jeevan": {"password": "jeevan123", "role": "SAM", "name": "Jeevan Sharma", "email": "jeevan@sidharth.com", "employee_id": "EMP-105"},
    "jeevan@sidharth.com": {"password": "jeevan123", "role": "SAM", "name": "Jeevan Sharma", "email": "jeevan@sidharth.com", "employee_id": "EMP-105"},
    "jitendra": {"password": "jitendra123", "role": "SAM", "name": "Jitendra Sharma", "email": "jitendra@sidharth.com", "employee_id": "EMP-106"},
    "jitendra@sidharth.com": {"password": "jitendra123", "role": "SAM", "name": "Jitendra Sharma", "email": "jitendra@sidharth.com", "employee_id": "EMP-106"},
    "deepak": {"password": "deepak123", "role": "SAM", "name": "Deepak Sethiya", "email": "deepak@sidharth.com", "employee_id": "EMP-107"},
    "deepak@sidharth.com": {"password": "deepak123", "role": "SAM", "name": "Deepak Sethiya", "email": "deepak@sidharth.com", "employee_id": "EMP-107"},
}


def init_session_auth():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["user"] = None


def login_user(db_adapter, identifier: str, password: str) -> bool:
    if not identifier or not password:
        return False

    clean_id = str(identifier).strip().lower()
    clean_pwd = str(password).strip()

    # 1. Fallback Registry Check
    if clean_id in DEFAULT_CREDENTIALS:
        account = DEFAULT_CREDENTIALS[clean_id]
        if account["password"] == clean_pwd:
            st.session_state["authenticated"] = True
            st.session_state["user"] = {
                "employee_id": account["employee_id"],
                "name": account["name"],
                "email": account["email"],
                "role": account["role"],
            }
            return True

    # 2. Relational Employees Table Check
    try:
        df_emp = db_adapter.fetch_all("employees")
        if df_emp is not None and not df_emp.empty:
            for _, row in df_emp.iterrows():
                e_id = str(row.get("employee_id", "")).strip().lower()
                e_email = str(row.get("email", "")).strip().lower()
                e_name = str(row.get("full_name", "")).strip().lower()
                e_pwd = str(row.get("password", "")).strip()

                if (clean_id in [e_id, e_email, e_name]) and clean_pwd == e_pwd:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = {
                        "employee_id": row.get("employee_id", ""),
                        "name": row.get("full_name", "User"),
                        "email": row.get("email", ""),
                        "role": str(row.get("role", "LGE")).upper(),
                    }
                    return True
    except Exception as e:
        st.error(f"Authentication DB Error: {e}")

    return False


def logout_user():
    st.session_state["authenticated"] = False
    st.session_state["user"] = None


def get_current_user() -> dict:
    return st.session_state.get("user", {"employee_id": "EMP-101", "name": "Guest", "role": "LGE", "email": ""})