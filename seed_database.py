"""
Relational Database Seeder for Sidharth Shutter & Automation CRM.
Creates employees, products, customers, leads_master, quotations_master, and followup_logs.
"""
import sqlite3

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

RAW_CLIENT_LEADS = [
    ("BID-Oct-26-001", "Mr Omprakash", "", "5103316010", "om@neravu.com", "134 sobha legacy Devanahalli Bangalore", "Bangalore", "Karnataka", "Overhead Sectional Door", 2, "Whats App", "EMP-101", "EMP-105", "Done", "Not Sent"),
    ("BID-Oct-26-002", "Mr Neeraj", "", "9601266130", "", "punjab", "Punjab", "Punjab", "Motors", 1, "Phone Call", "EMP-101", "EMP-105", "Done", "Not Sent"),
    ("BID-Oct-26-003", "Mr Venektesh", "", "9039095870", "", "Bengaluru, Karnataka, India", "Bangalore", "Karnataka", "Motors", 1, "India Mart", "EMP-101", "EMP-105", "Done", "Not Sent"),
    ("BID-Oct-26-005", "Mr Baljeet", "Blue Cold Refrigeration Pvt. Ltd.", "9972618426", "projects.blr2@bluecoldref.com", "Plant at RIICO Industrial area, Bhiwadi", "Bhiwadi", "Rajasthan", "Dock Leveller", 6, "Enquiry Email", "EMP-101", "EMP-105", "Done", "Sent"),
    ("BID-Oct-26-006", "N/A", "KANAK ENGINEERING AND TRADING CO.", "7428531318", "kanak_engineering@yahoo.com", "1/5111, GALI NO.4, BALBIR NAGAR , SHAHDARA DELHI", "Delhi", "Delhi", "High-Speed Roll Up Door", 10, "Whats App", "EMP-101", "EMP-105", "Done", "Sent"),
    ("BID-Oct-26-010", "Mr Rahul Gupta", "Rahul trading co", "9707214967", "rahultradingcompany.info@gmail.com", "Guwhati Assam", "Assam", "Assam", "Boom Barriers", 6, "Whats App", "EMP-101", "EMP-105", "Done", "Sent")
]

def seed_relational_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS followup_logs")
    cursor.execute("DROP TABLE IF EXISTS quotations_master")
    cursor.execute("DROP TABLE IF EXISTS leads_master")
    cursor.execute("DROP TABLE IF EXISTS customers")
    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("DROP TABLE IF EXISTS employees")

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

    cursor.execute("""
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL UNIQUE,
        category TEXT DEFAULT 'Automation',
        is_active INTEGER DEFAULT 1
    )
    """)
    cursor.executemany("INSERT INTO products (product_name, category) VALUES (?, ?)", DEFAULT_PRODUCTS)

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

    for idx, item in enumerate(RAW_CLIENT_LEADS, start=1):
        cid, cname, comp, phone, email, addr, city, state, prod_name, qty, source, lge_id, sam_id, fstat, qstat = item

        cursor.execute("INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", (cid, cname, comp, phone, email, addr, city, state))

        cursor.execute("SELECT product_id FROM products WHERE product_name = ?", (prod_name,))
        p_row = cursor.fetchone()
        pid = p_row[0] if p_row else 1

        cursor.execute("""
        INSERT INTO leads_master (client_id, product_id, quantity, source, final_status, quotation_status, handled_by_lge_id, assigned_sam_id, claimed_qs_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cid, pid, qty, source, fstat, qstat, lge_id, sam_id, "EMP-102" if qstat == "Sent" else "Unassigned"))

        lead_id = cursor.lastrowid

        if qstat == "Sent":
            q_num = f"SSAPL/2026-27/{840 + idx}"
            cursor.execute("""
            INSERT INTO quotations_master (quotation_id, lead_id, client_id, quotation_number, qut_amount, quotation_status, claimed_qs_id, shared_by_id, company_name_1)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"QUO-{idx:04d}", lead_id, cid, q_num, 53100.0, "Approved", "EMP-102", "EMP-102", comp))

        cursor.execute("""
        INSERT INTO followup_logs (lead_id, employee_id, followup_status, notes)
        VALUES (?, ?, ?, ?)
        """, (lead_id, lge_id, fstat, f"Initial lead ingested for {cname}"))

    conn.commit()
    conn.close()
    print("✅ Database successfully seeded matching clean relational schema!")

if __name__ == "__main__":
    seed_relational_database()