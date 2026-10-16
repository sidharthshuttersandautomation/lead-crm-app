"""utils/people.py - Match people's names to employee records, creating missing ones."""
import re
import secrets

from utils.security import hash_password
from utils.time_utils import now_str


def name_key(name) -> str:
    return re.sub(r"[^a-z]", "", str(name).lower())


def ensure_people(db, names, role="SAM") -> dict:
    """
    Returns {name: employee_id} for every name (except "N/A"). Names not found among
    employees are created as INACTIVE records (no sign-in) so leads can be assigned to them.
    """
    emp = db.fetch_all("employees")
    by_key = {name_key(n): i for n, i in zip(emp["full_name"], emp["employee_id"])} if not emp.empty else {}
    taken = set(emp["email"].str.lower()) if not emp.empty else set()
    out = {}
    for name in names:
        if not name or name.strip().upper() == "N/A":
            continue
        key = name_key(name)
        if key in by_key:
            out[name] = by_key[key]
            continue
        words = [re.sub(r"[^a-z]", "", w) for w in name.lower().split()] or ["person"]
        email = f"{words[0]}@sidharth.com"
        if email in taken:
            email = f"{'.'.join(words)}@sidharth.com"
        emp_id = db.next_employee_id()
        if email in taken:
            email = f"{'.'.join(words)}.{emp_id.lower()}@sidharth.com"
        if db.insert_row("employees", {"employee_id": emp_id, "full_name": name, "email": email,
                                       "password_hash": hash_password(secrets.token_urlsafe(24)),
                                       "role": role, "is_active": 0, "created_at": now_str()}) is not None:
            taken.add(email)
            by_key[key] = emp_id
            out[name] = emp_id
    return out
