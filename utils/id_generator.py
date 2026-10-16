"""utils/id_generator.py - Business IDs, generated from the highest existing value."""
import datetime

from config.settings import CLIENT_ID_PREFIX
from utils.time_utils import financial_year


def generate_client_id(db_adapter, client_type: str, date_obj: datetime.date) -> str:
    """e.g. BID-Oct-26-007 (New Buy) or SID-Oct-26-002 (Service)."""
    prefix = CLIENT_ID_PREFIX.get(str(client_type).strip(), "BID")
    return db_adapter.next_client_id(prefix, date_obj.strftime("%b-%y"))


def generate_quotation_number(db_adapter, date_obj: datetime.date, company: str = None) -> str:
    """e.g. SSAPL/2026-27/842 or SSGI/2026-27/574. Revisions keep the number and add R1, R2..."""
    return db_adapter.next_quotation_number(financial_year(date_obj), company)
