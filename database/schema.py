"""
database/schema.py - Table definitions.

Written in plain SQL that maps directly to Postgres later:
  INTEGER PRIMARY KEY AUTOINCREMENT  ->  BIGINT GENERATED ALWAYS AS IDENTITY
  TEXT timestamps (IST)              ->  TIMESTAMP
  REAL amounts                       ->  NUMERIC(12,2)
"""

SCHEMA_VERSION = 7

DDL = [
    """
    CREATE TABLE IF NOT EXISTS schema_info (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS employees (
        employee_id   TEXT PRIMARY KEY,
        full_name     TEXT NOT NULL,
        email         TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL,
        is_active     INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS products (
        product_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL UNIQUE,
        category     TEXT NOT NULL DEFAULT 'Automation',
        is_active    INTEGER NOT NULL DEFAULT 1
    )""",
    """
    CREATE TABLE IF NOT EXISTS customers (
        client_id      TEXT PRIMARY KEY,
        client_name    TEXT NOT NULL,
        company_name   TEXT,
        phone_number   TEXT NOT NULL,
        email          TEXT,
        address        TEXT,
        city           TEXT NOT NULL,
        state          TEXT,
        is_key_account INTEGER NOT NULL DEFAULT 0,
        created_at     TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS leads_master (
        lead_id            INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id          TEXT NOT NULL REFERENCES customers(client_id),
        product_id         INTEGER NOT NULL REFERENCES products(product_id),
        quantity           INTEGER NOT NULL DEFAULT 1,
        source             TEXT NOT NULL,
        type_of_client     TEXT NOT NULL DEFAULT 'New Buy',
        final_status       TEXT NOT NULL DEFAULT 'New',
        quotation_status   TEXT NOT NULL DEFAULT 'Not Sent',
        priority           TEXT NOT NULL DEFAULT 'Normal',
        remarks            TEXT,
        handled_by_lge_id  TEXT REFERENCES employees(employee_id),
        assigned_sam_id    TEXT REFERENCES employees(employee_id),
        claimed_qs_id      TEXT REFERENCES employees(employee_id),
        followup_owner_id  TEXT REFERENCES employees(employee_id),
        next_followup_at   TEXT,
        lost_reason        TEXT,
        ingestion_date     TEXT NOT NULL,
        ingested_at        TEXT NOT NULL,
        is_after_cutoff    INTEGER NOT NULL DEFAULT 0,
        sla_due_date       TEXT,
        claimed_at         TEXT,
        quote_sent_at      TEXT,
        closed_at          TEXT,
        updated_at         TEXT
    )""",
    """
    CREATE TABLE IF NOT EXISTS quotations_master (
        quotation_id       TEXT PRIMARY KEY,
        lead_id            INTEGER NOT NULL REFERENCES leads_master(lead_id),
        client_id          TEXT NOT NULL REFERENCES customers(client_id),
        quotation_number   TEXT NOT NULL,
        revision_no        INTEGER NOT NULL DEFAULT 0,
        qut_amount         REAL NOT NULL,
        quotation_status   TEXT NOT NULL DEFAULT 'Under Review',
        follow_up_required TEXT NOT NULL DEFAULT 'Yes',
        claimed_qs_id      TEXT REFERENCES employees(employee_id),
        approved_by_id     TEXT REFERENCES employees(employee_id),
        shared_by_id       TEXT REFERENCES employees(employee_id),
        folder_link        TEXT,
        company_name_1     TEXT,
        approved_date      TEXT,
        approved_month     TEXT,
        revision_reason    TEXT,
        gross_amount       REAL,
        discount_percent   REAL,
        discount_amount    REAL,
        revision_requested INTEGER NOT NULL DEFAULT 0,
        review_note        TEXT,
        reviewed_by        TEXT REFERENCES employees(employee_id),
        reviewed_at        TEXT,
        created_by         TEXT REFERENCES employees(employee_id),
        created_at         TEXT NOT NULL,
        UNIQUE (quotation_number, revision_no)
    )""",
    """
    CREATE TABLE IF NOT EXISTS followup_logs (
        followup_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id              INTEGER NOT NULL REFERENCES leads_master(lead_id),
        quotation_id         TEXT REFERENCES quotations_master(quotation_id),
        employee_id          TEXT NOT NULL REFERENCES employees(employee_id),
        followup_sequence_no INTEGER NOT NULL DEFAULT 1,
        followup_status      TEXT NOT NULL,
        cancel_category      TEXT,
        scheduled_call_time  TEXT,
        notes                TEXT NOT NULL,
        logged_at            TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id            TEXT PRIMARY KEY,
        lead_id             INTEGER NOT NULL UNIQUE REFERENCES leads_master(lead_id),
        client_id           TEXT NOT NULL REFERENCES customers(client_id),
        quotation_id        TEXT REFERENCES quotations_master(quotation_id),
        purchase_order_no   TEXT,
        pi_amount           REAL NOT NULL DEFAULT 0,
        order_value         REAL,
        next_collection_date TEXT,
        collection_remarks  TEXT,
        payment_status      TEXT NOT NULL DEFAULT 'Pending',
        measurement_status  TEXT NOT NULL DEFAULT 'Pending',
        drawing_status      TEXT NOT NULL DEFAULT 'Pending',
        production_status   TEXT NOT NULL DEFAULT 'Not Started',
        dispatch_status     TEXT NOT NULL DEFAULT 'Pending',
        remarks             TEXT,
        created_by          TEXT REFERENCES employees(employee_id),
        created_at          TEXT NOT NULL,
        updated_at          TEXT
    )""",
    """
    CREATE TABLE IF NOT EXISTS payments (
        payment_id   TEXT PRIMARY KEY,
        order_id     TEXT NOT NULL REFERENCES orders(order_id),
        amount       REAL NOT NULL,
        paid_on      TEXT NOT NULL,
        mode         TEXT NOT NULL,
        reference    TEXT,
        notes        TEXT,
        recorded_by  TEXT REFERENCES employees(employee_id),
        created_at   TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS call_snoozes (
        snooze_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id        INTEGER NOT NULL REFERENCES leads_master(lead_id),
        employee_id    TEXT NOT NULL REFERENCES employees(employee_id),
        scheduled_for  TEXT NOT NULL,
        snoozed_at     TEXT NOT NULL,
        snoozed_until  TEXT NOT NULL,
        minutes        INTEGER NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS targets (
        target_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id  TEXT NOT NULL REFERENCES employees(employee_id),
        month        TEXT NOT NULL,
        metric       TEXT NOT NULL,
        value        REAL NOT NULL,
        set_by       TEXT REFERENCES employees(employee_id),
        set_at       TEXT NOT NULL,
        UNIQUE (employee_id, month, metric)
    )""",
    """
    CREATE TABLE IF NOT EXISTS payment_followups (
        followup_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id      TEXT NOT NULL REFERENCES orders(order_id),
        milestone     TEXT NOT NULL,
        logged_by     TEXT REFERENCES employees(employee_id),
        outcome       TEXT NOT NULL,
        promised_date TEXT,
        delay_reason  TEXT,
        notes         TEXT,
        next_call_at  TEXT,
        logged_at     TEXT NOT NULL
    )""",
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        at          TEXT NOT NULL,
        actor_id    TEXT,
        action      TEXT NOT NULL,
        table_name  TEXT,
        record_id   TEXT,
        old_values  TEXT,
        new_values  TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_leads_client ON leads_master(client_id)",
    "CREATE INDEX IF NOT EXISTS idx_leads_owner ON leads_master(followup_owner_id)",
    "CREATE INDEX IF NOT EXISTS idx_leads_qs ON leads_master(claimed_qs_id)",
    "CREATE INDEX IF NOT EXISTS idx_quotes_lead ON quotations_master(lead_id)",
    "CREATE INDEX IF NOT EXISTS idx_logs_lead ON followup_logs(lead_id)",
    "CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone_number)",
    "CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at)",
    "CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_snoozes_lead ON call_snoozes(lead_id)",
    "CREATE INDEX IF NOT EXISTS idx_payfu_order ON payment_followups(order_id)",
]

