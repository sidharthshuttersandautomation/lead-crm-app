"""
database/base_adapter.py - Contract every database engine must implement.

Views only talk to this interface, so moving from SQLite to Supabase/Postgres
means writing one new adapter class, not touching the screens.

Write methods return a truthy value on success and False/None on failure; the
reason is kept in `self.last_error` so the screen can show it.
"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseDatabaseAdapter(ABC):
    def __init__(self):
        self.actor_id = None
        self.last_error = ""

    def set_actor(self, actor_id):
        """Employee ID recorded in the audit trail for every write."""
        self.actor_id = actor_id

    # ---------- setup
    @abstractmethod
    def init_schema(self) -> None: ...

    # ---------- generic reads / writes
    @abstractmethod
    def fetch_all(self, table_name: str) -> pd.DataFrame: ...

    @abstractmethod
    def insert_row(self, table_name: str, row_dict: dict):
        """Insert a record. Returns the new primary key, or None on failure."""

    @abstractmethod
    def update_row(self, table_name: str, key_column: str, key_value, updated_dict: dict) -> bool: ...

    @abstractmethod
    def delete_row(self, table_name: str, key_column: str, key_value) -> bool: ...

    # ---------- workflow operations that must be atomic
    @abstractmethod
    def claim_lead(self, lead_id: int, qs_id: str) -> bool:
        """Claim an unassigned lead. False if someone else already claimed it."""

    # ---------- ID generators (based on the highest existing value, not row counts)
    @abstractmethod
    def next_client_id(self, prefix: str, month_label: str) -> str: ...

    @abstractmethod
    def next_quotation_number(self, fy_label: str, prefix: str = None) -> str: ...

    @abstractmethod
    def next_quotation_id(self) -> str: ...

    @abstractmethod
    def next_employee_id(self) -> str: ...

    @abstractmethod
    def next_order_id(self) -> str: ...

    @abstractmethod
    def next_payment_id(self) -> str: ...

    # ---------- auth & audit
    @abstractmethod
    def get_login_record(self, identifier: str):
        """Employee row including password_hash, matched by email, ID or username."""

    @abstractmethod
    def log_event(self, action: str, table_name=None, record_id=None, old_values=None, new_values=None) -> None: ...

    @abstractmethod
    def count_rows(self, table_name: str) -> int: ...

    def run_data_migrations(self) -> None:
        """Re-apply idempotent data fixes (optional for engines that don't need it)."""

    # ---------- bulk operations (Excel import)
    @abstractmethod
    def bulk_insert(self, table_name: str, rows: list) -> int:
        """Insert many rows in one transaction (all or nothing). Returns rows inserted."""

    @abstractmethod
    def clear_lead_data(self) -> dict:
        """Delete all customers, leads, quotations, calls, orders and payments. Keeps users and products."""
