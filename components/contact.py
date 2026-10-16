"""components/contact.py - Click-to-call, WhatsApp and email links."""
import html
from urllib.parse import quote


def phone_e164(phone) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 10:
        return "91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "91" + digits[1:]
    return digits


def contact_links(phone, email=None, name="") -> str:
    """HTML: Call / WhatsApp / Email buttons. Call opens the phone dialer (mobile) or calling app (PC)."""
    number = phone_e164(phone)
    parts = []
    if number:
        shown = html.escape(str(phone))
        parts.append(f"<a class='call-btn phone' href='tel:+{number}'>📞 Call {shown}</a>")
        greeting = quote(f"Hello {name}, this is Sidharth Shutter & Automation.")
        parts.append(f"<a class='call-btn wa' href='https://wa.me/{number}?text={greeting}' "
                     f"target='_blank' rel='noopener'>💬 WhatsApp</a>")
    if email and str(email) not in ("None", "nan", ""):
        parts.append(f"<a class='call-btn mail' href='mailto:{html.escape(str(email), quote=True)}'>✉️ Email</a>")
    return "<div style='margin:10px 0 2px;'>" + "".join(parts) + "</div>" if parts else ""