# Columns added after the first release. init_schema adds any that are missing,
# so an existing database is upgraded in place without losing data.
MIGRATION_COLUMNS = [
    ("quotations_master", "gross_amount", "REAL"),
    ("quotations_master", "discount_percent", "REAL"),
    ("quotations_master", "discount_amount", "REAL"),
    ("orders", "order_value", "REAL"),
    ("orders", "next_collection_date", "TEXT"),
    ("orders", "collection_remarks", "TEXT"),
    ("quotations_master", "revision_requested", "INTEGER NOT NULL DEFAULT 0"),
    ("quotations_master", "review_note", "TEXT"),
    ("quotations_master", "reviewed_by", "TEXT"),
    ("quotations_master", "reviewed_at", "TEXT"),
    ("leads_master", "customer_responded", "TEXT"),
    ("employees", "is_team_lead", "INTEGER"),
    ("employees", "can_handle_po", "INTEGER"),
    ("orders", "po_date", "TEXT"),
    ("orders", "po_amount", "REAL"),
    ("orders", "pi_number", "TEXT"),
    ("orders", "delivery_days", "INTEGER"),
    ("orders", "po_checks", "TEXT"),
    ("orders", "po_verified_at", "TEXT"),
    ("orders", "po_verified_by", "TEXT"),
    ("orders", "expected_delivery_date", "TEXT"),
    ("orders", "dispatched_at", "TEXT"),
    ("orders", "installed_at", "TEXT"),
    ("orders", "po_owner_id", "TEXT"),
    ("orders", "plan_advance", "REAL"),
    ("orders", "plan_dispatch", "REAL"),
    ("orders", "plan_install", "REAL"),
    ("orders", "po_claimed_at", "TEXT"),
]

