import os
import sqlite3
import secrets
from datetime import datetime, timezone

from flask import (
    Flask,
    g,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash
)

from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "busguard.db")

app = Flask(__name__)
app.secret_key = os.environ.get("BUSGUARD_SECRET_KEY", secrets.token_hex(32))


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS buses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_number TEXT UNIQUE NOT NULL,
            route TEXT,
            assigned_driver_id INTEGER,
            journey_status TEXT NOT NULL DEFAULT 'not_started',
            FOREIGN KEY (assigned_driver_id) REFERENCES drivers (id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_id INTEGER NOT NULL,
            driver_id INTEGER,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp TEXT NOT NULL,
            journey_status TEXT NOT NULL,
            FOREIGN KEY (bus_id) REFERENCES buses (id) ON DELETE CASCADE
        );
        """
    )

    # Seed the default admin account described in the roadmap, only once.
    existing = db.execute("SELECT id FROM admins LIMIT 1").fetchone()
    if not existing:
        db.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("BusGuard", generate_password_hash("BusGuard_123")),
        )
    db.commit()
    db.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not authenticated"}), 401
            return redirect(url_for("admin_login_page"))
        return fn(*args, **kwargs)

    return wrapper


def driver_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("driver_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not authenticated"}), 401
            return redirect(url_for("driver_login_page"))
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/track")
def track_page():
    return render_template("track.html")


@app.route("/admin/login")
def admin_login_page():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard_page"))
    return render_template("admin_login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard_page():
    return render_template("admin_dashboard.html")


@app.route("/driver/login")
def driver_login_page():
    if session.get("driver_id"):
        return redirect(url_for("driver_dashboard_page"))
    return render_template("driver_login.html")


@app.route("/driver/dashboard")
@driver_required
def driver_dashboard_page():
    db = get_db()
    driver = db.execute(
        "SELECT * FROM drivers WHERE id = ?", (session["driver_id"],)
    ).fetchone()
    bus = db.execute(
        "SELECT * FROM buses WHERE assigned_driver_id = ?", (session["driver_id"],)
    ).fetchone()
    return render_template("driver_dashboard.html", driver=driver, bus=bus)


# ---------------------------------------------------------------------------
# Admin auth API
# ---------------------------------------------------------------------------

@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    db = get_db()
    admin = db.execute(
        "SELECT * FROM admins WHERE username = ?", (username,)
    ).fetchone()

    if not admin or not check_password_hash(admin["password_hash"], password):
            return jsonify({"success": False, "message": "Invalid Admin ID or password."}), 401

    session.clear()
    session["admin_id"] = admin["id"]
    session["admin_username"] = admin["username"]
    return jsonify({"success": True, "redirect": url_for("admin_dashboard_page")})


@app.route("/api/admin/logout", methods=["POST"])
def api_admin_logout():
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("landing")})


# ---------------------------------------------------------------------------
# Driver auth API
# ---------------------------------------------------------------------------

@app.route("/api/driver/login", methods=["POST"])
def api_driver_login():
    data = request.get_json(silent=True) or {}
    driver_id = (data.get("driverId") or "").strip()
    password = data.get("password") or ""

    db = get_db()
    driver = db.execute(
        "SELECT * FROM drivers WHERE driver_id = ?", (driver_id,)
    ).fetchone()

    if not driver or not check_password_hash(driver["password_hash"], password):
        return jsonify({"error": "Invalid Driver ID or password."}), 401

    session.clear()
    session["driver_id"] = driver["id"]
    session["driver_name"] = driver["name"]
    return jsonify({"ok": True, "redirect": url_for("driver_dashboard_page")})


@app.route("/api/driver/logout", methods=["POST"])
def api_driver_logout():
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("landing")})


# ---------------------------------------------------------------------------
# Admin management API — Drivers
# ---------------------------------------------------------------------------

@app.route("/api/admin/drivers", methods=["GET"])
@admin_required
def list_drivers():
    db = get_db()
    rows = db.execute(
        """
        SELECT d.id, d.driver_id, d.name, d.phone, d.created_at,
               b.bus_number AS assigned_bus
        FROM drivers d
        LEFT JOIN buses b ON b.assigned_driver_id = d.id
        ORDER BY d.id DESC
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/admin/drivers", methods=["POST"])
@admin_required
def add_driver():
    data = request.get_json(silent=True) or {}
    driver_id = (data.get("driver_id") or "").strip()
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""

    if not driver_id or not name or not password:
        return jsonify({"error": "driver_id, name and password are required."}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO drivers (driver_id, name, phone, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (driver_id, name, phone, generate_password_hash(password), now_iso()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "That Driver ID already exists."}), 409

    return jsonify({"ok": True})


@app.route("/api/admin/drivers/<int:driver_pk>", methods=["PUT"])
@admin_required
def edit_driver(driver_pk):
    data = request.get_json(silent=True) or {}
    db = get_db()
    driver = db.execute("SELECT * FROM drivers WHERE id = ?", (driver_pk,)).fetchone()
    if not driver:
        return jsonify({"error": "Driver not found."}), 404

    name = (data.get("name") or driver["name"]).strip()
    phone = (data.get("phone") or driver["phone"] or "").strip()

    if data.get("password"):
        db.execute(
            "UPDATE drivers SET name = ?, phone = ?, password_hash = ? WHERE id = ?",
            (name, phone, generate_password_hash(data["password"]), driver_pk),
        )
    else:
        db.execute(
            "UPDATE drivers SET name = ?, phone = ? WHERE id = ?",
            (name, phone, driver_pk),
        )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/drivers/<int:driver_pk>", methods=["DELETE"])
@admin_required
def remove_driver(driver_pk):
    db = get_db()
    db.execute("UPDATE buses SET assigned_driver_id = NULL WHERE assigned_driver_id = ?", (driver_pk,))
    db.execute("DELETE FROM drivers WHERE id = ?", (driver_pk,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Admin management API — Buses
# ---------------------------------------------------------------------------

@app.route("/api/admin/buses", methods=["GET"])
@admin_required
def list_buses():
    db = get_db()
    rows = db.execute(
        """
        SELECT bu.id, bu.bus_number, bu.route, bu.journey_status,
               d.id AS driver_pk, d.driver_id AS driver_code, d.name AS driver_name
        FROM buses bu
        LEFT JOIN drivers d ON d.id = bu.assigned_driver_id
        ORDER BY bu.id DESC
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/admin/buses", methods=["POST"])
@admin_required
def add_bus():
    data = request.get_json(silent=True) or {}
    bus_number = (data.get("bus_number") or "").strip()
    route = (data.get("route") or "").strip()
    assigned_driver_pk = data.get("assigned_driver_id") or None

    if not bus_number:
        return jsonify({"error": "bus_number is required."}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO buses (bus_number, route, assigned_driver_id, journey_status) VALUES (?, ?, ?, 'not_started')",
            (bus_number, route, assigned_driver_pk),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "That bus number already exists."}), 409

    return jsonify({"ok": True})


@app.route("/api/admin/buses/<int:bus_pk>", methods=["PUT"])
@admin_required
def edit_bus(bus_pk):
    data = request.get_json(silent=True) or {}
    db = get_db()
    bus = db.execute("SELECT * FROM buses WHERE id = ?", (bus_pk,)).fetchone()
    if not bus:
        return jsonify({"error": "Bus not found."}), 404

    bus_number = (data.get("bus_number") or bus["bus_number"]).strip()
    route = data.get("route", bus["route"])
    assigned_driver_pk = data.get("assigned_driver_id", bus["assigned_driver_id"])

    try:
        db.execute(
            "UPDATE buses SET bus_number = ?, route = ?, assigned_driver_id = ? WHERE id = ?",
            (bus_number, route, assigned_driver_pk, bus_pk),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "That bus number already exists."}), 409

    return jsonify({"ok": True})


@app.route("/api/admin/buses/<int:bus_pk>", methods=["DELETE"])
@admin_required
def remove_bus(bus_pk):
    db = get_db()
    db.execute("DELETE FROM buses WHERE id = ?", (bus_pk,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/buses/<int:bus_pk>/end", methods=["POST"])
@admin_required
def admin_end_journey(bus_pk):
    db = get_db()
    bus = db.execute("SELECT * FROM buses WHERE id = ?", (bus_pk,)).fetchone()
    if not bus:
        return jsonify({"error": "Bus not found."}), 404

    db.execute("UPDATE buses SET journey_status = 'ended' WHERE id = ?", (bus_pk,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Admin monitoring API — live tracking / driver status / journey status
# ---------------------------------------------------------------------------

@app.route("/api/admin/overview", methods=["GET"])
@admin_required
def admin_overview():
    db = get_db()
    buses = db.execute(
        """
        SELECT bu.id, bu.bus_number, bu.journey_status,
               d.id AS driver_pk, d.driver_id AS driver_code, d.name AS driver_name
        FROM buses bu
        LEFT JOIN drivers d ON d.id = bu.assigned_driver_id
        ORDER BY bu.bus_number
        """
    ).fetchall()

    result = []
    for bus in buses:
        loc = db.execute(
            "SELECT latitude, longitude, timestamp FROM locations WHERE bus_id = ? ORDER BY id DESC LIMIT 1",
            (bus["id"],),
        ).fetchone()
        result.append(
            {
                "id": bus["id"],
                "bus_number": bus["bus_number"],
                "journey_status": bus["journey_status"],
                "driver_name": bus["driver_name"],
                "driver_code": bus["driver_code"],
                "location": dict(loc) if loc else None,
            }
        )
    return jsonify(result)


# ---------------------------------------------------------------------------
# Driver journey + location API
# ---------------------------------------------------------------------------

@app.route("/api/driver/journey/start", methods=["POST"])
@driver_required
def journey_start():
    db = get_db()
    bus = db.execute(
        "SELECT * FROM buses WHERE assigned_driver_id = ?", (session["driver_id"],)
    ).fetchone()
    if not bus:
        return jsonify({"error": "No bus is assigned to this driver yet. Contact your admin."}), 400

    db.execute("UPDATE buses SET journey_status = 'in_progress' WHERE id = ?", (bus["id"],))
    db.commit()
    return jsonify({"ok": True, "bus_number": bus["bus_number"]})


@app.route("/api/driver/journey/end", methods=["POST"])
@driver_required
def journey_end():
    db = get_db()
    bus = db.execute(
        "SELECT * FROM buses WHERE assigned_driver_id = ?", (session["driver_id"],)
    ).fetchone()
    if not bus:
        return jsonify({"error": "No bus is assigned to this driver."}), 400

    db.execute("UPDATE buses SET journey_status = 'ended' WHERE id = ?", (bus["id"],))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/driver/location", methods=["POST"])
@driver_required
def post_location():
    data = request.get_json(silent=True) or {}
    lat = data.get("latitude")
    lng = data.get("longitude")
    if lat is None or lng is None:
        return jsonify({"error": "latitude and longitude are required."}), 400

    db = get_db()
    bus = db.execute(
        "SELECT * FROM buses WHERE assigned_driver_id = ?", (session["driver_id"],)
    ).fetchone()
    if not bus:
        return jsonify({"error": "No bus is assigned to this driver."}), 400

    db.execute(
        "INSERT INTO locations (bus_id, driver_id, latitude, longitude, timestamp, journey_status) VALUES (?, ?, ?, ?, ?, ?)",
        (bus["id"], session["driver_id"], lat, lng, now_iso(), bus["journey_status"]),
    )
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Public tracking API (no login required)
# ---------------------------------------------------------------------------

@app.route("/api/buses", methods=["GET"])
def public_bus_list():
    db = get_db()
    rows = db.execute(
        "SELECT bus_number, route, journey_status FROM buses ORDER BY bus_number"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/location/<bus_number>", methods=["GET"])
def public_location(bus_number):
    db = get_db()
    bus = db.execute(
        "SELECT * FROM buses WHERE bus_number = ?", (bus_number,)
    ).fetchone()
    if not bus:
        return jsonify({"error": "Bus not found."}), 404

    loc = db.execute(
        "SELECT latitude, longitude, timestamp FROM locations WHERE bus_id = ? ORDER BY id DESC LIMIT 1",
        (bus["id"],),
    ).fetchone()

    driver = None
    if bus["assigned_driver_id"]:
        driver = db.execute(
            "SELECT name FROM drivers WHERE id = ?", (bus["assigned_driver_id"],)
        ).fetchone()

    return jsonify(
        {
            "bus_number": bus["bus_number"],
            "route": bus["route"],
            "journey_status": bus["journey_status"],
            "driver_name": driver["name"] if driver else None,
            "location": dict(loc) if loc else None,
        }
    )


if __name__ == "__main__":
    import shutil
    db_bak = os.path.join(BASE_DIR, "busguard.db.bak")
    if os.path.exists(DB_PATH) and not os.path.exists(db_bak):
        # We need to migrate/recreate because the existing DB has an outdated schema
        # Missing created_at, password_hash instead of password, etc.
        shutil.move(DB_PATH, db_bak)

    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
