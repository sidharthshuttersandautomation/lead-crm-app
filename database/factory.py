"""
database/factory.py - Builds the configured adapter and prepares the database.

The engine is chosen in .streamlit/secrets.toml ([database] engine = "sqlite").
A Postgres/Supabase adapter can be added here later without touching the views.
"""
import streamlit as st

from config.settings import DEFAULT_PRODUCTS, PRODUCT_LIST, ROLES, SALESPERSON_LIST
from database.sqlite_adapter import SQLiteAdapter
from utils.security import hash_password, verify_password
from utils.time_utils import now_str

DEFAULT_DB_PATH = "data/crm_database.db"


def _secret(section, key, default=None):
    try:
        return st.secrets[section][key]
    except Exception:
        return default


def get_adapter():
    engine = str(_secret("database", "engine", "sqlite")).lower()
    if engine != "sqlite":
        raise RuntimeError(f"Database engine '{engine}' is not available yet. Use 'sqlite'.")
    return SQLiteAdapter(_secret("database", "sqlite_path", DEFAULT_DB_PATH))


@st.cache_resource(show_spinner=False)
def _init_schema_once(db_path_key: str):
    """Create tables and the product list once per server process."""
    db = get_adapter()
    db.init_schema()
    db.set_actor("SYSTEM")
    sync_products(db)
    return True


def sync_products(db):
    """Every product in PRODUCT_LIST exists and is active; any other product is hidden from dropdowns."""
    existing = db.fetch_all("products")
    have = {str(n).lower(): (int(i), int(a)) for n, i, a in
            zip(existing["product_name"], existing["product_id"], existing["is_active"])} if not existing.empty else {}
    wanted = {p.lower() for p in PRODUCT_LIST}
    for name in PRODUCT_LIST:
        if name.lower() not in have:
            db.insert_row("products", {"product_name": name, "category": "Products", "is_active": 1})
        elif have[name.lower()][1] != 1:
            db.update_row("products", "product_id", have[name.lower()][0], {"is_active": 1})
    for key, (pid, active) in have.items():
        if key not in wanted and active == 1:
            db.update_row("products", "product_id", pid, {"is_active": 0})


@st.cache_resource(show_spinner=False)
def _post_account_migrations_once(db_path_key: str, employee_count: int):
    """Default flags for accounts created after start-up (runs again whenever the number of employees changes)."""
    get_adapter().run_data_migrations()
    return True


@st.cache_resource(show_spinner=False)
def _sync_salespeople_once(db_path_key: str, names: tuple):
    from utils.people import ensure_people
    db = get_adapter()
    db.set_actor("SYSTEM")
    return ensure_people(db, list(names), role="SAM")


def secrets_status() -> str:
    """Explains what is missing from the secrets, for the sign-in screen."""
    try:
        sections = list(st.secrets.keys())
    except Exception:
        return ("No secrets were found. Locally, create .streamlit/secrets.toml in the folder you run "
                "'streamlit run' from. On Streamlit Cloud, paste them in App settings → Secrets.")
    if "bootstrap" not in sections:
        found = ", ".join(f"[{s}]" for s in sections) or "none"
        return f"Secrets were found but there is no [bootstrap] section (sections found: {found})."
    missing = [k for k in ("admin_email", "admin_password") if not _secret("bootstrap", k)]
    if missing and _accounts_from_secrets():
        return ""
    if missing:
        return "The [bootstrap] section is missing: " + ", ".join(missing) + "."
    return ""


def _accounts_from_secrets() -> dict:
    try:
        return dict(st.secrets.get("accounts", {}))
    except Exception:
        return {}


