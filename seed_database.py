"""
seed_database.py - Generates 50+ Real-World Test Records for Sidharth Shutter CRM.
"""
import random
import sqlite3
import datetime

DB_PATH = "crm_database.db"

DEFAULT_EMPLOYEES = [
    ("EMP-101", "Albert Singh", "albert@sidharth.com", "albert123", "LGE"),
    ("EMP-102", "Pooja", "pooja@sidharth.com", "pooja123", "QS"),
    ("EMP-103", "Anjali", "anjali@sidharth.com", "anjali123", "QS"),
    ("EMP-104", "Dolly", "dolly@sidharth.com", "dolly123", "QS"),
    ("EMP-105", "Jeevan Sharma", "jeevan@sidharth.com", "jeevan123", "SAM"),
    ("EMP-106", "Jitendra Sharma", "jitendra@sidharth.com", "jitendra123", "SAM"),
    ("EMP-107", "Deepak Sethiya", "deepak@sidharth.com", "deepak123", "SAM"),
    ("EMP-108", "System Administrator", "admin@sidharth.com", "admin123", "ADMIN")
]

DEFAULT_PRODUCTS = [
    ("Automatic Rolling Shutters", "Shutters"),
    ("Dock Leveller", "Dock Equipment"),
    ("Dock Shelter", "Dock Equipment"),
    ("High-Speed Roll Up Door", "Doors"),
    ("High-Speed Fold Up Door", "Doors"),
    ("Hermetic Doors", "Doors"),
    ("Fire Exit Door", "Doors"),
    ("Boom Barriers", "Automation"),
    ("Motors", "Components"),
    ("Spare Part", "Components"),
    ("Service Charge", "Services")
]

