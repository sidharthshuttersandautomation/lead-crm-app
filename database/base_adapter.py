"""
Abstract Database Interface Contract for Cross-Engine Swappability.
"""
from abc import ABC, abstractmethod
import pandas as pd

class BaseDatabaseAdapter(ABC):

    @abstractmethod
    def fetch_all(self, table_name: str) -> pd.DataFrame:
        """Fetch all records from a table as a Pandas DataFrame."""
        pass

    @abstractmethod
    def insert_row(self, table_name: str, row_dict: dict) -> bool:
        """Insert a single record into the specified table."""
        pass

    @abstractmethod
    def update_row(self, table_name: str, key_column: str, key_value: str, updated_dict: dict) -> bool:
        """Update an existing record identified by key_column == key_value."""
        pass

    @abstractmethod
    def delete_row(self, table_name: str, key_column: str, key_value: str) -> bool:
        """Delete a record identified by key_column == key_value."""
        pass