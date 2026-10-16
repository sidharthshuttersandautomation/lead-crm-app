"""
components/cards.py - One consistent, structured card for clients, calls, tickets and quotations.

Layout:  [client ID chip] Name · company              [big value]
                                                       [status pill]
         Label        Label        Label        Label
         value        value        value        value
         (Call / WhatsApp buttons)
         (optional note strip)
"""
import html

CSS_RAW = """
<style>
.ic-card { background:#FFFFFF; border:1px solid rgba(24,75,156,0.16); border-radius:16px; padding:16px 20px;
  margin-bottom:10px; box-shadow:0 2px 10px rgba(14,44,104,0.05); position:relative; overflow:hidden;
  transition: box-shadow .18s ease, border-color .18s ease; }
.ic-card:hover { border-color: rgba(24,75,156,0.35); box-shadow:0 8px 24px rgba(14,44,104,0.10); }
.ic-card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--accent,#184B9C); }
.ic-head { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; flex-wrap:wrap; }
.ic-id { display:inline-block; background:#E8EFFB; color:#184B9C; font-weight:800; font-size:12.5px;
  padding:3px 10px; border-radius:8px; letter-spacing:.02em; margin-right:8px; }
.ic-name { font-size:17px; font-weight:800; color:#0E2C68; }
.ic-co { color:#64748B; font-size:13.5px; font-weight:600; margin-top:3px; }
.ic-right { text-align:right; }
.ic-big { font-size:20px; font-weight:800; color:#0E2C68; font-variant-numeric:tabular-nums; }
.ic-pill { display:inline-block; padding:3px 11px; border-radius:20px; font-size:12px; font-weight:800; margin:4px 0 0 4px; }
.ic-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:10px 18px;
  margin-top:14px; padding-top:12px; border-top:1px dashed #E2E8F0; }
.ic-f .l { font-size:11.5px; text-transform:uppercase; letter-spacing:.06em; color:#94A3B8; font-weight:700; }
.ic-f .v { font-size:14px; color:#1E293B; font-weight:600; margin-top:2px; }
.ic-note { margin-top:12px; background:#F1F5F9; border-radius:10px; padding:9px 12px; font-size:13px; color:#475569; }
.ic-note.warn { background:#FFF1F2; color:#9F1239; }
</style>
"""

PILL = {
    "red": ("#FDE7EA", "#BE123C"), "amber": ("#FEF3C7", "#B45309"), "green": ("#E3F6EC", "#047857"),
    "blue": ("#E0F2FE", "#0369A1"), "navy": ("#E2E8F4", "#0E2C68"), "grey": ("#F1F5F9", "#475569"),
}
ACCENT = {"red": "#BE123C", "amber": "#B45309", "green": "#00A859", "blue": "#184B9C", "navy": "#0E2C68"}


def clean(v, empty="—"):
    if v is None:
        return empty
    s = str(v).strip()
    return empty if s.lower() in ("", "nan", "none", "nat") else s


def flat(markup: str) -> str:
    """HTML for st.markdown: no indentation and no blank lines, so Markdown never turns it into a code block."""
    return " ".join(line.strip() for line in markup.splitlines() if line.strip())


CSS = flat(CSS_RAW)


def card_html(client_id, name, company=None, big=None, pills=(), fields=(), links="", note=None,
              note_warn=False, accent="blue") -> str:
    pills_html = "".join(
        f"<span class='ic-pill' style='background:{PILL[c][0]}; color:{PILL[c][1]};'>{html.escape(t)}</span>"
        for t, c in pills if t)
    fields_html = "".join(
        f"<div class='ic-f'><div class='l'>{html.escape(l)}</div><div class='v'>{v}</div></div>"
        for l, v in fields if v not in (None, "", "—"))
    note_html = (f"<div class='ic-note{' warn' if note_warn else ''}'>{note}</div>" if note else "")
    return flat(f"""
    <div class='ic-card' style='--accent:{ACCENT.get(accent, accent)};'>
      <div class='ic-head'>
        <div><span class='ic-id'>{html.escape(clean(client_id))}</span><span class='ic-name'>{html.escape(clean(name))}</span>
          <div class='ic-co'>{html.escape(clean(company, ''))}</div></div>
        <div class='ic-right'>{f"<div class='ic-big'>{html.escape(big)}</div>" if big else ""}{pills_html}</div>
      </div>
      {f"<div class='ic-grid'>{fields_html}</div>" if fields_html else ""}
      {links}{note_html}
    </div>""")


def esc(v, empty="—"):
    return html.escape(clean(v, empty))
