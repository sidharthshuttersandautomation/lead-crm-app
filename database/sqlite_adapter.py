"""
SQLite Database Adapter Implementation.
"""
import sqlite3
import pandas as pd
from database.base_adapter import BaseDatabaseAdapter

DB_PATH = "crm_database.db"

class SQLiteAdapter(BaseDatabaseAdapter):
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Creates tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Users Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT,
                full_name TEXT,
                email TEXT
            )
            """)

            # Seed default users if empty
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                default_users = [
                    ("U101", "admin", "admin123", "ADMIN", "System Administrator", "admin@sidharth.com"),
                    ("U102", "albert", "albert123", "LGE", "Albert Singh", "albert@sidharth.com"),
                    ("U103", "pooja", "pooja123", "QS", "Pooja", "pooja@sidharth.com"),
                    ("U104", "dolly", "dolly123", "QS", "Dolly", "dolly@sidharth.com"),
                    ("U105", "jeevan", "jeevan123", "SAM", "Jeevan Sharma", "jeevan@sidharth.com"),
                    ("U106", "ops", "ops123", "OPERATIONS", "Operations Specialist", "ops@sidharth.com")
                ]
                cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", default_users)

            # Leads Data Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads_data (
                "Sr. No" INTEGER PRIMARY KEY,
                "Client ID" TEXT,
                "Date Stamp" TEXT,
                "Month" TEXT,
                "Date" TEXT,
                "Client Name" TEXT,
                "Company Name" TEXT,
                "Contact No." TEXT,
                "Email" TEXT,
                "Product" TEXT,
                "Quantity" INTEGER,
                "Address" TEXT,
                "City" TEXT,
                "State" TEXT,
                "Source" TEXT,
                "Assigned Salesperson" TEXT,
                "Type of client" TEXT,
                "Final Status" TEXT,
                "Quotation Status" TEXT,
                "Leads Handle By" TEXT,
                "Quotation Sent By" TEXT,
                "Customer Status" TEXT,
                "Customer Responded" TEXT,
                "Remarks" TEXT,
                "Product Status" TEXT,
                "Claimed By QS" TEXT
            )
            """)

            # Quotation Sheet Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotation_sheet (
                "Quotation Number" TEXT PRIMARY KEY,
                "Client ID" TEXT,
                "Client Name" TEXT,
                "Company Name" TEXT,
                "Contact Number" TEXT,
                "City" TEXT,
                "Product" TEXT,
                "Quantity" INTEGER,
                "Subtotal Amount" REAL,
                "GST Amount" REAL,
                "Grand Total" REAL,
                "Assigned Salesperson" TEXT,
                "Prepared By QS" TEXT,
                "Quotation Status" TEXT,
                "Revision Count" INTEGER,
                "Request Timestamp" TEXT,
                "Completion Timestamp" TEXT,
                "Is After Cutoff" TEXT,
                "Remarks" TEXT
            )
            """)

            # Followup Tracker Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS followup_tracker (
                "Followup ID" TEXT PRIMARY KEY,
                "Client ID" TEXT,
                "Client Name" TEXT,
                "Contact Number" TEXT,
                "City" TEXT,
                "Product" TEXT,
                "Last Quoted Price" REAL,
                "Assigned Salesperson" TEXT,
                "Follow-up Status" TEXT,
                "Completed Follow-ups Count" INTEGER,
                "Remarks History" TEXT,
                "Next Follow-up Date" TEXT,
                "Next Follow-up Time" TEXT,
                "Cancel Category" TEXT,
                "Last Followed By" TEXT
            )
            """)

            # Process Order Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS process_order (
                "Order ID" TEXT PRIMARY KEY,
                "Client ID" TEXT,
                "Quotation Number" TEXT,
                "Client Name" TEXT,
                "Company Name" TEXT,
                "Product" TEXT,
                "PO Number" TEXT,
                "PI Number" TEXT,
                "Advance Payment Status" TEXT,
                "Measurement Status" TEXT,
                "Drawing Status" TEXT,
                "Production Status" TEXT,
                "Dispatch Status" TEXT,
                "Invoice Number" TEXT,
                "Final Remarks" TEXT
            )
            """)
            conn.commit()

    def fetch_all(self, table_name: str) -> pd.DataFrame:
        with self._get_connection() as conn:
            try:
                return pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
            except Exception:
                return pd.DataFrame()

    def insert_row(self, table_name: str, row_dict: dict) -> bool:
        with self._get_connection() as conn:
            try:
                df = pd.DataFrame([row_dict])
                df.to_sql(table_name, conn, if_exists="append", index=False)
                return True
            except Exception as e:
                print(f"SQLite insert error on {table_name}: {e}")
                return False

    def update_row(self, table_name: str, key_column: str, key_value: str, updated_dict: dict) -> bool:
        with self._get_connection() as conn:
            try:
                set_clause = ", ".join([f'"{k}" = ?' for k in updated_dict.keys()])
                values = list(updated_dict.values()) + [str(key_value)]
                sql = f'UPDATE "{table_name}" SET {set_clause} WHERE "{key_column}" = ?'
                conn.execute(sql, values)
                conn.commit()
                return True
            except Exception as e:
                print(f"SQLite update error on {table_name}: {e}")
                return False

    def delete_row(self, table_name: str, key_column: str, key_value: str) -> bool:
        with self._get_connection() as conn:
            try:
                sql = f'DELETE FROM "{table_name}" WHERE "{key_column}" = ?'
                conn.execute(sql, [str(key_value)])
                conn.commit()
                return True
            except Exception as e:
                print(f"SQLite delete error on {table_name}: {e}")
                return False