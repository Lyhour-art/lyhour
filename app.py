
import os, sqlite3, secrets
from flask import Flask, render_template, g, redirect, url_for, request, flash, session, send_from_directory, abort

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "store.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=secrets.token_hex(16),
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=10 * 1024 * 1024, # 10MB
)

# --- simple admin credentials ---
ADMIN_USERNAME = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "admin123")

# ---- database helpers ----
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()


def seed_if_empty():
    db = get_db()
    cur = db.execute("SELECT COUNT(*) as c FROM products")
    if cur.fetchone()["c"] == 0:
        items = [
            ("Air Flex Runner","Sneakers",89.0,"https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1080&auto=format&fit=crop","Lightweight running shoe with breathable mesh upper."),
            ("Urban Street Pro","Sneakers",119.0,"https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=1080&auto=format&fit=crop","Premium everyday sneaker with cushioned midsole."),
            ("TrailMaster X","Trail",139.0,"https://images.unsplash.com/photo-1608231387042-66d1773070a5?q=80&w=1080&auto=format&fit=crop","Rugged outsole for off-road grip and stability."),
            ("Court Classic 2","Tennis",99.0,"https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?q=80&w=1080&auto=format&fit=crop","Heritage court silhouette with modern comfort."),
            ("Studio Flow","Training",109.0,"https://images.unsplash.com/photo-1543508282-6319a3e2621f?q=80&w=1080&auto=format&fit=crop","Versatile trainer for gym and HIIT sessions."),
            ("All-Day Comfort","Casual",79.0,"https://images.unsplash.com/photo-1526178611292-66f7e0837fb3?q=80&w=1080&auto=format&fit=crop","Memory foam insole and flexible outsole."),
            ("Marathon Elite","Running",159.0,"https://images.unsplash.com/photo-1519744792095-2f2205e87b6f?q=80&w=1080&auto=format&fit=crop","Carbon plate propulsion and responsive foam."),
            ("Heritage High","Lifestyle",129.0,"https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1080&auto=format&fit=crop","Classic high-top with durable leather overlays."),
            ("Coast Slide","Sandals",49.0,"https://images.unsplash.com/photo-1608231387042-66d1773070a5?q=80&w=1080&auto=format&fit=crop","Comfort slide with contoured footbed."),
            ("City Runner Knit","Running",99.0,"https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=1080&auto=format&fit=crop","Sock-fit knit upper and grippy outsole.")
        ]
        db.executemany("INSERT INTO products(name, category, price, image, description) VALUES(?,?,?,?,?)", items)
        db.commit()
    cur = db.execute("SELECT COUNT(*) as c FROM products")
    if cur.fetchone()["c"] == 0:
        # seed single product
        sample_image = "sample.jpg" if os.path.exists(os.path.join(UPLOAD_FOLDER, "sample.jpg")) else ""
        db.execute("INSERT INTO products(name, category, price, image, description) VALUES(?,?,?,?,?)",
                   ("Soft Leather Jacket", "Outerwear", 129.00, sample_image, 
                    "A minimalist, soft-touch leather jacket designed for everyday wear."))
        db.commit()

# ---- routes ----
@app.route("/")
def home():
    init_db(); seed_if_empty()
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    return render_template("index.html", products=products, title="KAIRA — Store")

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        abort(404)
    more = db.execute("SELECT * FROM products WHERE id != ? ORDER BY created_at DESC LIMIT 6", (product_id,)).fetchall()
    return render_template("product_detail.html", product=product, more_products=more, title=product["name"])

# ---- admin auth ----
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["admin"] = True
            flash("Welcome back.")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials.")
    return render_template("admin_login.html", title="Admin Login")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Signed out.")
    return redirect(url_for("home"))

def require_admin():
    if not session.get("admin"):
        flash("Please sign in as admin.")
        return False
    return True

@app.route("/admin")
def admin_dashboard():
    if not require_admin(): return redirect(url_for("admin_login"))
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM products").fetchone()["c"]
    cats = db.execute("SELECT COUNT(DISTINCT category) as c FROM products").fetchone()["c"]
    latest_row = db.execute("SELECT name FROM products ORDER BY created_at DESC LIMIT 1").fetchone()
    latest = latest_row["name"] if latest_row else "—"
    # Category breakdown
    rows = db.execute("SELECT category, COUNT(*) as c FROM products GROUP BY category ORDER BY c DESC").fetchall()
    cat_labels = [r["category"] for r in rows] or ["—"]
    cat_counts = [r["c"] for r in rows] or [0]
    # Last 14 days
    from datetime import datetime, timedelta
    day_labels = []
    day_counts = []
    today = datetime.utcnow().date()
    counts = { r["d"]: r["c"] for r in db.execute("SELECT DATE(created_at) as d, COUNT(*) as c FROM products WHERE DATE(created_at) >= DATE('now','-20 days') GROUP BY DATE(created_at)").fetchall() }
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        day_labels.append(d.strftime("%d %b"))
        day_counts.append(int(counts.get(key, 0)))
    stats = {"total": total, "categories": cats, "latest": latest, "cat_labels": cat_labels, "cat_counts": cat_counts, "day_labels": day_labels, "day_counts": day_counts}
    return render_template("admin_dashboard.html", stats=stats, title="Admin — Dashboard")

@app.route("/admin/products")
def admin_products():
    if not require_admin(): return redirect(url_for("admin_login"))
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("admin_products.html", products=products, title="Admin — Products")

@app.route("/admin/products/add", methods=["GET","POST"])
def admin_add_product():
    if not require_admin(): return redirect(url_for("admin_login"))
    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form["category"].strip()
        price = float(request.form["price"])
        description = request.form["description"].strip()
        image_filename = None
        url_from_form = request.form.get('image_url','').strip()
        file = request.files.get('image')
        if url_from_form:
            image_filename = url_from_form
        elif file and file.filename:
            image_filename = secure_filename(file.filename)
            save_path = os.path.join(UPLOAD_FOLDER, image_filename)
            file.save(save_path)
        else:
            image_filename = ""
        db = get_db()
        db.execute("INSERT INTO products(name, category, price, image, description) VALUES(?,?,?,?,?)",
                   (name, category, price, image_filename, description))
        db.commit()
        flash("Product created.")
        return redirect(url_for("admin_products"))
    return render_template("admin_product_form.html", product=None, title="Add product")

from werkzeug.utils import secure_filename

@app.route("/admin/products/<int:product_id>/edit", methods=["GET","POST"])
def admin_edit_product(product_id):
    if not require_admin(): return redirect(url_for("admin_login"))
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product: abort(404)
    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form["category"].strip()
        price = float(request.form["price"])
        description = request.form["description"].strip()
        image_filename = product["image"]
        file = request.files.get("image")
        if file and file.filename:
            image_filename = secure_filename(file.filename)
            save_path = os.path.join(UPLOAD_FOLDER, image_filename)
            file.save(save_path)
        db.execute("UPDATE products SET name=?, category=?, price=?, image=?, description=? WHERE id=?",
                   (name, category, price, image_filename, description, product_id))
        db.commit()
        flash("Product updated.")
        return redirect(url_for("admin_products"))
    return render_template("admin_product_form.html", product=product, title="Edit product")

@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
def admin_delete_product(product_id):
    if not require_admin(): return redirect(url_for("admin_login"))
    db = get_db()
    db.execute("DELETE FROM products WHERE id=?", (product_id,))
    db.commit()
    flash("Product deleted.")
    return redirect(url_for("admin_products"))

if __name__ == "__main__":
    with app.app_context():
        init_db(); seed_if_empty()
    app.run(host="0.0.0.0", port=5000, debug=True)