def sync_accounts(db) -> list:
    """
    Creates every account listed under [accounts.<username>] in secrets that does
    not exist yet (matched by email). Existing accounts are never changed, so a
    password changed inside the app is kept. Returns messages for problems.
    """
    problems = []
    accounts = _accounts_from_secrets()
    if not accounts:
        return problems
    existing = db.fetch_all("employees")
    emails = set(existing["email"].str.lower()) if not existing.empty else set()
    ids = set(existing["employee_id"]) if not existing.empty else set()
    for username, acc in accounts.items():
        try:
            acc = dict(acc)
        except Exception:
            problems.append(f"[accounts.{username}] is not a table.")
            continue
        email = str(acc.get("email") or f"{username}@sidharth.com").strip().lower()
        if email in emails:
            continue
        role = str(acc.get("role", "")).upper()
        password = acc.get("password")
        if role not in ROLES or not password:
            problems.append(f"[accounts.{username}] needs a valid role ({', '.join(ROLES)}) and a password.")
            continue
        emp_id = str(acc.get("employee_id") or "").strip() or db.next_employee_id()
        if emp_id in ids:
            emp_id = db.next_employee_id()
        ok = db.insert_row("employees", {
            "employee_id": emp_id, "full_name": str(acc.get("name") or username.title()),
            "email": email, "password_hash": hash_password(str(password)), "role": role,
            "is_active": 1, "created_at": now_str(),
        })
        if ok is None:
            problems.append(f"[accounts.{username}]: {db.last_error}")
        else:
            emails.add(email)
            ids.add(emp_id)
    return problems


@st.cache_resource(show_spinner=False)
def _sync_passwords_once(db_path_key: str, fingerprint: str) -> int:
    """
    When [bootstrap] sync_passwords = "true": set every account listed in secrets
    to the password in secrets. Runs once per server start / secrets change.
    """
    db = get_adapter()
    db.set_actor("SYSTEM")
    changed = 0
    for username, acc in _accounts_from_secrets().items():
        acc = dict(acc)
        email = str(acc.get("email") or f"{username}@sidharth.com").strip().lower()
        record = db.get_login_record(email)
        if record and acc.get("password") and not verify_password(str(acc["password"]), record["password_hash"]):
            updates = {"password_hash": hash_password(str(acc["password"])), "is_active": 1}
            if db.update_row("employees", "employee_id", record["employee_id"], updates):
                changed += 1
    print(f"Password sync: {changed} account(s) updated from secrets.")
    return changed


def bootstrap_database(db_path_key: str):
    """
    Runs on every page load but only does work when needed:
    tables/products once per process; first admin and demo data whenever the
    database has no employees (so adding secrets later works without a reboot).
    """
    _init_schema_once(db_path_key)
    db = get_adapter()
    db.set_actor("SYSTEM")

    if db.count_rows("employees") == 0:
        email = _secret("bootstrap", "admin_email")
        password = _secret("bootstrap", "admin_password")
        if email and password:
            db.insert_row("employees", {
                "employee_id": "EMP-100",
                "full_name": _secret("bootstrap", "admin_name", "System Administrator"),
                "email": str(email).strip().lower(),
                "password_hash": hash_password(str(password)),
                "role": "ADMIN",
                "is_active": 1,
                "created_at": now_str(),
            })

    if _accounts_from_secrets():
        for problem in sync_accounts(db):
            print("Account setup:", problem)
        if str(_secret("bootstrap", "sync_passwords", "false")).lower() == "true":
            import hashlib, json
            fingerprint = hashlib.sha256(json.dumps(
                {k: dict(v) for k, v in _accounts_from_secrets().items()}, sort_keys=True, default=str
            ).encode()).hexdigest()
            _sync_passwords_once(db_path_key, fingerprint)

    if db.count_rows("employees") > 0:
        _sync_salespeople_once(db_path_key, tuple(SALESPERSON_LIST))
        _post_account_migrations_once(db_path_key, db.count_rows("employees"))

    if db.count_rows("employees") > 0 and db.count_rows("leads_master") == 0 \
            and str(_secret("bootstrap", "seed_demo_data", "false")).lower() == "true":
        from scripts.seed_demo_data import seed_demo_data
        seed_demo_data(db, demo_password=_secret("bootstrap", "demo_password"))
    return True
