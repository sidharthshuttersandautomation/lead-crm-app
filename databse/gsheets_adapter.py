import streamlit as st
import pandas as pd
from typing import Dict
from database.base_adapter import BaseDatabaseAdapter
from config.sheet_mappings import TABLE_SCHEMAS

# Default Users seeded for authentication & portal demo
_DEFAULT_USERS = pd.DataFrame(
    [
        {"user_id": "U101", "full_name": "Albert Singh", "email": "albert@company.com", "role": "LGE", "created_at": "2026-10-01"},
        {"user_id": "U102", "full_name": "Pooja", "email": "pooja@company.com", "role": "QS", "created_at": "2026-10-01"},
        {"user_id": "U103", "full_name": "Anjali", "email": "anjali@company.com", "role": "QS", "created_at": "2026-10-01"},
        {"user_id": "U104", "full_name": "Dolly", "email": "dolly@company.com", "role": "QS", "created_at": "2026-10-01"},
        {"user_id": "U105", "full_name": "Jeevan Sharma", "email": "jeevan@company.com", "role": "SAM", "created_at": "2026-10-01"},
        {"user_id": "U106", "full_name": "Jitendra Sir", "email": "jitendra@company.com", "role": "SAM", "created_at": "2026-10-01"},
        {"user_id": "U107", "full_name": "Deepak Sir", "email": "deepak@company.com", "role": "SAM", "created_at": "2026-10-01"},
        {"user_id": "U108", "full_name": "Admin", "email": "admin@company.com", "role": "ADMIN", "created_at": "2026-10-01"},
    ]
)

_IN_MEMORY_DB: Dict[str, pd.DataFrame] = {
    table: pd.DataFrame(columns=cols) for table, cols in TABLE_SCHEMAS.items()
}
_IN_MEMORY_DB["users"] = _DEFAULT_USERS


class GSheetsAdapter(BaseDatabaseAdapter):
    """Google Sheets connection implementation with session cache fallback."""

    def __init__(self):
        self.use_gsheets = False
        try:
            if "gsheets" in st.secrets:
                from streamlit_gsheets import GSheetsConnection
                self.conn = st.connection("gsheets", type=GSheetsConnection)
                self.use_gsheets = True
        except Exception:
            self.use_gsheets = False

    def fetch_all(self, table_name: str) -> pd.DataFrame:
        if self.use_gsheets:
            try:
                df = self.conn.read(worksheet=table_name, ttl="0s")
                return df.fillna("")
            except Exception:
                pass

        if table_name not in st.session_state:
            st.session_state[table_name] = _IN_MEMORY_DB.get(
                table_name, pd.DataFrame(columns=TABLE_SCHEMAS.get(table_name, []))
            )
        return st.session_state[table_name].copy()

    def insert_row(self, table_name: str, record: dict) -> bool:
        schema = TABLE_SCHEMAS.get(table_name, list(record.keys()))
        formatted_record = {col: record.get(col, "") for col in schema}

        if self.use_gsheets:
            try:
                df_existing = self.fetch_all(table_name)
                df_updated = pd.concat(
                    [df_existing, pd.DataFrame([formatted_record])], ignore_index=True
                )
                self.conn.update(worksheet=table_name, data=df_updated)
            except Exception as e:
                st.error(f"Google Sheets write error: {e}")

        df_current = self.fetch_all(table_name)
        df_updated = pd.concat(
            [df_current, pd.DataFrame([formatted_record])], ignore_index=True
        )
        st.session_state[table_name] = df_updated
        return True

    def update_row(
        self, table_name: str, key_col: str, key_val: str, record: dict
    ) -> bool:
        df = self.fetch_all(table_name)
        if df.empty or key_col not in df.columns:
            return False

        mask = df[key_col].astype(str) == str(key_val)
        if not mask.any():
            return False

        idx = df[mask].index[0]
        for col, val in record.items():
            if col in df.columns:
                df.at[idx, col] = val

        if self.use_gsheets:
            try:
                self.conn.update(worksheet=table_name, data=df)
            except Exception as e:
                st.error(f"Google Sheets update error: {e}")

        st.session_state[table_name] = df
        return True

    def delete_row(self, table_name: str, key_col: str, key_val: str) -> bool:
        df = self.fetch_all(table_name)
        if df.empty or key_col not in df.columns:
            return False

        df_filtered = df[df[key_col].astype(str) != str(key_val)].reset_index(drop=True)

        if self.use_gsheets:
            try:
                self.conn.update(worksheet=table_name, data=df_filtered)
            except Exception as e:
                st.error(f"Google Sheets delete error: {e}")

        st.session_state[table_name] = df_filtered
        return True