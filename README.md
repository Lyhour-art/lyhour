
# KAIRA — Minimal Flask Store

A professional-looking Flask + SQLite mini store with:
- Product grid (id, name, category, price, image, description)
- Category badge on image (top-left)
- Product details page with "More products" excluding current
- Admin area: dashboard, list, add, edit, delete
- Admin login + sign out (default `admin` / `admin123`)

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install flask
python app.py
```

Visit http://localhost:5000

### Admin login
Default credentials:
- **Username:** `admin`
- **Password:** `admin123`

(You can override with environment variables `ADMIN_USER` and `ADMIN_PASS`.)

### Images
New product images are uploaded to `static/uploads/`. A sample image is preloaded.
