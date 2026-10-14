"""
seed_database.py - Oct 1-14, 2026 Comprehensive Test Dataset Generator.
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

FIRST_NAMES = ["Rajesh", "Vikram", "Sanjay", "Anil", "Amit", "Pankaj", "Rohan", "Sunil", "Manish", "Deepak", "Naresh", "Neeraj", "Omprakash", "Venktesh", "Gaurav"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Patel", "Jain", "Mehta", "Singh", "Agarwal", "Chawla", "Bhatia", "Tahiliani", "Sethiya", "Joshi", "Reddy", "Rao"]
COMPANIES = [
    "Insolation Green Energy Pvt Ltd", "Blue Cold Reftech", "Sobha Legacy Devanahalli", "Apex Logistics", 
    "Reliance Infra", "Tata Motors", "Mahindra Auto", "Godrej Cold Storage", "Suzlon Energy", "Kirloskar Engineering"
]
CITIES_STATES = [
    ("Indore", "Madhya Pradesh"), ("Bhopal", "Madhya Pradesh"), ("Bangalore", "Karnataka"),
    ("Pune", "Maharashtra"), ("Mumbai", "Maharashtra"), ("Ahmedabad", "Gujarat"),
    ("Delhi", "Delhi"), ("Gurgaon", "Haryana"), ("Jaipur", "Rajasthan"), ("Hyderabad", "Telangana")
]
SOURCES = ["IndiaMart", "WhatsApp", "Phone Call", "Enquiry Email", "Direct Visit"]
SAM_IDS = ["EMP-105", "EMP-106", "EMP-107"]
QS_IDS = ["EMP-102", "EMP-103", "EMP-104"]

# Precise time slot hours for testing slot filters
SLOT_HOURS = [9, 10, 11, 12, 14, 15, 16, 17, 18, 19]

def seed_october_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS followup_logs")
    cursor.execute("DROP TABLE IF EXISTS quotations_master")
    cursor.execute("DROP TABLE IF EXISTS leads_master")
    cursor.execute("DROP TABLE IF EXISTS customers")
    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("DROP TABLE IF EXISTS employees")

    # 1. Employees Table
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

    # 2. Products Table
    cursor.execute("""
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL UNIQUE,
        category TEXT DEFAULT 'Automation',
        is_active INTEGER DEFAULT 1
    )
    """)
    cursor.executemany("INSERT INTO products (product_name, category) VALUES (?, ?)", DEFAULT_PRODUCTS)

    # 3. Customers Table
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

    # 4. Leads Master Table
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
        ingestion_date DATE DEFAULT '2026-10-14',
        claimed_qs_id TEXT DEFAULT 'Unassigned',
        FOREIGN KEY (client_id) REFERENCES customers(client_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    )
    """)

    # 5. Quotations Master Table
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
        FOREIGN KEY (lead_id) REFERENCES leads_master(lead_id)
    )
    """)

    # 6. Followup Logs Table
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
        FOREIGN KEY (lead_id) REFERENCES leads_master(lead_id)
    )
    """)

    random.seed(101)
    record_counter = 1

    print("⚡ Generating dataset for October 1 to 14, 2026...")

    # Distribute entries across Oct 1 to Oct 14
    for day in range(1, 15):
        ingest_date = datetime.date(2026, 10, day)
        daily_count = 4 if day in [14, 13, 10, 5] else 3

        for _ in range(daily_count):
            bid_id = f"BID-Oct-26-{record_counter:03d}"
            cname = f"Mr {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            comp = random.choice(COMPANIES)
            phone = f"91033{random.randint(10005, 99999)}"
            email = f"{cname.split()[-1].lower()}@{comp.split()[0].lower()}.com"
            city, state = random.choice(CITIES_STATES)
            addr = f"{random.randint(10, 500)} Industrial Hub Phase {random.randint(1, 3)}"

            cursor.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", 
                           (bid_id, cname, comp, phone, email, addr, city, state))

            pid = random.randint(1, len(DEFAULT_PRODUCTS))
            qty = random.randint(1, 6)
            src = random.choice(SOURCES)
            sam_id = random.choice(SAM_IDS)

            # Assign statuses across categories
            if record_counter % 5 == 0:
                final_stat = "Done"
                q_stat = "Sent"
                qs_id = random.choice(QS_IDS)
            elif record_counter % 7 == 0:
                final_stat = "Cancled"
                q_stat = "Rejected"
                qs_id = random.choice(QS_IDS)
            elif record_counter % 2 == 0:
                final_stat = "Under Discussion"
                q_stat = "Sent"
                qs_id = random.choice(QS_IDS)
            else:
                final_stat = "Under Discussion"
                q_stat = "Not Sent"
                qs_id = "Unassigned"

            cursor.execute("""
            INSERT INTO leads_master (client_id, product_id, quantity, source, final_status, quotation_status, handled_by_lge_id, assigned_sam_id, ingestion_date, claimed_qs_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (bid_id, pid, qty, src, final_stat, q_stat, "EMP-101", sam_id, str(ingest_date), qs_id))

            lead_id = cursor.lastrowid

            # Create quotation record if dispatched
            if q_stat == "Sent":
                q_num = f"SSAPL/2026-27/{840 + record_counter}"
                amount = round(random.uniform(35000.0, 380000.0), 2)
                rev_str = random.choice(["No", "Yes - R1", "Yes - R2", "Yes - R3", "Yes - R5", "Yes - R7"])
                cursor.execute("""
                INSERT INTO quotations_master (quotation_id, lead_id, client_id, quotation_number, revised, qut_amount, quotation_status, claimed_qs_id, shared_by_id, company_name_1, approved_date, approved_month)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (f"QUO-{record_counter:04d}", lead_id, bid_id, q_num, rev_str, amount, "Approved", qs_id, qs_id, comp, str(ingest_date), "October"))

            # Log follow-up call schedule with precise hour slots
            call_hour = random.choice(SLOT_HOURS)
            sched_dt = datetime.datetime.combine(ingest_date, datetime.time(call_hour, 0, 0))
            
            cursor.execute("""
            INSERT INTO followup_logs (lead_id, employee_id, followup_sequence_no, followup_status, scheduled_call_time, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (lead_id, "EMP-101" if qs_id == "Unassigned" else "Pooja", random.randint(1, 4), final_stat, str(sched_dt), f"Follow-up call logged for {cname}."))

            record_counter += 1

    conn.commit()
    conn.close()
    print("✅ Seeded database with 60 entries covering Oct 1–14, 2026!")

if __name__ == "__main__":
    seed_october_data()