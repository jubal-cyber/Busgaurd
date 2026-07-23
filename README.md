# BusGuard V1

A working school-bus live-tracking app: Flask backend + SQLite database, wired
to the BusGuard UI designs (landing page, driver login/dashboard, admin login/dashboard,
and a public tracking page), with a live Leaflet/OpenStreetMap map.

## 1. Install & run

Requires Python 3.9+.

```bash
cd busguard
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000** in your browser.

The database (`busguard.db`) is created automatically on first run, along with
a default admin account:

- **Username:** `BusGuard`
- **Password:** `BusGuard_123`

(Change this password once you've logged in — there's currently no "change
password" UI yet, so for now that just means: don't expose this to the public
internet as-is. Ask me if you'd like a password-change screen added.)

## 2. How the pieces fit together

| Page | Route | Notes |
|---|---|---|
| Landing | `/` | Public. Links to Track Bus, Driver Login, Admin Login. |
| Track a bus | `/track` | Public, no login. Search by bus number, live map updates every 3s. |
| Admin login | `/admin/login` | |
| Admin dashboard | `/admin/dashboard` | Driver Management, Bus Management, Live Bus Tracking, Driver Status, Journey Status, Logout. |
| Driver login | `/driver/login` | |
| Driver dashboard | `/driver/dashboard` | Start Journey → Share Live Location (real GPS) → End Journey. |

Backend REST API (all JSON):

- `POST /api/admin/login`, `POST /api/admin/logout`
- `POST /api/driver/login`, `POST /api/driver/logout`
- `GET/POST /api/admin/drivers`, `PUT/DELETE /api/admin/drivers/<id>`
- `GET/POST /api/admin/buses`, `PUT/DELETE /api/admin/buses/<id>`
- `GET /api/admin/overview` — live map + status data for the admin dashboard
- `POST /api/driver/journey/start`, `POST /api/driver/journey/end`
- `POST /api/driver/location` — driver's browser posts `{latitude, longitude}`
- `GET /api/buses` — public list of registered buses
- `GET /api/location/<bus_number>` — public live location lookup

## 3. First-time walkthrough (matches the roadmap's "Final Demo")

1. Go to `/admin/login`, sign in with `BusGuard` / `BusGuard_123`.
2. In **Bus Management**, add a bus (e.g. `TN-07-BG-21`).
3. In **Driver Management**, add a driver (Driver ID, name, password) — then
   go back to **Bus Management** and assign that driver to the bus (edit the
   bus, or set the driver when adding it).
4. Log out, go to `/driver/login`, sign in as that driver.
5. Click **Start Journey**, then **Share Live Location** — your browser will
   ask for GPS permission. Location pings are sent to the server every ~2.5s.
6. Open `/track` in another tab/device (or as a parent would), enter the bus
   number, and watch the marker move on the map.
7. Back on the admin dashboard, **Live Bus Tracking** / **Driver Status** /
   **Journey Status** show the same thing from the admin's side.
8. Driver clicks **End Journey** when done.

## 4. Important things to know before you rely on this

- **GPS needs a real device.** Browser geolocation only works on `localhost`
  or over HTTPS — it will NOT work if you just open the HTML files directly
  (`file://`) or over plain HTTP on a non-localhost address. Testing on your
  own laptop against `127.0.0.1:5000` is fine; testing on a phone will need
  either HTTPS or a tunnel (e.g. `ngrok`) once you're ready.
- **This is a development server.** `app.py`'s `python3 app.py` uses Flask's
  built-in dev server — great for building/testing, not for production. When
  you're ready to deploy, run it behind something like `gunicorn` and put a
  real webserver (nginx) or a host like Render/Railway in front of it.
- **Passwords are hashed** (not stored in plain text) using Werkzeug's
  password hashing, including the default admin account.
- **Map tiles** come from the free OpenStreetMap tile servers via Leaflet —
  no API key needed, but be considerate of their usage policy if this goes
  into real production use with lots of traffic.

## 5. Natural next steps (say the word and I'll build any of these)

- Edit-driver / edit-bus modals in the admin dashboard (backend routes already exist — `PUT /api/admin/drivers/<id>` and `PUT /api/admin/buses/<id>` — just need a UI form)
- Change-password screen for the admin/driver accounts
- ETA calculation on the tracking page
- Route/waypoint visualization (not just a live dot)
- Deployment config (Dockerfile / gunicorn / Procfile) for your chosen host
