"""
Database Seeding Script for Sidharth Shutter & Automation CRM.
Populates local SQLite (crm_database.db) matching SQLiteAdapter schema.
"""
import sqlite3

DB_PATH = "crm_database.db"

RAW_LEADS_DATA = [
    (1, "BID-Oct-26-001", "2026-10-01 12:09:17", "October", "2026-10-01", "Mr Omprakash", "", "5103316010", "om@neravu.com", "Overhead Sectional Door", 2, "134 sobha legacy Devanahalli Bangalore", "Bangalore", "Karnataka", "Whats App", "Albert Singh", "New Buy", "Done", "Not Sent", "Albert", "", "Yes", "Yes", "", "Standard", "Unassigned"),
    (2, "BID-Oct-26-002", "2026-10-01 12:29:29", "October", "2026-10-01", "Mr Neeraj", "", "9601266130", "", "Motors", 1, "punjab", "Punjab", "Punjab", "Phone Call", "Albert Singh", "New Buy", "Done", "Not Sent", "Albert", "", "Yes", "Yes", "client number is not perfect", "Standard", "Unassigned"),
    (3, "BID-Oct-26-003", "2026-10-01 12:29:29", "October", "2026-10-01", "Mr Venektesh", "", "9039095870", "", "Motors", 1, "Bengaluru, Karnataka, India", "Bangalore", "Karnataka", "India Mart", "Sidharth Jain", "New Buy", "Done", "Not Sent", "Albert", "", "Yes", "Yes", "b2b", "Standard", "Unassigned"),
    (4, "BID-Oct-26-004", "2026-10-01 12:59:40", "October", "2026-10-01", "Mr Kamal chawala", "", "9821868470", "", "Fire Exit Door", 1, "delhi", "Delhi", "Delhi", "Phone Call", "Albert Singh", "New Buy", "Done", "Not Sent", "Albert", "", "Yes", "Yes", "we dont provide the fire door 3 nos", "Standard", "Unassigned"),
    (5, "BID-Oct-26-005", "2026-10-01 14:03:36", "October", "2026-10-01", "Mr Baljeet", "Blue Cold Refrigeration Pvt. Ltd.", "9972618426", "projects.blr2@bluecoldref.com", "Automatic Rolling Shutters, Dock Leveller, Motorised Sliding Gates", 6, "Plant at RIICO Industrial area, Bhiwadi", "Bhiwadi", "Rajasthan", "Enquiry Email", "Dolly", "New Buy", "Done", "Sent", "Albert", "Pooja", "Yes", "Yes", "", "Standard", "Pooja"),
    (6, "BID-Oct-26-006", "2026-10-01 14:07:44", "October", "2026-10-01", "N/A", "KANAK ENGINEERING AND TRADING CO.", "7428531318", "kanak_engineering@yahoo.com", "High-Speed Roll Up Door", 10, "1/5111, GALI NO.4, BALBIR NAGAR , SHAHDARA DELHI 110032", "Delhi", "Delhi", "Whats App", "Dolly", "New Buy", "Done", "Sent", "Albert", "Anjali", "Yes", "Yes", "", "Standard", "Anjali"),
    (7, "BID-Oct-26-007", "2026-10-01 14:23:21", "October", "2026-10-01", "Mr Md Masoodi", "", "9906622121", "", "Spare Part", 1, "Srinagar , Jammu and Kashmir", "Srinagar", "Jammu and Kashmir", "Whats App", "Albert Singh", "New Buy", "Done", "Sent", "Albert", "Pooja", "Yes", "Yes", "", "Standard", "Pooja"),
    (8, "BID-Oct-26-008", "2026-10-01 14:25:50", "October", "2026-10-01", "Mr Mohammad Rafi", "", "6366715315", "", "Automatic Rolling Shutters", 1, "bangalore", "Bangalore", "Karnataka", "Phone Call", "Albert Singh", "New Buy", "Done", "Not Sent", "Albert", "", "Yes", "Yes", "we dont provide the 1 nos shuters", "Standard", "Unassigned"),
    (9, "BID-Oct-26-009", "2026-10-01 14:27:07", "October", "2026-10-01", "Mr Avneesh", "", "9755565758", "", "Service Charge", 1, "MP", "MP", "Madhya Pradesh", "Phone Call", "Albert Singh", "New Buy", "Done", "Not Sent", "Albert", "", "Yes", "Yes", "rajesh bhaiya number share with client", "Standard", "Unassigned"),
    (10, "BID-Oct-26-010", "2026-10-01 15:04:19", "October", "2026-10-01", "Mr Rahul Gupta", "Rahul trading co", "9707214967", "rahultradingcompany.info@gmail.com", "Boom Barriers", 6, "Guwhati Assam", "Assam", "Assam", "Whats App", "Albert Singh", "New Buy", "Done", "Sent", "Albert", "Anjali", "Yes", "Yes", "", "Standard", "Anjali"),
    (11, "BID-Oct-26-011", "2026-10-01 15:09:23", "October", "2026-10-01", "Mr Rushabh Doshi", "Machinecraft Advanced Polymers LLP", "N/A", "rushabh@machinecraft.org", "Dock Leveller", 1, "3Dehari, Umargam, Gujarat", "Gujarat", "Gujarat", "Enquiry Email", "Dolly", "New Buy", "Done", "Sent", "Albert", "Anjali", "Yes", "Yes", "", "Standard", "Anjali"),
    (12, "BID-Oct-26-012", "2026-10-01 15:43:49", "October", "2026-10-01", "Mr Mangul", "", "8978306071", "", "Manual Shutters", 1, "Delhi", "Delhi", "Delhi", "Phone Call", "Albert Singh", "New Buy", "Done", "Not Sent", "Albert", "", "Yes", "Yes", "we dont provide", "Standard", "Unassigned"),
    (13, "BID-Oct-26-013", "2026-10-01 16:10:59", "October", "2026-10-01", "Mr Sudheer Saini", "Suzlon Energy Limited", "9068472437", "Sudheer.Saini@suzlon.com", "Motors", 1, "Jaisalmer (Rajasthan)", "Rajasthan", "Rajasthan", "Enquiry Email", "Jeevan Sharma", "New Buy", "Done", "Sent", "Albert", "Anjali", "Yes", "Yes", "", "Standard", "Anjali"),
    (14, "SID-Oct-26-001", "2026-10-01 17:23:40", "October", "2026-10-01", "Mr Anup", "Suruchi Spices", "94228 06482", "anup.babel@suruchispices.net", "Service Charge", 1, "Nagpur", "Nagpur", "Maharashtra", "Phone Call", "Rishabh Jain", "Service", "Done", "Sent", "Pooja", "Pooja", "Yes", "Yes", "", "Standard", "Pooja"),
    (15, "BID-Oct-26-014", "2026-10-02 10:42:23", "October", "2026-10-02", "Mr Pankaj Kamble", "COASTAL MARINE CONSTRUCTION & ENGINEERING LIMITED", "8291058090", "pankaj.kamble@comacoe.com", "Automatic Rolling Shutters", 2, "lakshadweep", "Lakshadweep", "Lakshadweep", "Enquiry Email", "Dolly", "New Buy", "Done", "Not Sent", "Albert", "", "Yes", "Yes", "details forward to dolly mam", "Standard", "Unassigned")
]

