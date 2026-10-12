import datetime
import pytz

# Timezone & SLA Cutoff Settings
IST_TZ = pytz.timezone("Asia/Kolkata")
SLA_CUTOFF_HOUR = 17
SLA_CUTOFF_MINUTE = 30

# Branding
LOGO_BLUE = "#0A4B8A"
COMPANY_NAME = "Sidharth Shutter & Automation"

# Master Dropdowns
LEAD_SOURCES = ["WhatsApp", "Phone Call", "Enquiry Email", "Website", "Indiamart", "Referral", "Direct Sales"]
TYPE_OF_CLIENT = ["Architect", "Builder", "End User", "Contractor", "Dealer"]
FINAL_STATUS_OPTIONS = ["Under Discussion", "Done", "Canceled"]
QUOTATION_STATUS_OPTIONS = ["Pending", "Approved", "Rejected", "Under Discussion"]
FOLLOWUP_STATUS_OPTIONS = ["Under Discussion", "Won", "Lost", "Rescheduled"]
CANCEL_CATEGORIES = ["Price Issue", "Competitor Won", "Delay in Quote", "Client Cancelled Project", "Specifications Not Matching", "Other"]

USER_ROLES = ["Admin", "Lead Executive", "Quotation Specialist", "Sales Manager"]