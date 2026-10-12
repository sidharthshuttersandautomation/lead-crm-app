import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from database.base_adapter import BaseDatabaseAdapter
from config.sheet_mappings import LEADS_COLUMNS, QUOTATION_COLUMNS, FOLLOWUP_COLUMNS, PROCESS_ORDER_COLUMNS, USERS_COLUMNS

class GSheetsAdapter(BaseDatabaseAdapter):
    def __init__(self):
        self.sheet_id = "1ajDjxHOqfQw_7qRNvMT4I6q9jujJ6tjPqe6M4kOdoIo"
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.client = self._get_client()

    def _get_client(self):
        try:
            # 1. Check for st.secrets["connections"]["gsheets"] (matches your TOML structure)
            if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
                creds_dict = dict(st.secrets["connections"]["gsheets"])
                creds = Credentials.from_service_account_info(creds_dict, scopes=self.scopes)
                return gspread.authorize(creds)
            
            # 2. Check for st.secrets["gcp_service_account"]
            elif "gcp_service_account" in st.secrets:
                creds = Credentials.from_service_account_info(
                    st.secrets["gcp_service_account"],
                    scopes=self.scopes
                )
                return gspread.authorize(creds)
                
            # 3. Local fallback to service_account.json file
            else:
                creds = Credentials.from_service_account_file(
                    "service_account.json", scopes=self.scopes
                )
                return gspread.authorize(creds)
        except Exception as e:
            st.error(f"Google Sheets Auth Error: {str(e)}")
            return None

    def _get_worksheet(self, table_name: str):
        if not self.client:
            return None
        try:
            spreadsheet = self.client.open_by_key(self.sheet_id)
            return spreadsheet.worksheet(table_name)
        except Exception as e:
            st.error(f"Error accessing worksheet '{table_name}': {str(e)}")
            return None

    def fetch_table(self, table_name: str) -> pd.DataFrame:
        ws = self._get_worksheet(table_name)
        if ws:
            records = ws.get_all_records()
            return pd.DataFrame(records)
        return self._get_fallback_mock_data(table_name)

    def insert_row(self, table_name: str, record: dict) -> bool:
        ws = self._get_worksheet(table_name)
        if ws:
            headers = ws.row_values(1)
            row_to_insert = [record.get(h, "") for h in headers]
            ws.append_row(row_to_insert)
            return True
        return False

    def update_row(self, table_name: str, key_field: str, key_value: str, updated_record: dict) -> bool:
        ws = self._get_worksheet(table_name)
        if ws:
            cell = ws.find(str(key_value))
            if cell:
                row_idx = cell.row
                headers = ws.row_values(1)
                for col_name, val in updated_record.items():
                    if col_name in headers:
                        col_idx = headers.index(col_name) + 1
                        ws.update_cell(row_idx, col_idx, str(val))
                return True
        return False

    def _get_fallback_mock_data(self, table_name: str) -> pd.DataFrame:
        if table_name == "leads_data":
            return pd.DataFrame([{
                "client_id": "BID-Oct-26-001", "date_stamp": "2026-10-12 10:15:00",
                "client_name": "Rajesh Kumar", "company_name": "Kumar Builders",
                "number": "9876543210", "email": "rajesh@kumar.com",
                "product": "Rolling Shutter", "qty": 2, "address": "MI Road",
                "city": "Jaipur", "state": "Rajasthan", "source": "WhatsApp",
                "assigned_salesperson": "Jeevan", "type_of_client": "Builder",
                "customer_responded": "Yes", "final_status": "Under Discussion",
                "quotation_status": "Sent", "leads_handled_by": "Albert",
                "quotation_sent_by": "Pooja", "customer_status": "Active",
                "remarks": "Needs motor quote", "month": "October", "date": "12"
            }])
        elif table_name == "quotation_sheet":
            return pd.DataFrame([{
                "quotation_id": "Q-001", "client_id": "BID-Oct-26-001",
                "quotation_number": "SSAPL/2026-27/841", "quotation_amount": 125000,
                "revised_count": 0, "quotation_status": "Pending",
                "follow_up_required": True, "assigned_qs_id": "Pooja",
                "quotation_shared_by": "Pooja", "company_name_1": "Kumar Builders",
                "request_timestamp": "2026-10-12 11:00:00", "completion_timestamp": "",
                "is_after_cutoff": False, "target_completion_date": "2026-10-12"
            }])
        elif table_name == "followup_tracker":
            return pd.DataFrame([{
                "followup_id": "F-001", "client_id": "BID-Oct-26-001",
                "quotation_id": "Q-001", "quotation_follow_up_by": "Jeevan",
                "followup_1": "Discussed spec", "total_followups": 1,
                "followup_status": "Under Discussion", "cancel_category": "",
                "won_by_followup": False, "scheduled_call_time": "2026-10-12 17:00:00",
                "notes": "Call regarding discount", "approved_date": "", "month": "October"
            }])
        elif table_name == "users":
            return pd.DataFrame([
                {"user_id": "u1", "full_name": "Admin User", "email": "admin@sidharth.com", "role": "Admin", "password_hash": "admin123"},
                {"user_id": "u2", "full_name": "Albert", "email": "albert@sidharth.com", "role": "Lead Executive", "password_hash": "pass123"},
                {"user_id": "u3", "full_name": "Pooja", "email": "pooja@sidharth.com", "role": "Quotation Specialist", "password_hash": "pass123"},
                {"user_id": "u4", "full_name": "Jeevan", "email": "jeevan@sidharth.com", "role": "Sales Manager", "password_hash": "pass123"}
            ])
        return pd.DataFrame()