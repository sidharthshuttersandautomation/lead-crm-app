"""
config/settings.py - Single source of truth for business rules and option lists.

Change values here, not inside the views. Items marked PENDING DECISION are
placeholders until the business team signs them off.
"""
import pytz

# ---------------------------------------------------------------- Brand
PRIMARY_ROYAL_BLUE = "#184B9C"
DARK_NAVY_BLUE = "#0E2C68"
ACCENT_EMERALD_GREEN = "#00A859"
BACKGROUND_LIGHT = "#F8FAFC"
LOGO_PATH = "assets/company_logo.jpeg"

# ---------------------------------------------------------------- Time & SLA
IST = pytz.timezone("Asia/Kolkata")
SLA_CUTOFF_HOUR = 17
SLA_CUTOFF_MINUTE = 30
TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"   # all timestamps are stored as IST text

# ---------------------------------------------------------------- Roles
ROLES = ["LGE", "QS", "SAM", "PO", "OPERATIONS", "ACCOUNTS", "ADMIN"]  # first = default when creating users
ROLE_DESCRIPTIONS = {
    "LGE": "Lead Generation Executive",
    "QS": "Quotation Specialist",
    "SAM": "Sales Account Manager",
    "ADMIN": "CRM Administrator",
    "OPERATIONS": "Operations Specialist",
    "ACCOUNTS": "Accounts & Collections",
    "PO": "PO & PI Team",
}
# Roles that add leads (used in "Added by" filters)
LEAD_ADDER_ROLES = ["LGE", "QS", "ADMIN"]
# Roles that record customer payments
COLLECTION_ROLES = ["ACCOUNTS", "ADMIN"]
# Roles allowed to approve quotations (shown in "Approved by")
APPROVER_ROLES = ["SAM", "ADMIN"]
# Roles allowed to download the full client export (PENDING DECISION)
EXPORT_ROLES = ["ADMIN"]

# ---------------------------------------------------------------- Status vocabulary
# Lead pipeline stage (leads_master.final_status). PENDING DECISION: sign-off.
# Business names, spelled as the company uses them. Done = deal won, Cancled = deal lost.
STAGE_NEW, STAGE_WON, STAGE_LOST = "Pending", "Done", "Cancled"
LEAD_STAGES = ["Done", "Cancled", "CallBack", "Pending", "In Discussion", "Not Responed", "Under Finalization"]
CLOSED_STAGES = [STAGE_WON, STAGE_LOST]
OPEN_STAGES = [s for s in LEAD_STAGES if s not in CLOSED_STAGES]
# Outcomes a follow-up call can record (it becomes the lead's new stage)
FOLLOWUP_OUTCOMES = LEAD_STAGES
CUSTOMER_RESPONDED = ["Yes", "No"]

# Where the lead is in the quotation desk (leads_master.quotation_status)
QUOTE_PROGRESS = ["Not Sent", "Under Process", "Sent"]

# Internal approval state of one quotation revision (quotations_master.quotation_status)
#   Under Review = drafted, waiting for approval (not yet sent to the client)
#   Approved     = approved and sent to the client
#   Rejected     = rejected internally, needs a new revision
QUOTE_APPROVAL = ["Under Review", "Approved", "Rejected"]

MAX_REVISIONS = 7          # R0 is the original; R1..R7 allowed. PENDING DECISION.
PRIORITIES = ["Normal", "High"]

# ---------------------------------------------------------------- Option lists
CLIENT_TYPES = ["Buy", "Service"]
CLIENT_ID_PREFIX = {"Buy": "BID", "Service": "SID"}
QUOTE_NUMBER_PREFIX = "SSAPL"
# First quotation number used when a financial year has no quotations yet.
# Set this to continue your existing numbering.
QUOTE_NUMBER_START = 841
# Quotation companies: prefix -> first number of its own series (used when the
# financial year has no quotations for that company yet).
QUOTE_COMPANIES = {"SSAPL": 841, "SSGI": 534, "SSA": 541}

SOURCE_OPTIONS = ["IndiaMart", "WhatsApp", "Phone Call", "Enquiry Email", "Sales Email", "Reference",
                  "Direct Visit", "Marketing Team"]

CANCEL_CATEGORY_OPTIONS = [
    "Price Issue", "Competitor Won", "No Response", "Project Hold",
    "Requirement Changed", "Not Interested", "Technical Mismatch",
    "Payment Issue", "Location Issue", "Internal Delay", "Budget Not Approved", "Site Not Ready",
]

PRODUCT_LIST = [
    "Automatic Rolling Shutters", "Dock Leveller", "Dock Shelter", "High-Speed Roll Up Door",
    "High-Speed Fold Up Door", "High-Speed Self Repairable Door", "Residential Sectional Doors",
    "Industrial Sectional Door", "Hermetic Doors", "Fire Exit Door", "Auto Sliding Door",
    "Motorised Swing Gates", "Motorised Sliding Gates", "Retractable Gates", "Boom Barriers",
    "Strong Life Shutter Motor", "Manual Shutters", "Wind Shutters", "No Product", "Spare Part",
    "Service Charge", "Sensor / Automatic Glass Door", "Motors", "Dock Bumper", "Dock Edge",
    "Overhead Sectional Door", "Gate", "Tank Door Shutter", "Gear Shutter", "General purpose Doors",
    "Not Confirmed", "Hanger Door", "Impact Barrier", "Manual Swing Gate", "Manual Sliding Gate", "Scissor Lift",
]
DEFAULT_PRODUCTS = [(p, "Products") for p in PRODUCT_LIST]

