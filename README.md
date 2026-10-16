# Sidharth Shutter CRM

Streamlit lead, quotation, follow-up and order tracker. Database: SQLite (Supabase later).

## ⚠️ Read first: SQLite on Streamlit Cloud

Streamlit Community Cloud **wipes the database file every time the app restarts,
redeploys (every git push) or wakes from sleep.** Until the Supabase move:

- Treat the cloud app as a **test / training environment**.
- Admins: download a backup daily (Admin overview → Database backup).
- Don't enter real customer data you can't afford to lose.

## Project layout

```
app.py                  sign-in and role-based menu
config/settings.py      all business rules and option lists (edit here)
database/schema.py      table definitions
database/sqlite_adapter.py  the only file that talks to SQLite
database/factory.py     picks the database engine, creates tables + first admin
components/             shared UI pieces
views/                  one file per screen
utils/                  auth, IDs, SLA, metrics, alerts
scripts/seed_demo_data.py   demo data for an EMPTY database
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then edit passwords
streamlit run app.py
```

The first run creates `data/crm_database.db`, the product list, every account listed
under `[accounts.<username>]` in secrets, and (if `seed_demo_data = "true"`) sample leads.

## Login accounts

Accounts live in `.streamlit/secrets.toml` (locally) or App → Settings → Secrets (cloud):

```toml
[accounts.pooja]
name = "Pooja"
email = "pooja@sidharth.com"
role = "QS"              # ADMIN, LGE, QS, SAM, OPERATIONS
employee_id = "EMP-102"  # optional
password = "..."
```

- Sign in with the username (`pooja`), the email, or the employee ID.
- Missing accounts are created at start-up; existing ones are never overwritten.
- To add someone: add a block, save the secrets, reboot the app.
- On Streamlit Cloud every reboot resets the database, so accounts return to the
  passwords in secrets. Passwords changed in "My account" last until the next reset.

## Deploy with GitHub + Streamlit Community Cloud

1. **Create a private GitHub repository** (company account, not personal).
2. Push the code:
   ```bash
   git init
   git add .
   git status            # confirm NO secrets.toml and NO .db files are listed
   git commit -m "CRM v2: stabilised SQLite release"
   git branch -M main
   git remote add origin https://github.com/<company>/sidharth-crm.git
   git push -u origin main
   ```
3. Go to share.streamlit.io → **Create app** → pick the repo, branch `main`,
   main file `app.py`. Under **Advanced settings** choose Python 3.12 and paste the
   contents of your `secrets.toml` into **Secrets**.
4. Deploy. Sign in with the `[bootstrap]` admin email and password.
5. Updating later: `git add . && git commit -m "..." && git push`. The app redeploys
   automatically (and the SQLite data resets, see above).

## Roles

| Role | Main screens |
|---|---|
| ADMIN | 7 menu groups with sub-tabs: Overview · Alerts · Leads & clients · Quotations · Sales & money · Admin tools · My account |
| LGE | Add new lead, Follow-up calls, Client inspector |
| QS | Quotation desk, Claim & create, Quotation entry & revisions, Follow-up calls, Add new lead |
| SAM | Sales pipeline, Follow-up calls |
| OPERATIONS | Order fulfilment |
| PO | PO & PI Team (one login each): claim POs first-come-first-served, PO checks, any payment terms (e.g. 100% advance, 50/40/10, 20/70/10), payment calls |
| ACCOUNTS | Collections, Orders |

Extra access (set per person in **Users**):
- **Team lead** — adds 🔀 Reassign & escalate (default: Dolly).

Targets: admins set monthly targets in 📈 Employee report card; gauges show progress there and in each person's My progress.

## Follow-ups and POs (v3.3)

- **Follow-up by** on every new lead decides who calls the client. "Unclaimed" puts the lead in
  📞 Follow-up calls → 🙋 Unclaimed follow-ups, where the first person to claim it owns it.
- PO desk: 📥 claim a PO → 🗂️ Order profile → 🧾 PO revision (tick every point; send back for revision or verify).
  Every check round is kept; the order shows how many revisions and how long verification took.
  The progress bar only moves when money is received. Completed orders drop out of the Order profile list.
- Admin: 💼 Sales & money → 📈 PO progress. ⚙️ Admin tools → 📦 Master export & backup → 🧹 Clear all data.

## Mac, iPhone and iPad

- Colours are fixed to the light brand theme, so macOS/iOS dark mode does not change them.
- On phones the menu starts closed: tap the blue » button (top-left) to open it.
- iPhone/iPad pop-up alerts: Safari only allows them for web apps opened from the Home Screen
  (Share → Add to Home Screen, then open the CRM from that icon and tap "Turn on desktop alerts").
  Reminders inside the app work everywhere.

## Security checklist

- [ ] The old Google service-account key in the previous `secrets.toml` was shared:
      **delete/rotate it** in Google Cloud Console (IAM → Service accounts → Keys).
- [ ] Change `admin_password` and `demo_password` from the example values.
- [ ] Set `seed_demo_data = "false"` before real use.
- [ ] Never commit `.streamlit/secrets.toml` or any `.db` file (already in `.gitignore`).

## Business rules still pending sign-off (config/settings.py)

`LEAD_STAGES`, `MAX_REVISIONS`, `EXPORT_ROLES`, `QUOTE_NUMBER_START`, holiday calendar for the SLA.