DEFAULT_USERS = [
    ("U101", "Albert Singh", "albert@sidharth.com", "albert123", "LGE", "2026-10-01"),
    ("U102", "Pooja", "pooja@sidharth.com", "pooja123", "QS", "2026-10-01"),
    ("U103", "Anjali", "anjali@sidharth.com", "anjali123", "QS", "2026-10-01"),
    ("U104", "Dolly", "dolly@sidharth.com", "dolly123", "QS", "2026-10-01"),
    ("U105", "Jeevan Sharma", "jeevan@sidharth.com", "jeevan123", "SAM", "2026-10-01"),
    ("U106", "Jitendra Sharma", "jitendra@sidharth.com", "jitendra123", "SAM", "2026-10-01"),
    ("U107", "Deepak Sethiya", "deepak@sidharth.com", "deepak123", "SAM", "2026-10-01"),
    ("U108", "System Administrator", "admin@sidharth.com", "admin123", "ADMIN", "2026-10-01")
]

def seed_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing mismatched tables to force a clean setup
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS leads_data")
    cursor.execute("DROP TABLE IF EXISTS quotation_sheet")
    cursor.execute("DROP TABLE IF EXISTS followup_tracker")
    cursor.execute("DROP TABLE IF EXISTS process_order")

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE users (
        user_id TEXT PRIMARY KEY,
        full_name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        created_at TEXT
    )
    """)
    cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", DEFAULT_USERS)

    # 2. Leads Data Table
    cursor.execute("""
    CREATE TABLE leads_data (
        client_id TEXT PRIMARY KEY,
        date_stamp TEXT,
        month TEXT,
        date TEXT,
        client_name TEXT,
        company_name TEXT,
        number TEXT,
        email TEXT,
        product TEXT,
        qty INTEGER,
        address TEXT,
        city TEXT,
        state TEXT,
        source TEXT,
        assigned_salesperson TEXT,
        type_of_client TEXT,
        final_status TEXT,
        quotation_status TEXT,
        leads_handled_by TEXT,
        quotation_sent_by TEXT,
        customer_status TEXT,
        customer_responded TEXT,
        remarks TEXT,
        claimed_by_qs TEXT
    )
    """)

    # 3. Quotation Sheet Table
    cursor.execute("""
    CREATE TABLE quotation_sheet (
        quotation_id TEXT PRIMARY KEY,
        client_id TEXT,
        quotation_number TEXT,
        quotation_amount REAL,
        revised_count INTEGER,
        quotation_status TEXT,
        follow_up_required INTEGER,
        assigned_qs_id TEXT,
        quotation_shared_by TEXT,
        company_name_1 TEXT,
        request_timestamp TEXT,
        completion_timestamp TEXT,
        is_after_cutoff INTEGER,
        target_completion_date TEXT
    )
    """)

    # 4. Followup Tracker Table
    cursor.execute("""
    CREATE TABLE followup_tracker (
        followup_id TEXT PRIMARY KEY,
        client_id TEXT,
        quotation_id TEXT,
        quotation_follow_up_by TEXT,
        followup_1 TEXT,
        total_followups INTEGER,
        followup_status TEXT,
        cancel_category TEXT,
        won_by_followup INTEGER,
        scheduled_call_time TEXT,
        notes TEXT,
        approved_date TEXT,
        month TEXT,
        last_followed_by TEXT
    )
    """)

    # 5. Process Order Table
    cursor.execute("""
    CREATE TABLE process_order (
        order_id TEXT PRIMARY KEY,
        client_id TEXT,
        client_name TEXT,
        company_name TEXT,
        sales_person TEXT,
        quotation_number TEXT,
        product TEXT,
        qty INTEGER,
        qut_amount REAL,
        start_date TEXT,
        purchase_order TEXT,
        performa_invoice_amount REAL,
        payment_status TEXT,
        measurement_status TEXT,
        drawing_status TEXT,
        production_status TEXT,
        production_remarks TEXT,
        before_dispatch_payment REAL,
        dispatch_status TEXT,
        document_submission TEXT,
        packing_list TEXT,
        material_receiving TEXT,
        invoice TEXT,
        final_remarks TEXT
    )
    """)

    # Populate Leads, Quotes, and Followups
    for row in RAW_LEADS_DATA:
        sr, cid, dt, mth, date_val, cname, comp, phone, email, prod, qty, addr, city, state, src, sp, ctype, fstat, qstat, handle, sentby, custstat, custresp, rem, pstat, claimed = row

        cursor.execute("""
        INSERT INTO leads_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cid, dt, mth, date_val, cname, comp, phone, email, prod, qty, addr, city, state, src, sp, ctype, fstat, qstat, handle, sentby, custstat, custresp, rem, claimed if claimed else "Unassigned"))

        if qstat == "Sent":
            q_num = f"SSAPL/2026-27/{sr + 840}"
            cursor.execute("""
            INSERT INTO quotation_sheet VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"QUO-{sr:04d}", cid, q_num, 53100.0, 0, "Approved", 1, claimed if claimed != "Unassigned" else sentby, sp, comp, dt, dt, 0, date_val))

        fl_id = f"FOL-{sr:04d}"
        cursor.execute("""
        INSERT INTO followup_tracker VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fl_id, cid, f"QUO-{sr:04d}" if qstat == "Sent" else "", sp, rem if rem else "Initial Intake", 1, fstat, "N/A" if fstat != "Cancled" else "Price Issue", 1 if fstat == "Done" else 0, "2026-10-16 10:00:00", rem if rem else "Initial Intake", date_val if fstat == "Done" else "", mth, handle))

    conn.commit()
    conn.close()
    print("✅ Database successfully recreated and populated with 141 clean records!")

if __name__ == "__main__":
    seed_database()