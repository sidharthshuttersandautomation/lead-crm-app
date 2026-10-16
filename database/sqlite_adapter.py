"""
database/sqlite_adapter.py - SQLite implementation of the CRM database contract.
"""
import json
import os
import re
import sqlite3
from contextlib import contextmanager

import pandas as pd

from config.settings import QUOTE_COMPANIES, QUOTE_NUMBER_PREFIX, QUOTE_NUMBER_START
from database.base_adapter import BaseDatabaseAdapter
from database.schema import DATA_MIGRATIONS, DDL, MIGRATION_COLUMNS, SCHEMA_VERSION, WRITABLE_TABLES
from utils.time_utils import now_str

PRIMARY_KEYS = {
    "employees": "employee_id",
    "products": "product_id",
    "customers": "client_id",
    "leads_master": "lead_id",
    "quotations_master": "quotation_id",
    "followup_logs": "followup_id",
    "orders": "order_id",
    "payments": "payment_id",
    "call_snoozes": "snooze_id",
    "targets": "target_id",
    "payment_followups": "followup_id",
    "po_revisions": "rev_id",
}
SENSITIVE_COLUMNS = {"password_hash"}

# Read views: joined, human-friendly shapes used by the screens.
READ_QUERIES = {
    "leads_master": """
        SELECT lm.lead_id, lm.client_id, c.client_name, c.company_name, c.phone_number,
               c.email, c.address, c.city, c.state, c.is_key_account,
               lm.product_id, p.product_name AS product, lm.quantity AS qty,
               lm.source, lm.type_of_client, lm.customer_responded, lm.final_status, lm.quotation_status,
               lm.priority, lm.remarks, lm.lost_reason,
               lm.handled_by_lge_id, lge.full_name AS leads_handled_by,
               lm.assigned_sam_id, sam.full_name AS assigned_salesperson,
               lm.claimed_qs_id, qs.full_name AS claimed_qs_name,
               lm.followup_owner_id, own.full_name AS followup_owner_name,
               lm.next_followup_at, lm.ingestion_date, lm.ingested_at,
               lm.is_after_cutoff, lm.sla_due_date, lm.claimed_at,
               lm.quote_sent_at, lm.closed_at, lm.updated_at
        FROM leads_master lm
        JOIN customers c ON lm.client_id = c.client_id
        JOIN products p ON lm.product_id = p.product_id
        LEFT JOIN employees lge ON lm.handled_by_lge_id = lge.employee_id
        LEFT JOIN employees sam ON lm.assigned_sam_id = sam.employee_id
        LEFT JOIN employees qs ON lm.claimed_qs_id = qs.employee_id
        LEFT JOIN employees own ON lm.followup_owner_id = own.employee_id
        ORDER BY lm.lead_id
    """,
    "quotations_master": """
        SELECT qm.quotation_id, qm.lead_id, qm.client_id, qm.quotation_number,
               qm.revision_no,
               qm.quotation_number || CASE WHEN qm.revision_no > 0
                    THEN ' R' || qm.revision_no ELSE '' END AS quotation_ref,
               c.client_name, c.company_name, c.phone_number,
               p.product_name AS product, lm.quantity AS qty,
               qm.qut_amount, qm.quotation_status, qm.follow_up_required,
               qm.claimed_qs_id, qs.full_name AS claimed_qs_name,
               qm.shared_by_id, sh.full_name AS quotation_shared_by,
               qm.approved_by_id, ap.full_name AS approved_by,
               lm.assigned_sam_id, sam.full_name AS assigned_salesperson,
               lm.final_status, lm.priority,
               qm.folder_link, qm.company_name_1, qm.approved_date, qm.approved_month,
               qm.revision_reason,
               COALESCE(qm.gross_amount, qm.qut_amount) AS gross_amount,
               COALESCE(qm.discount_percent, 0) AS discount_percent,
               COALESCE(qm.discount_amount, 0) AS discount_amount,
               COALESCE(qm.revision_requested, 0) AS revision_requested, qm.review_note,
               qm.reviewed_by, rv.full_name AS reviewed_by_name, qm.reviewed_at,
               qm.created_by, qm.created_at
        FROM quotations_master qm
        JOIN leads_master lm ON qm.lead_id = lm.lead_id
        JOIN customers c ON qm.client_id = c.client_id
        JOIN products p ON lm.product_id = p.product_id
        LEFT JOIN employees qs ON qm.claimed_qs_id = qs.employee_id
        LEFT JOIN employees sh ON qm.shared_by_id = sh.employee_id
        LEFT JOIN employees ap ON qm.approved_by_id = ap.employee_id
        LEFT JOIN employees sam ON lm.assigned_sam_id = sam.employee_id
        LEFT JOIN employees rv ON qm.reviewed_by = rv.employee_id
        ORDER BY qm.created_at
    """,
    "followup_logs": """
        SELECT fl.followup_id, fl.lead_id, lm.client_id, c.client_name,
               fl.quotation_id, fl.employee_id, e.full_name AS employee_name,
               fl.followup_sequence_no, fl.followup_status, fl.cancel_category,
               fl.scheduled_call_time, fl.notes, fl.logged_at
        FROM followup_logs fl
        JOIN leads_master lm ON fl.lead_id = lm.lead_id
        JOIN customers c ON lm.client_id = c.client_id
        LEFT JOIN employees e ON fl.employee_id = e.employee_id
        ORDER BY fl.logged_at, fl.followup_id
    """,
    "orders": """
        SELECT o.order_id, o.lead_id, o.client_id, c.client_name, c.company_name,
               c.phone_number, c.city,
               p.product_name AS product, lm.quantity AS qty,
               lm.assigned_sam_id, sam.full_name AS sales_person,
               qm.quotation_number || CASE WHEN qm.revision_no > 0
                    THEN ' R' || qm.revision_no ELSE '' END AS quotation_ref,
               qm.qut_amount, o.purchase_order_no, o.pi_amount,
               COALESCE(o.order_value, NULLIF(o.pi_amount, 0), qm.qut_amount, 0) AS order_value,
               COALESCE(pay.received, 0) AS received,
               COALESCE(o.order_value, NULLIF(o.pi_amount, 0), qm.qut_amount, 0)
                   - COALESCE(pay.received, 0) AS balance,
               COALESCE(pay.payments_count, 0) AS payments_count, pay.last_payment_on,
               o.payment_status, o.measurement_status, o.drawing_status,
               o.production_status, o.dispatch_status, o.remarks,
               o.next_collection_date, o.collection_remarks,
               o.po_date, o.po_amount, o.pi_number, o.delivery_days, o.po_checks, o.po_verified_at,
               o.po_verified_by, o.expected_delivery_date, o.dispatched_at, o.installed_at,
               o.po_owner_id, po.full_name AS po_owner_name, c.email,
               COALESCE(o.plan_advance, 50) AS plan_advance, COALESCE(o.plan_dispatch, 40) AS plan_dispatch,
               COALESCE(o.plan_install, 10) AS plan_install, o.po_claimed_at, o.po_status,
               (SELECT COUNT(*) FROM po_revisions r WHERE r.order_id = o.order_id AND r.result = 'Sent for revision') AS po_revisions,
               o.created_by, o.created_at, o.updated_at
        FROM orders o
        JOIN leads_master lm ON o.lead_id = lm.lead_id
        JOIN customers c ON o.client_id = c.client_id
        JOIN products p ON lm.product_id = p.product_id
        LEFT JOIN employees sam ON lm.assigned_sam_id = sam.employee_id
        LEFT JOIN quotations_master qm ON o.quotation_id = qm.quotation_id
        LEFT JOIN employees po ON o.po_owner_id = po.employee_id
        LEFT JOIN (SELECT order_id, SUM(amount) AS received, COUNT(*) AS payments_count,
                          MAX(paid_on) AS last_payment_on
                   FROM payments GROUP BY order_id) pay ON pay.order_id = o.order_id
        ORDER BY o.created_at
    """,
    "payments": """
        SELECT pm.payment_id, pm.order_id, o.client_id, c.client_name, c.company_name,
               pm.amount, pm.paid_on, pm.mode, pm.reference, pm.notes,
               pm.recorded_by, e.full_name AS recorded_by_name, pm.created_at
        FROM payments pm
        JOIN orders o ON pm.order_id = o.order_id
        JOIN customers c ON o.client_id = c.client_id
        LEFT JOIN employees e ON pm.recorded_by = e.employee_id
        ORDER BY pm.paid_on, pm.created_at
    """,
    "call_snoozes": """
        SELECT cs.snooze_id, cs.lead_id, lm.client_id, c.client_name, cs.employee_id,
               e.full_name AS employee_name, cs.scheduled_for, cs.snoozed_at, cs.snoozed_until, cs.minutes
        FROM call_snoozes cs
        JOIN leads_master lm ON cs.lead_id = lm.lead_id
        JOIN customers c ON lm.client_id = c.client_id
        LEFT JOIN employees e ON cs.employee_id = e.employee_id
        ORDER BY cs.snoozed_at
    """,
    "po_revisions": """
        SELECT r.*, e.full_name AS checked_by_name, o.client_id
        FROM po_revisions r JOIN orders o ON r.order_id = o.order_id
        LEFT JOIN employees e ON r.checked_by = e.employee_id
        ORDER BY r.order_id, r.round_no
    """,
    "employees": """
        SELECT employee_id, full_name, email, role, is_active, COALESCE(is_team_lead, 0) AS is_team_lead,
               COALESCE(can_handle_po, 0) AS can_handle_po, created_at
        FROM employees ORDER BY employee_id
    """,
    "targets": """
        SELECT t.*, e.full_name AS employee_name FROM targets t
        LEFT JOIN employees e ON t.employee_id = e.employee_id ORDER BY t.month DESC
    """,
    "payment_followups": """
        SELECT pf.*, e.full_name AS logged_by_name, c.client_name, o.client_id
        FROM payment_followups pf
        JOIN orders o ON pf.order_id = o.order_id
        JOIN customers c ON o.client_id = c.client_id
        LEFT JOIN employees e ON pf.logged_by = e.employee_id
        ORDER BY pf.logged_at
    """,
    "products": "SELECT * FROM products ORDER BY product_name",
    "customers": "SELECT * FROM customers ORDER BY created_at",
    "audit_log": "SELECT * FROM audit_log ORDER BY audit_id DESC",
}


