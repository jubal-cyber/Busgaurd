import sqlite3

conn = sqlite3.connect("busguard.db")
cursor = conn.cursor()

# -----------------------------
# Admin Table
# -----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")

# -----------------------------
# Driver Table
# -----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    driver_id TEXT UNIQUE NOT NULL,
    phone TEXT,
    password TEXT NOT NULL
)
""")

# -----------------------------
# Bus Table
# -----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS buses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bus_number TEXT UNIQUE NOT NULL,
    assigned_driver TEXT,
    status TEXT
)
""")

# -----------------------------
# Location Table
# -----------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bus_id INTEGER,
    latitude REAL,
    longitude REAL,
    timestamp TEXT,
    journey_status TEXT
)
""")

# -----------------------------
# Default Admin
# -----------------------------
cursor.execute("""
INSERT OR IGNORE INTO admins (username, password)
VALUES (?, ?)
""", ("BusGuard", "BusGuard_123"))

# -----------------------------
# Default Driver
# -----------------------------
cursor.execute("""
INSERT OR IGNORE INTO drivers
(name, driver_id, phone, password)
VALUES (?, ?, ?, ?)
""", ("Mr. Kumar", "DR001", "9876543210", "Driver_123"))

# -----------------------------
# Default Bus
# -----------------------------
cursor.execute("""
INSERT OR IGNORE INTO buses
(bus_number, assigned_driver, status)
VALUES (?, ?, ?)
""", ("MCC001", "DR001", "Inactive"))

conn.commit()
conn.close()

print("✅ BusGuard database initialized successfully!")