FIRST_NAMES = ["Rajesh", "Vikram", "Sanjay", "Anil", "Amit", "Pankaj", "Rohan", "Sunil", "Manish", "Deepak", "Rakesh", "Suresh", "Alok", "Vikas", "Gaurav"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Patel", "Jain", "Mehta", "Singh", "Agarwal", "Chawla", "Bhatia", "Kulkarni", "Reddy", "Nair", "Rao", "Joshi"]
COMPANY_PREFIXES = ["Apex", "Reliance", "Tata", "Blue Star", "Mahindra", "Suzlon", "Godrej", "Adani", "Larsen", "Kirloskar", "Thermax", "Havel's", "Finolex", "Voltas", "Polycab"]
COMPANY_SUFFIXES = ["Industries", "Logistics Pvt Ltd", "Automation Co", "Engineering Solutions", "Pharma Ltd", "Cold Storage", "Infra", "Motors", "Traders", "Enterprises"]
CITIES_STATES = [
    ("Indore", "Madhya Pradesh"), ("Bhopal", "Madhya Pradesh"), ("Bangalore", "Karnataka"),
    ("Pune", "Maharashtra"), ("Mumbai", "Maharashtra"), ("Ahmedabad", "Gujarat"),
    ("Delhi", "Delhi"), ("Gurgaon", "Haryana"), ("Jaipur", "Rajasthan"), ("Hyderabad", "Telangana")
]
SOURCES = ["IndiaMart", "WhatsApp", "Phone Call", "Enquiry Email", "Direct Visit"]
SAM_IDS = ["EMP-105", "EMP-106", "EMP-107"]
QS_IDS = ["EMP-102", "EMP-103", "EMP-104"]

def seed_large_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS followup_logs")
    cursor.execute("DROP TABLE IF EXISTS quotations_master")
    cursor.execute("DROP TABLE IF EXISTS leads_master")
    cursor.execute("DROP TABLE IF EXISTS customers")
    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("DROP TABLE IF EXISTS employees")

    # 1. Employees
    cursor.execute("""
    CREATE TABLE employees (
        employee_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.executemany("INSERT INTO employees (employee_id, full_name, email, password, role) VALUES (?, ?, ?, ?, ?)", DEFAULT_EMPLOYEES)

    # 2. Products
    cursor.execute("""
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL UNIQUE,
        category TEXT DEFAULT 'Automation',
        is_active INTEGER DEFAULT 1
    )
    """)
    cursor.executemany("INSERT INTO products (product_name, category) VALUES (?, ?)", DEFAULT_PRODUCTS)

    # 3. Customers
    cursor.execute("""
    CREATE TABLE customers (
        client_id TEXT PRIMARY KEY,
        client_name TEXT NOT NULL,
        company_name TEXT,
        phone_number TEXT NOT NULL,
        email TEXT,
        address TEXT,
        city TEXT NOT NULL,
        state TEXT DEFAULT 'Madhya Pradesh',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 4. Leads Master
    cursor.execute("""
    CREATE TABLE leads_master (
        lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        source TEXT NOT NULL,
        type_of_client TEXT DEFAULT 'New Buy',
        final_status TEXT DEFAULT 'Under Discussion',
        quotation_status TEXT DEFAULT 'Not Sent',
        customer_status TEXT DEFAULT 'Active',
        customer_responded TEXT DEFAULT 'Yes',
        product_status TEXT DEFAULT 'Standard',
        remarks TEXT,
        handled_by_lge_id TEXT,
        assigned_sam_id TEXT,
        ingestion_date DATE DEFAULT CURRENT_DATE,
        claimed_qs_id TEXT DEFAULT 'Unassigned',
        FOREIGN KEY (client_id) REFERENCES customers(client_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id),
        FOREIGN KEY (handled_by_lge_id) REFERENCES employees(employee_id),
        FOREIGN KEY (assigned_sam_id) REFERENCES employees(employee_id)
    )
    """)

    # 5. Quotations Master
    cursor.execute("""
    CREATE TABLE quotations_master (
        quotation_id TEXT PRIMARY KEY,
        lead_id INTEGER NOT NULL,
        client_id TEXT NOT NULL,
        quotation_number TEXT NOT NULL,
        revision_no INTEGER DEFAULT 0,
        revised TEXT DEFAULT 'No',
        qut_amount NUMERIC(12, 2) NOT NULL,
        quotation_status TEXT DEFAULT 'Approved',
        follow_up_required TEXT DEFAULT 'Yes',
        claimed_qs_id TEXT,
        approved_by_id TEXT,
        shared_by_id TEXT,
        folder_link TEXT,
        company_name_1 TEXT,
        approved_date DATE,
        approved_month TEXT,
        created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads_master(lead_id),
        FOREIGN KEY (client_id) REFERENCES customers(client_id),
        FOREIGN KEY (claimed_qs_id) REFERENCES employees(employee_id)
    )
    """)

    # 6. Followup Logs
    cursor.execute("""
    CREATE TABLE followup_logs (
        followup_id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        quotation_id TEXT,
        employee_id TEXT NOT NULL,
        followup_sequence_no INTEGER DEFAULT 1,
        followup_status TEXT NOT NULL,
        cancel_category TEXT DEFAULT 'N/A',
        won_by_followup INTEGER DEFAULT 0,
        scheduled_call_time TIMESTAMP,
        notes TEXT NOT NULL,
        logged_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads_master(lead_id),
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
    )
    """)

    random.seed(42)
    base_date = datetime.date(2026, 10, 1)

    print("⚡ Generating 50 fake test records...")
    for i in range(1, 51):
        cid = f"BID-Oct-26-{i:03d}"
        cname = f"Mr {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        comp = f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"
        phone = f"9{random.randint(100000000, 999999999)}"
        email = f"{cname.split()[-1].lower()}@{comp.split()[0].lower()}.com"
        city, state = random.choice(CITIES_STATES)
        addr = f"Plot No {random.randint(10, 250)}, Industrial Area Phase {random.randint(1, 4)}"

        # Insert Customer
        cursor.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", (cid, cname, comp, phone, email, addr, city, state))

        pid = random.randint(1, len(DEFAULT_PRODUCTS))
        prod_name = DEFAULT_PRODUCTS[pid - 1][0]
        qty = random.randint(1, 8)
        src = random.choice(SOURCES)
        sam_id = random.choice(SAM_IDS)

        # 60% leads have quotations sent, 40% unassigned
        is_quoted = i <= 30
        qstat = "Sent" if is_quoted else "Not Sent"
        claimed_qs = random.choice(QS_IDS) if is_quoted else "Unassigned"
        fstat = random.choice(["Under Discussion", "Done", "Under Review"]) if is_quoted else "Under Discussion"

        ingest_dt = str(base_date + datetime.timedelta(days=(i % 14)))

        # Insert Lead
        cursor.execute("""
        INSERT INTO leads_master (client_id, product_id, quantity, source, final_status, quotation_status, handled_by_lge_id, assigned_sam_id, ingestion_date, claimed_qs_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cid, pid, qty, src, fstat, qstat, "EMP-101", sam_id, ingest_dt, claimed_qs))

        lead_id = cursor.lastrowid

        # Insert Quotation if quoted
        if is_quoted:
            q_num = f"SSAPL/2026-27/{840 + i}"
            amount = round(random.uniform(25000.0, 450000.0), 2)
            rev_str = random.choice(["No", "Yes - R1", "Yes - R2", "Yes - R3"])
            cursor.execute("""
            INSERT INTO quotations_master (quotation_id, lead_id, client_id, quotation_number, revised, qut_amount, quotation_status, claimed_qs_id, shared_by_id, company_name_1, approved_date, approved_month)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"QUO-{i:04d}", lead_id, cid, q_num, rev_str, amount, "Approved", claimed_qs, claimed_qs, comp, ingest_dt, "October"))

        # Log initial follow-up
        cursor.execute("""
        INSERT INTO followup_logs (lead_id, employee_id, followup_status, notes)
        VALUES (?, ?, ?, ?)
        """, (lead_id, "EMP-101", fstat, f"Initial lead ingested for {cname}"))

    conn.commit()
    conn.close()
    print("✅ Successfully generated 50 test records in crm_database.db!")

if __name__ == "__main__":
    seed_large_database()