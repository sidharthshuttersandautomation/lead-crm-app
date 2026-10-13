"""
Master Configuration & Options for Sidharth Shutter CRM.
"""
import pytz

PRIMARY_ROYAL_BLUE = "#184B9C"
DARK_NAVY_BLUE = "#0E2C68"
ACCENT_EMERALD_GREEN = "#00A859"
BACKGROUND_LIGHT = "#F8FAFC"

IST = pytz.timezone("Asia/Kolkata")
SLA_CUTOFF_HOUR = 17
SLA_CUTOFF_MINUTE = 30

CLIENT_TYPES = ["New Buy", "Service"]

FINAL_STATUS_OPTIONS = ["Done", "Cancled", "CallBack", "Pending", "In Discussion", "Not Responed", "Under Finalization"]

PRODUCT_NAME_OPTIONS = [
    "Automatic Rolling Shutters", "Dock Leveller", "Dock Shelter",
    "High-Speed Roll Up Door", "High-Speed Fold Up Door", "High-Speed Self Repairable Door",
    "Residential Sectional Doors", "Industrial Sectional Door", "Hermetic Doors",
    "Fire Exit Door", "Auto Sliding Door", "Motorised Swing Gates",
    "Motorised Sliding Gates", "Retractable Gates", "Boom Barriers",
    "Strong Life Shutter Motor", "Manual Shutters", "Wind Shutters",
    "Spare Part", "Service Charge", "Motors", "Dock Bumper", "Dock Edge",
    "Overhead Sectional Door", "Gate", "Scissor Lift"
]

SALESPERSONS_LIST = [
    "Mansingh Rathore", "Sidharth Jain", "Deepak Sethiya", "Jeevan Sharma",
    "Shahwaj", "Jitendra Sharma", "Bhavya Jain", "Albert Singh", "Rishabh Jain", "Dolly", "N/A"
]

CANCEL_CATEGORY_OPTIONS = [
    "Price Issue", "Competitor Won", "No Response", "Project Hold",
    "Requirement Changed", "Not Interested", "Technical Mismatch",
    "Payment Issue", "Location Issue", "Site Not Ready"
]

SOURCE_OPTIONS = ["Marketing Team", "WhatsApp", "IndiaMart", "Sales Email", "Phone Call", "Reference", "Direct Visit"]

TEAM_MEMBERS = ["Pooja", "Dolly", "Anjali", "Albert", "Rishabh", "Bhavya", "Jeevan Sharma", "Jitendra Sharma", "Deepak Sethiya", "Other"]

REPORTING_TIMEFRAMES = ["1 Week", "15 Days", "1 Month", "2 Months", "3 Months", "4 Months", "6 Months", "9 Months", "12 Months", "Custom Date Range"]