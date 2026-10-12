from abc import ABC, abstractmethod
import pandas as pd

class BaseDatabaseAdapter(ABC):
    """Abstract interface to ensure zero UI changes when migrating from GSheets to Supabase."""
    
    @abstractmethod
    def fetch_table(self, table_name: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def insert_row(self, table_name: str, record: dict) -> bool:
        pass

    @abstractmethod
    def update_row(self, table_name: str, key_field: str, key_value: str, updated_record: dict) -> bool:
        pass