def _max_suffix(values, pattern):
    """Highest integer captured by `pattern` across `values` (0 if none)."""
    best = 0
    regex = re.compile(pattern)
    for v in values:
        m = regex.search(str(v))
        if m:
            best = max(best, int(m.group(1)))
    return best


class SQLiteAdapter(BaseDatabaseAdapter):
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        folder = os.path.dirname(db_path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    # ------------------------------------------------------------------ plumbing
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _columns(self, conn, table_name):
        return {r["name"] for r in conn.execute(f'PRAGMA table_info("{table_name}")')}

    @staticmethod
    def _clean_for_audit(values: dict) -> dict:
        return {k: ("***" if k in SENSITIVE_COLUMNS else v) for k, v in (values or {}).items()}

    def init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            for stmt in DDL:
                conn.execute(stmt)
            for table, column, col_type in MIGRATION_COLUMNS:
                if column not in self._columns(conn, table):
                    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}')
            for stmt in DATA_MIGRATIONS:
                conn.execute(stmt)
            conn.execute(
                "INSERT OR REPLACE INTO schema_info (key, value) VALUES ('version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def run_data_migrations(self) -> None:
        with self._conn() as conn:
            for stmt in DATA_MIGRATIONS:
                conn.execute(stmt)

    def count_rows(self, table_name: str) -> int:
        if table_name not in WRITABLE_TABLES and table_name != "audit_log":
            return 0
        try:
            with self._conn() as conn:
                return conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        except Exception:
            return 0

    # ------------------------------------------------------------------ reads
    def fetch_all(self, table_name: str) -> pd.DataFrame:
        query = READ_QUERIES.get(table_name)
        if query is None:
            self.last_error = f"Unknown table '{table_name}'."
            return pd.DataFrame()
        try:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                return pd.read_sql_query(query, conn)
            finally:
                conn.close()
        except Exception as exc:
            self.last_error = f"Could not read {table_name}: {exc}"
            print(self.last_error)
            return pd.DataFrame()

    # ------------------------------------------------------------------ writes
    def insert_row(self, table_name: str, row_dict: dict):
        self.last_error = ""
        if table_name not in WRITABLE_TABLES:
            self.last_error = f"Table '{table_name}' is not writable."
            return None
        try:
            with self._conn() as conn:
                allowed = self._columns(conn, table_name)
                unknown = set(row_dict) - allowed
                if unknown:
                    raise ValueError(f"Unknown column(s) for {table_name}: {', '.join(sorted(unknown))}")
                cols = list(row_dict.keys())
                col_sql = ", ".join(f'"{c}"' for c in cols)
                sql = f'INSERT INTO "{table_name}" ({col_sql}) VALUES ({", ".join("?" for _ in cols)})'
                cur = conn.execute(sql, [row_dict[c] for c in cols])
                pk = PRIMARY_KEYS.get(table_name)
                new_id = row_dict.get(pk) if pk in row_dict else cur.lastrowid
            self.log_event("INSERT", table_name, new_id, None, self._clean_for_audit(row_dict))
            return new_id
        except sqlite3.IntegrityError as exc:
            self.last_error = f"Save rejected by a data rule ({exc}). Nothing was saved."
        except Exception as exc:
            self.last_error = f"Save failed: {exc}"
        print(self.last_error)
        return None

    def update_row(self, table_name: str, key_column: str, key_value, updated_dict: dict) -> bool:
        self.last_error = ""
        if table_name not in WRITABLE_TABLES:
            self.last_error = f"Table '{table_name}' is not writable."
            return False
        if not updated_dict:
            return True
        try:
            with self._conn() as conn:
                allowed = self._columns(conn, table_name)
                unknown = (set(updated_dict) | {key_column}) - allowed
                if unknown:
                    raise ValueError(f"Unknown column(s) for {table_name}: {', '.join(sorted(unknown))}")
                old = conn.execute(
                    f'SELECT * FROM "{table_name}" WHERE "{key_column}" = ?', (key_value,)
                ).fetchone()
                if old is None:
                    self.last_error = f"Record {key_value} was not found in {table_name}."
                    return False
                set_clause = ", ".join(f'"{k}" = ?' for k in updated_dict)
                conn.execute(
                    f'UPDATE "{table_name}" SET {set_clause} WHERE "{key_column}" = ?',
                    list(updated_dict.values()) + [key_value],
                )
            old = dict(old)
            changed_old = {k: old.get(k) for k in updated_dict if old.get(k) != updated_dict[k]}
            changed_new = {k: updated_dict[k] for k in changed_old}
            if changed_new:
                self.log_event("UPDATE", table_name, key_value,
                               self._clean_for_audit(changed_old), self._clean_for_audit(changed_new))
            return True
        except sqlite3.IntegrityError as exc:
            self.last_error = f"Update rejected by a data rule ({exc}). Nothing was changed."
        except Exception as exc:
            self.last_error = f"Update failed: {exc}"
        print(self.last_error)
        return False

    def delete_row(self, table_name: str, key_column: str, key_value) -> bool:
        self.last_error = ""
        if table_name not in WRITABLE_TABLES:
            self.last_error = f"Table '{table_name}' is not writable."
            return False
        try:
            with self._conn() as conn:
                if key_column not in self._columns(conn, table_name):
                    raise ValueError(f"Unknown column {key_column}")
                old = conn.execute(
                    f'SELECT * FROM "{table_name}" WHERE "{key_column}" = ?', (key_value,)
                ).fetchone()
                cur = conn.execute(f'DELETE FROM "{table_name}" WHERE "{key_column}" = ?', (key_value,))
                if cur.rowcount == 0:
                    self.last_error = f"Record {key_value} was not found in {table_name}."
                    return False
            self.log_event("DELETE", table_name, key_value,
                           self._clean_for_audit(dict(old)) if old else None, None)
            return True
        except sqlite3.IntegrityError:
            self.last_error = "This record is linked to other records and cannot be deleted."
        except Exception as exc:
            self.last_error = f"Delete failed: {exc}"
        print(self.last_error)
        return False

    # ------------------------------------------------------------------ bulk
    def bulk_insert(self, table_name: str, rows: list) -> int:
        self.last_error = ""
        if not rows:
            return 0
        if table_name not in WRITABLE_TABLES:
            self.last_error = f"Table '{table_name}' is not writable."
            return 0
        cols = list(rows[0].keys())
        try:
            with self._conn() as conn:
                unknown = set(cols) - self._columns(conn, table_name)
                if unknown:
                    raise ValueError(f"Unknown column(s) for {table_name}: {', '.join(sorted(unknown))}")
                col_sql = ", ".join(f'"{c}"' for c in cols)
                conn.executemany(f'INSERT INTO "{table_name}" ({col_sql}) VALUES ({", ".join("?" for _ in cols)})',
                                 [[r.get(c) for c in cols] for r in rows])
            self.log_event("BULK_INSERT", table_name, None, None, {"rows": len(rows)})
            return len(rows)
        except Exception as exc:
            self.last_error = f"Bulk insert into {table_name} failed: {exc}"
            print(self.last_error)
            return 0

    def clear_lead_data(self) -> dict:
        counts = {}
        with self._conn() as conn:
            for table in ("targets", "po_revisions", "payment_followups", "call_snoozes", "payments", "orders", "followup_logs", "quotations_master",
                          "leads_master", "customers"):
                counts[table] = conn.execute(f'DELETE FROM "{table}"').rowcount
        self.log_event("CLEAR_LEAD_DATA", None, None, counts, None)
        return counts

    # ------------------------------------------------------------------ workflow
    def claim_lead(self, lead_id: int, qs_id: str) -> bool:
        self.last_error = ""
        ts = now_str()
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    """UPDATE leads_master
                       SET claimed_qs_id = ?, quotation_status = 'Under Process',
                           claimed_at = ?, updated_at = ?
                       WHERE lead_id = ? AND claimed_qs_id IS NULL""",
                    (qs_id, ts, ts, int(lead_id)),
                )
                claimed = cur.rowcount == 1
            if claimed:
                self.log_event("CLAIM", "leads_master", lead_id, {"claimed_qs_id": None},
                               {"claimed_qs_id": qs_id, "quotation_status": "Under Process"})
            else:
                self.last_error = "Another specialist claimed this ticket first."
            return claimed
        except Exception as exc:
            self.last_error = f"Claim failed: {exc}"
            return False

    def claim_followup(self, lead_id: int, emp_id: str) -> bool:
        """Take an unclaimed follow-up. False if someone else took it first."""
        self.last_error = ""
        try:
            with self._conn() as conn:
                cur = conn.execute("UPDATE leads_master SET followup_owner_id = ?, updated_at = ? "
                                   "WHERE lead_id = ? AND followup_owner_id IS NULL", (emp_id, now_str(), int(lead_id)))
                ok = cur.rowcount == 1
            if ok:
                self.log_event("CLAIM_FOLLOWUP", "leads_master", lead_id, {"followup_owner_id": None}, {"followup_owner_id": emp_id})
            else:
                self.last_error = "Someone else took this follow-up first."
            return ok
        except Exception as exc:
            self.last_error = f"Claim failed: {exc}"
            return False

    # ------------------------------------------------------------------ ID generators
    def _scalar_list(self, sql, params=()):
        with self._conn() as conn:
            return [r[0] for r in conn.execute(sql, params).fetchall()]

    def next_client_id(self, prefix: str, month_label: str) -> str:
        base = f"{prefix}-{month_label}-"
        ids = self._scalar_list("SELECT client_id FROM customers WHERE client_id LIKE ?", (base + "%",))
        n = _max_suffix(ids, re.escape(base) + r"(\d+)$") + 1
        return f"{base}{n:03d}"

    def next_quotation_number(self, fy_label: str, prefix: str = None) -> str:
        prefix = prefix or QUOTE_NUMBER_PREFIX
        base = f"{prefix}/{fy_label}/"
        nums = self._scalar_list(
            "SELECT quotation_number FROM quotations_master WHERE quotation_number LIKE ?", (base + "%",))
        current = _max_suffix(nums, re.escape(base) + r"(\d+)$")
        start = QUOTE_COMPANIES.get(prefix, QUOTE_NUMBER_START)
        return f"{base}{max(current + 1, start)}"

    def next_quotation_id(self) -> str:
        ids = self._scalar_list("SELECT quotation_id FROM quotations_master")
        return f"QUO-{_max_suffix(ids, r'QUO-(\d+)$') + 1:04d}"

    def next_employee_id(self) -> str:
        ids = self._scalar_list("SELECT employee_id FROM employees")
        return f"EMP-{max(_max_suffix(ids, r'EMP-(\d+)$') + 1, 101)}"

    def next_order_id(self) -> str:
        ids = self._scalar_list("SELECT order_id FROM orders")
        return f"ORD-{_max_suffix(ids, r'ORD-(\d+)$') + 1:04d}"

    def next_payment_id(self) -> str:
        ids = self._scalar_list("SELECT payment_id FROM payments")
        return f"PAY-{_max_suffix(ids, r'PAY-(\d+)$') + 1:05d}"

    # ------------------------------------------------------------------ auth & audit
    def get_login_record(self, identifier: str):
        ident = str(identifier or "").strip().lower()
        if not ident:
            return None
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM employees
                   WHERE lower(email) = ? OR lower(employee_id) = ?
                      OR lower(substr(email, 1, instr(email, '@') - 1)) = ?""",
                (ident, ident, ident),
            ).fetchall()
        return dict(rows[0]) if len(rows) == 1 else None

    def log_event(self, action, table_name=None, record_id=None, old_values=None, new_values=None) -> None:
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO audit_log (at, actor_id, action, table_name, record_id, old_values, new_values)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (now_str(), self.actor_id, action, table_name,
                     None if record_id is None else str(record_id),
                     json.dumps(old_values, default=str) if old_values else None,
                     json.dumps(new_values, default=str) if new_values else None),
                )
        except Exception as exc:  # auditing must never break the user's action
            print(f"Audit log failed: {exc}")