# Value renames applied on start-up (safe to run repeatedly).
DATA_MIGRATIONS = [
    """UPDATE leads_master SET final_status = CASE final_status
         WHEN 'Won' THEN 'Done' WHEN 'Lost' THEN 'Cancled' WHEN 'New' THEN 'Pending'
         WHEN 'Not Responded' THEN 'Not Responed' ELSE final_status END
       WHERE final_status IN ('Won', 'Lost', 'New', 'Not Responded')""",
    """UPDATE followup_logs SET followup_status = CASE followup_status
         WHEN 'Won' THEN 'Done' WHEN 'Lost' THEN 'Cancled' WHEN 'New' THEN 'Pending'
         WHEN 'Not Responded' THEN 'Not Responed' ELSE followup_status END
       WHERE followup_status IN ('Won', 'Lost', 'New', 'Not Responded')""",
    "UPDATE leads_master SET type_of_client = 'Buy' WHERE type_of_client = 'New Buy'",
    # Dolly leads the quotation team by default (admins can change it in Users).
    "UPDATE employees SET is_team_lead = CASE WHEN lower(full_name) = 'dolly' AND role = 'QS' THEN 1 ELSE 0 END WHERE is_team_lead IS NULL",
    # PO access now comes only from the PO role; clear the old per-person switch.
    "UPDATE employees SET can_handle_po = 0 WHERE can_handle_po IS NULL OR can_handle_po = 1",
]

# Tables the generic insert/update/delete methods are allowed to touch.
WRITABLE_TABLES = {
    "employees", "products", "customers", "leads_master",
    "quotations_master", "followup_logs", "orders", "payments", "call_snoozes", "targets", "payment_followups",
}
