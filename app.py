from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from collections import defaultdict
import os
import requests

# ------------------ APP ------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'change_this_secret')

# ------------------ DATABASE ------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_PATH, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(INSTANCE_PATH, 'orders.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- Admin credentials ----------
ADMIN_USERNAME = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASS', 'password123')

# ------------------ MODELS ------------------
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), unique=True, index=True)
    customer_name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    phone = db.Column(db.String(40))
    address = db.Column(db.String(400))
    status = db.Column(db.String(50), default="Pending")
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    map_link = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("OrderItem", backref="order", lazy=True)

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "customer_name": self.customer_name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "status": self.status,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "map_link": self.map_link,
            "created_at": self.created_at.isoformat(),
            "items": [{"name": i.item_name, "quantity": i.quantity, "price": i.price} for i in self.items]
        }

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    item_name = db.Column(db.String(200))
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0)

# ------------------ HELPERS ------------------
def generate_order_id(db_id=None):
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"ORD-{now}-{db_id}" if db_id else f"ORD-{now}"

# ------------------ ROUTES ------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/menu")
def menu_page():
    sheet_id = "17AU1Y2rc1gfdrTovzxUHJ_cRazph_roberLPrJhIWWg"
    sheet_name = "Sheet1"
    url = f"https://opensheet.elk.sh/{sheet_id}/{sheet_name}"

    try:
        data = requests.get(url).json()
    except Exception as e:
        print("Error fetching sheet:", e)
        data = []

    menu_by_cat = defaultdict(list)
    categories = []

    for idx, item in enumerate(data):
        category = item.get("category", "Uncategorized")
        if category not in categories:
            categories.append(category)
        try:
            price = int(item.get("price", 0))
        except:
            price = 0
        menu_by_cat[category].append({
            "id": idx + 1,
            "name": item.get("name", ""),
            "price": price,
            "image": item.get("image", "")
        })

    return render_template("menu.html", menu_by_category=menu_by_cat, categories=categories)

@app.route("/cart")
def cart_page():
    return render_template("cart.html")

@app.route("/place_order", methods=["POST"])
def place_order():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    latitude = request.form.get("latitude") or None
    longitude = request.form.get("longitude") or None
    map_link = request.form.get("map_link") or None
    item_names = request.form.getlist("item_name[]")
    quantities = request.form.getlist("quantity[]")
    prices = request.form.getlist("price[]")

    if not (name and phone and item_names):
        flash("Please provide name, phone and at least one item.", "danger")
        return redirect(url_for("cart_page"))

    new_order = Order(
        customer_name=name, email=email, phone=phone, address=address,
        latitude=latitude, longitude=longitude, map_link=map_link
    )
    db.session.add(new_order)
    db.session.commit()

    new_order.order_id = generate_order_id(new_order.id)
    db.session.commit()

    for i, item_name in enumerate(item_names):
        qty = int(quantities[i]) if quantities[i].isdigit() else 1
        price = float(prices[i])
        db.session.add(OrderItem(order_id=new_order.id, item_name=item_name, quantity=qty, price=price))

    db.session.commit()
    flash(f"Order placed successfully! Your Order ID: {new_order.order_id}", "success")
    return redirect(url_for("my_orders"))

@app.route("/myorders", methods=["GET", "POST"])
def my_orders():
    orders = []
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        if phone:
            orders = Order.query.filter_by(phone=phone).order_by(Order.created_at.desc()).all()
        elif email:
            orders = Order.query.filter_by(email=email).order_by(Order.created_at.desc()).all()
    return render_template("myorders.html", orders=orders)

# ------------------ Admin ------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin_dashboard.html", orders=orders)

@app.route("/admin/update_status/<int:order_db_id>", methods=["POST"])
def update_status(order_db_id):
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Not authorized"}), 403
    new_status = request.form.get("status")
    order = Order.query.get_or_404(order_db_id)
    order.status = new_status
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/api/order_status/<order_id>", methods=["GET"])
def api_order_status(order_id):
    o = Order.query.filter_by(order_id=order_id).first()
    if not o:
        return jsonify({"success": False, "message": "Order not found"}), 404
    return jsonify({"success": True, "order": o.to_dict()})

# ------------------ RUN ------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Ensure database & tables exist
    app.run(debug=True, host="0.0.0.0", port=5000)
