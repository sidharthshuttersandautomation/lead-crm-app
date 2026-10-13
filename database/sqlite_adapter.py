"""
Relational SQLite Adapter for Sidharth Shutter CRM.
"""
import sqlite3
import pandas as pd
from database.base_adapter import BaseDatabaseAdapter

DB_PATH = "crm_database.db"

class SQLiteAdapter(BaseDatabaseAdapter):
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def fetch_all(self, table_name: str) -> pd.DataFrame:
        with self._get_connection() as conn:
            try:
                if table_name == "leads_master":
                    query = """
                    SELECT 
                        lm.lead_id,
                        c.client_id,
                        c.client_name,
                        c.company_name,
                        c.phone_number,
                        c.email,
                        c.city,
                        c.address,
                        p.product_name AS product,
                        lm.quantity AS qty,
                        lm.source,
                        lm.final_status,
                        lm.quotation_status,
                        emp_lge.full_name AS leads_handled_by,
                        emp_sam.full_name AS assigned_salesperson,
                        emp_qs.full_name AS claimed_qs_name,
                        lm.claimed_qs_id,
                        lm.ingestion_date
                    FROM leads_master lm
                    JOIN customers c ON lm.client_id = c.client_id
                    JOIN products p ON lm.product_id = p.product_id
                    LEFT JOIN employees emp_lge ON lm.handled_by_lge_id = emp_lge.employee_id
                    LEFT JOIN employees emp_sam ON lm.assigned_sam_id = emp_sam.employee_id
                    LEFT JOIN employees emp_qs ON lm.claimed_qs_id = emp_qs.employee_id
                    """
                    return pd.read_sql_query(query, conn)

                elif table_name == "quotations_master":
                    query = """
                    SELECT 
                        qm.quotation_id,
                        qm.client_id,
                        qm.quotation_number,
                        c.client_name,
                        c.company_name,
                        c.phone_number,
                        p.product_name AS product,
                        qm.qut_amount,
                        qm.quotation_status,
                        qm.revised,
                        emp_qs.full_name AS quotation_shared_by,
                        qm.created_timestamp
                    FROM quotations_master qm
                    JOIN customers c ON qm.client_id = c.client_id
                    JOIN leads_master lm ON qm.lead_id = lm.lead_id
                    JOIN products p ON lm.product_id = p.product_id
                    LEFT JOIN employees emp_qs ON qm.claimed_qs_id = emp_qs.employee_id
                    """
                    return pd.read_sql_query(query, conn)

                elif table_name == "employees":
                    return pd.read_sql_query("SELECT employee_id, full_name, email, role, is_active FROM employees", conn)

                elif table_name == "products":
                    return pd.read_sql_query("SELECT * FROM products", conn)

                elif table_name == "followup_logs":
                    return pd.read_sql_query("SELECT * FROM followup_logs", conn)

                else:
                    return pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)

            except Exception as e:
                print(f"Error fetching {table_name}: {e}")
                return pd.DataFrame()

    def insert_row(self, table_name: str, row_dict: dict) -> bool:
        with self._get_connection() as conn:
            try:
                df = pd.DataFrame([row_dict])
                df.to_sql(table_name, conn, if_exists="append", index=False)
                return True
            except Exception as e:
                print(f"Insert error on {table_name}: {e}")
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
                print(f"Update error on {table_name}: {e}")
                return False

    def delete_row(self, table_name: str, key_column: str, key_value: str) -> bool:
        with self._get_connection() as conn:
            try:
                sql = f'DELETE FROM "{table_name}" WHERE "{key_column}" = ?'
                conn.execute(sql, [str(key_value)])
                conn.commit()
                return True
            except Exception as e:
                print(f"Delete error on {table_name}: {e}")
                return False