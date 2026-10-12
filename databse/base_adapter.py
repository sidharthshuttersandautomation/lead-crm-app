from abc import ABC, abstractmethod
import pandas as pd

class BaseDatabaseAdapter(ABC):
    """Abstract Base Adapter for Database Operations.
    Guarantees seamless zero-UI-change transition from Google Sheets to Supabase.
    """

    @abstractmethod
    def fetch_all(self, table_name: str) -> pd.DataFrame:
        """Fetch all records from a table as a Pandas DataFrame."""
        pass

    @abstractmethod
    def insert_row(self, table_name: str, record: dict) -> bool:
        """Insert a single record into the specified table."""
        pass

    @abstractmethod
    def update_row(
        self, table_name: str, key_col: str, key_val: str, record: dict
    ) -> bool:
        """Update an existing record identified by key_col == key_val."""
        pass

    @abstractmethod
    def delete_row(self, table_name: str, key_col: str, key_val: str) -> bool:
        """Delete a record identified by key_col == key_val."""
        pass