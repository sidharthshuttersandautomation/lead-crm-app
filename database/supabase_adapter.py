import pandas as pd
from database.base_adapter import BaseDatabaseAdapter

class SupabaseAdapter(BaseDatabaseAdapter):
    """Supabase Adapter placeholder for post-trial migration."""

    def __init__(self, supabase_url: str = "", supabase_key: str = ""):
        self.url = supabase_url
        self.key = supabase_key

    def fetch_all(self, table_name: str) -> pd.DataFrame:
        raise NotImplementedError("Supabase adapter will be enabled post GSheets trial.")

    def insert_row(self, table_name: str, record: dict) -> bool:
        return True

    def update_row(
        self, table_name: str, key_col: str, key_val: str, record: dict
    ) -> bool:
        return True

    def delete_row(self, table_name: str, key_col: str, key_val: str) -> bool:
        return True