# "Assigned salesperson" dropdown, in this order. People without a login are kept as
# inactive employee records so leads can still be assigned to them. "N/A" = nobody.
SALESPERSON_LIST = [
    "Mansingh Rathore", "Sidharth Jain", "Deepak Sethiya", "Jeevan Sharma", "Shahwaj", "Jitendra Sharma",
    "Bhavya Jain", "N/A", "Lenox", "Rishabh Jain", "Rahul", "Nishant", "Rajesh Jain", "Albert Singh",
    "Shubham Jain", "Ravikant Dixit", "Dolly", "Raunak Sharma",
]

# Quotation pricing
DISCOUNT_TYPES = ["Percent (%)", "Amount (₹)"]

# Order fulfilment & collections
PAYMENT_STATUSES = ["Pending", "Partial", "Received"]   # calculated from payments
PAYMENT_MODES = ["NEFT / RTGS", "UPI", "Cheque", "Cash", "Demand Draft", "Adjustment"]
AGEING_BUCKETS = [(0, 30, "0–30 days"), (31, 60, "31–60 days"), (61, 90, "61–90 days"), (91, 100000, "90+ days")]
MEASUREMENT_STATUSES = ["Pending", "Completed"]
DRAWING_STATUSES = ["Pending", "Sent for Approval", "Approved"]
PRODUCTION_STATUSES = ["Not Started", "In Production", "Completed"]
DISPATCH_STATUSES = ["Pending", "Ready", "Dispatched", "Installed"]

# Follow-up time slots: (label, start_hour inclusive, end_hour exclusive)
TIME_SLOTS = [
    ("Morning (9–11 AM)", 0, 11),
    ("Midday (11 AM–1 PM)", 11, 13),
    ("Afternoon (1–4 PM)", 13, 16),
    ("Evening (4–6 PM)", 16, 18),
    ("Late evening (after 6 PM)", 18, 24),
]

REPORTING_WINDOWS = {
    "This month": "month",
    "Last 7 days": 7, "Last 15 days": 15, "Last 30 days": 30,
    "Last 3 months": 91, "Last 6 months": 182, "Last 12 months": 365, "All time": None,
}

# ---------------------------------------------------------------- Management modules
# Who can open the management screens (KPI tower, team, reassignment, master export).
MANAGEMENT_ROLES = ["ADMIN"]                       # PENDING DECISION

# Working hours used for "lead waiting" timers. Sundays are off.
WORKDAY_START = (9, 30)
WORKDAY_END = (SLA_CUTOFF_HOUR, SLA_CUTOFF_MINUTE)

# Bottleneck thresholds
UNCLAIMED_ALERT_WORK_HOURS = 2      # unclaimed longer than this (working hours) is flagged
STALE_FOLLOWUP_DAYS = 3             # no call activity for more than this many days
UNDER_REVIEW_ALERT_HOURS = 24       # quotation waiting for approval longer than this
HIGH_REVISION_ALERT = 3             # quotations with this many revisions or more are flagged
QS_OVERLOAD_FACTOR = 1.5            # QS with open tickets > team average x this is "overloaded"

# Chance an open lead converts, by stage. Used for "expected realization". PENDING DECISION.
STAGE_PROBABILITY = {
    "Pending": 0.05,
    "In Discussion": 0.25,
    "CallBack": 0.30,
    "Not Responed": 0.10,
    "Under Finalization": 0.70,
}


# ---------------------------------------------------------------- PO & 3-stage payment collection
# (name, percent of order value, what triggers it)
PAYMENT_PLAN = [("Advance (on PO)", 50, "po"), ("Before dispatch", 40, "dispatch"), ("After installation", 10, "install")]
# Common payment terms offered in the PO form (advance / before dispatch / after installation).
PAYMENT_TERM_PRESETS = {"50 / 40 / 10 (standard)": (50, 40, 10), "100% advance": (100, 0, 0),
                        "60 / 30 / 10": (60, 30, 10), "20 / 70 / 10": (20, 70, 10), "10 / 80 / 10": (10, 80, 10),
                        "30 / 60 / 10": (30, 60, 10), "Custom": None}
PO_CHECKS = ["Amount matches the quotation", "Terms & conditions match", "Delivery period matches",
             "Billing / GST details correct", "Scope & quantity match"]
DELIVERY_ALERT_DAYS = 2           # "delivery in 2 days — ask for the dispatch payment"
DEFAULT_DELIVERY_DAYS = 20
PAYMENT_OUTCOMES = ["Payment received", "Promised to pay", "Payment delayed", "Not reachable", "Asked to call later"]
DELAY_REASONS = ["Client fund issue", "Awaiting internal approval", "Site / material not ready", "Dispute on quantity or quality",
                 "Documents / invoice pending", "Waiting for dispatch / installation", "Other"]
PO_ROLES = ["ADMIN", "PO"]   # only the PO & PI team (and admins) use the PO desk

# ---------------------------------------------------------------- Monthly targets (set by admins)
# metric key -> (label, roles it applies to, unit)
TARGET_METRICS = {
    "leads_added": ("Leads added", ["LGE", "QS"], "count"),
    "quotations_sent": ("Quotations sent", ["QS"], "count"),
    "calls_logged": ("Follow-up calls logged", ["QS", "SAM", "LGE"], "count"),
    "leads_converted": ("Deals done (converted)", ["SAM"], "count"),
    "sales_value": ("Sales value done (₹)", ["SAM"], "money"),
    "collections": ("Payments collected (₹)", ["ACCOUNTS", "SAM", "PO"], "money"),
    "pos_verified": ("POs verified", ["PO"], "count"),
    "payment_calls": ("Payment calls logged", ["PO"], "count"),
}
