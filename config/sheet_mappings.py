# Mappings to ensure Google Sheets column headers match exact database field definitions
LEADS_COLUMNS = [
    "client_id", "date_stamp", "client_name", "company_name", "number", "email",
    "product", "qty", "address", "city", "state", "source", "assigned_salesperson",
    "type_of_client", "customer_responded", "final_status", "quotation_status",
    "leads_handled_by", "quotation_sent_by", "customer_status", "remarks", "month", "date"
]

QUOTATION_COLUMNS = [
    "quotation_id", "client_id", "quotation_number", "quotation_amount", "revised_count",
    "quotation_status", "follow_up_required", "assigned_qs_id", "quotation_shared_by",
    "company_name_1", "request_timestamp", "completion_timestamp", "is_after_cutoff", "target_completion_date"
]

FOLLOWUP_COLUMNS = [
    "followup_id", "client_id", "quotation_id", "quotation_follow_up_by",
    "followup_1", "followup_2", "followup_3", "followup_4", "followup_5",
    "total_followups", "followup_status", "cancel_category", "won_by_followup",
    "scheduled_call_time", "notes", "approved_date", "month"
]

PROCESS_ORDER_COLUMNS = [
    "order_id", "client_id", "client_name", "company_name", "sales_person",
    "quotation_number", "product", "qty", "qut_amount", "start_date", "purchase_order",
    "performa_invoice_amount", "payment_status", "measurement_status", "drawing_status",
    "production_status", "production_remarks", "before_dispatch_payment",
    "dispatch_status", "document_submission", "packing_list", "material_receiving",
    "invoice", "final_remarks"
]

USERS_COLUMNS = ["user_id", "full_name", "email", "role", "password_hash"]