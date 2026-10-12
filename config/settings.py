import pytz

# Application Info
APP_TITLE = "Sidharth Shutter & Automation - Lead CRM"
APP_VERSION = "1.0.0"

# Brand Theme Styling (#0A4B8A Logo Blue)
PRIMARY_BLUE = "#0A4B8A"
PRIMARY_BLUE_HOVER = "#083B6E"
SECONDARY_BG = "#F8FAFC"
TEXT_COLOR = "#1E293B"

# Timezone & SLA Cutoff (5:30 PM IST Rule)
IST = pytz.timezone("Asia/Kolkata")
SLA_CUTOFF_HOUR = 17
SLA_CUTOFF_MINUTE = 30

# Master Dropdown Options
LEAD_SOURCES = [
    "Whats App",
    "Phone Call",
    "Enquiry Email",
    "Indiamart",
    "Website",
    "Direct Visit",
    "Reference",
    "Other",
]

PRODUCTS = [
    "Motorized Rolling Shutter",
    "Manual Shutter",
    "Sectional Overhead Door",
    "High-Speed Roll Up Door",
    "Automatic Sliding Gate",
    "Boom Barrier",
    "Dock Leveller",
    "Fire Rated Shutter",
    "Motors",
]

FINAL_STATUS_OPTIONS = ["Under Discussion", "Done", "Canceled"]
QUOTATION_STATUS_OPTIONS = ["Pending", "Approved", "Rejected", "Under Discussion"]
FOLLOWUP_STATUS_OPTIONS = ["Under Discussion", "Won", "Lost", "Rescheduled"]

CANCEL_CATEGORIES = [
    "Price Issue",
    "Competitor Won",
    "Delay in Quote",
    "Client Postponed",
    "Specifications Mismatch",
    "No Response",
    "Other",
]

DATE_FILTER_OPTIONS = [
    "10 Days",
    "15 Days",
    "1 Month",
    "3 Months",
    "4 Months",
    "6 Months",
    "9 Months",
    "12 Months",
    "Custom Range",
]