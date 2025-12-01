from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from collections import defaultdict
import json
import os
import requests

# ------------------ APP ------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "change_this_secret"

# ------------------ DATABASE ------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_PATH = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_PATH, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(INSTANCE_PATH, "orders.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ------------------ ADMIN CONFIG ------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

# ------------------ MODELS ------------------
class OrderItem(db.Model):
    __tablename__ = "order_item"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    item_name = db.Column(db.String(200))
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0.0)


class Order(db.Model):
    __tablename__ = "order"

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

    # 🔥 FIXED — always calculates correct total dynamically
    def total_price(self):
        return sum(float(i.price) * int(i.quantity) for i in self.items)


# ------------------ UTILS ------------------
def generate_order_id(db_id):
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"ORD-{now}-{db_id}"


# ------------------ ROUTES ------------------
@app.route("/")
def home():
    return render_template("index.html")


# ------------------ MENU PAGE ------------------
@app.route("/menu")
def menu_page():
    sheet_id = "17AU1Y2rc1gfdrTovzxUHJ_cRazph_roberLPrJhIWWg"
    sheet_name = "Sheet1"
    url = f"https://opensheet.elk.sh/{sheet_id}/{sheet_name}"

    try:
        data = requests.get(url).json()
    except:
        data = []

    categories = []
    menu_by_cat = defaultdict(list)

    for idx, item in enumerate(data):
        category = item.get("category", "Others")
        if category not in categories:
            categories.append(category)

        try:
            price = float(item.get("price", 0))
        except:
            price = 0.0

        menu_by_cat[category].append({
            "id": idx + 1,
            "name": item.get("name", ""),
            "price": price,
            "image": item.get("image", "")
        })

    return render_template("menu.html", menu_by_category=menu_by_cat, categories=categories)


# ------------------ CART ------------------
@app.route("/cart")
def cart_page():
    return render_template("cart.html")


# ------------------ PLACE ORDER ------------------
@app.route("/place_order", methods=["POST"])
def place_order():
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    address = request.form.get("address")

    if not name or not phone:
        flash("Name and phone number are required!", "danger")
        return redirect(url_for("cart_page"))

    item_names = request.form.getlist("item_name[]")
    quantities = request.form.getlist("quantity[]")
    prices = request.form.getlist("price[]")

    new_order = Order(
        customer_name=name,
        email=email,
        phone=phone,
        address=address,
        latitude=request.form.get("latitude") or None,
        longitude=request.form.get("longitude") or None,
        map_link=request.form.get("map_link") or None
    )

    db.session.add(new_order)
    db.session.commit()

    new_order.order_id = generate_order_id(new_order.id)
    db.session.commit()

    # SAVE ITEMS
    for i in range(len(item_names)):
        qty = int(quantities[i]) if quantities[i].isdigit() else 1

        try:
            price = float(prices[i])
        except:
            price = 0.0

        db.session.add(OrderItem(
            order_id=new_order.id,
            item_name=item_names[i],
            quantity=qty,
            price=price
        ))

    db.session.commit()

    return redirect(url_for("my_orders"))


# ------------------ TRACK ORDERS ------------------
@app.route("/myorders", methods=["GET", "POST"])
def my_orders():
    orders = []

    if request.method == "POST":
        phone = request.form.get("phone", "")
        email = request.form.get("email", "")

        if phone:
            orders = Order.query.filter_by(phone=phone).all()
        elif email:
            orders = Order.query.filter_by(email=email).all()

    return render_template("myorders.html", orders=orders)


# ------------------ ADMIN ------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid login", "danger")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    orders = Order.query.order_by(Order.id.desc()).all()
    return render_template("admin_dashboard.html", orders=orders)


@app.route("/admin/update_status/<int:order_db_id>", methods=["POST"])
def update_status(order_db_id):
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Not authorized"}), 403

    order = Order.query.get_or_404(order_db_id)
    new_status = request.form.get("status")
    order.status = new_status
    db.session.commit()
    return redirect(url_for("admin_dashboard"))


# ------------------ API ------------------
@app.route("/api/order_status/<order_id>")
def get_status(order_id):
    order = Order.query.filter_by(order_id=order_id).first()
    if not order:
        return jsonify({"success": False}), 404

    return jsonify({
        "success": True,
        "order": order.to_dict()
    })


# ------------------ MAIN ------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
