from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from collections import defaultdict
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, requests, random

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
class DeliveryPerson(db.Model):
    __tablename__ = "delivery_person"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)

    username = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(255))

    orders = db.relationship("Order", backref="delivery_person", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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
    otp = db.Column(db.String(6), nullable=True)
    delivery_person_id = db.Column(db.Integer, db.ForeignKey("delivery_person.id"), nullable=True)
    items = db.relationship("OrderItem", backref="order", lazy=True)

    def total_price(self):
        return sum(float(i.price) * int(i.quantity) for i in self.items)

# ------------------ UTILS ------------------
def generate_order_id(db_id):
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"ORD-{now}-{db_id}"

def generate_otp():
    return str(random.randint(100000, 999999))

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

@app.route("/cart")
def cart_page():
    return render_template("cart.html")
# ------------------ orders place------------------

@app.route("/place_order", methods=["POST"])
def place_order():

    # ===== DEBUGGING START =====
    import pprint
    print("\n\n================ DEBUG FORM DATA ================")
    pprint.pprint(request.form.to_dict(flat=False))
    print("================ END DEBUG ======================\n\n")
    # ===== DEBUGGING END =====

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
        map_link=request.form.get("map_link") or None,
        otp=generate_otp()
    )

    db.session.add(new_order)
    db.session.commit()

    new_order.order_id = generate_order_id(new_order.id)
    db.session.commit()

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

    flash(f"Order placed! OTP for delivery: {new_order.otp}", "success")
    return redirect(url_for("myorders"))



@app.route("/myorders", methods=["GET", "POST"])
def myorders():
    orders = []
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        query = Order.query
        if phone:
            query = query.filter(Order.phone == phone)
        elif email:
            query = query.filter(Order.email == email)
        orders = query.order_by(Order.created_at.desc()).all()
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

@app.route("/admin/add_delivery_person", methods=["GET", "POST"])
def add_delivery_person():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        name = request.form.get("name").strip()
        phone = request.form.get("phone").strip()
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()

        if not all([name, phone, password]):
            flash("Name, phone, and password are required!", "danger")
            return redirect(url_for("add_delivery_person"))

        # Auto-generate username if blank
        if not username:
            username = name.lower().replace(" ", "")
        
        # Check uniqueness
        if DeliveryPerson.query.filter_by(phone=phone).first():
            flash("Phone number already exists!", "danger")
            return redirect(url_for("add_delivery_person"))

        if DeliveryPerson.query.filter_by(username=username).first():
            flash("Username already taken!", "danger")
            return redirect(url_for("add_delivery_person"))

        dp = DeliveryPerson(
            name=name,
            phone=phone,
            username=username
        )
        dp.set_password(password)

        db.session.add(dp)
        db.session.commit()

        flash(f"Delivery person {name} added! Username: {username}", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("add_delivery_person.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    # ---- GET FILTER VALUES ----
    query = request.args.get("query", "")
    status_filter = request.args.get("status", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    page = request.args.get("page", 1, type=int)

    q = Order.query

    # ---- APPLY SEARCH ----
    if query:
        q = q.filter(
            or_(
                Order.order_id.contains(query),
                Order.customer_name.contains(query),
                Order.phone.contains(query),
                Order.email.contains(query),
            )
        )

    # ---- STATUS FILTER ----
    if status_filter:
        q = q.filter(Order.status == status_filter)

    # ---- DATE FILTER ----
    if start_date:
        q = q.filter(Order.created_at >= start_date)
    if end_date:
        q = q.filter(Order.created_at <= end_date)

    q = q.order_by(Order.created_at.desc())

    # ---- PAGINATION ----
    pagination = q.paginate(page=page, per_page=10)
    orders = pagination.items

    delivery_persons = DeliveryPerson.query.order_by(DeliveryPerson.name).all()

    return render_template(
        "admin_dashboard.html",
        orders=orders,
        delivery_persons=delivery_persons,
        pagination=pagination,
        query=query,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date
    )

@app.route("/admin/assign_delivery/<int:order_id>", methods=["POST"])
def assign_delivery(order_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    order = Order.query.get_or_404(order_id)
    dp_id = request.form.get("delivery_person_id")
    if dp_id:
        order.delivery_person_id = int(dp_id)
        order.status = "Accepted"
        db.session.commit()
        flash(f"Order {order.order_id} assigned successfully!", "success")
    else:
        flash("Select a delivery person!", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/update_status/<int:order_id>", methods=["POST"])
def update_status(order_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status")
    if new_status:
        order.status = new_status
        db.session.commit()
        flash(f"Order {order.order_id} status updated!", "success")
    return redirect(url_for("admin_dashboard"))

# ------------------ DELIVERY ------------------
@app.route("/delivery/login", methods=["GET", "POST"])
def delivery_login():
    if request.method == "POST":
        phone = request.form.get("phone")
        password = request.form.get("password")
        dp = DeliveryPerson.query.filter_by(phone=phone).first()
        if dp and dp.check_password(password):
            session["delivery_logged_in"] = True
            session["delivery_person_id"] = dp.id
            session["delivery_person_name"] = dp.name
            return redirect(url_for("delivery_dashboard"))
        flash("Invalid login!", "danger")
    return render_template("delivery_login.html")

@app.route("/delivery/logout")
def delivery_logout():
    session.pop("delivery_logged_in", None)
    session.pop("delivery_person_id", None)
    session.pop("delivery_person_name", None)
    return redirect(url_for("delivery_login"))

@app.route("/delivery/dashboard", methods=["GET", "POST"])
def delivery_dashboard():
    if not session.get("delivery_logged_in"):
        return redirect(url_for("delivery_login"))

    dp_id = session.get("delivery_person_id")
    orders = Order.query.filter(Order.delivery_person_id == dp_id, Order.status != "Delivered").order_by(Order.created_at.asc()).all()

    if request.method == "POST":
        order_id = request.form.get("order_id")
        entered_otp = request.form.get("otp")
        order = Order.query.get(int(order_id))
        if order and order.otp == entered_otp:
            order.status = "Delivered"
            db.session.commit()
            flash(f"Order {order.order_id} marked as Delivered", "success")
        else:
            flash("Invalid OTP!", "danger")
        return redirect(url_for("delivery_dashboard"))

    return render_template("delivery_dashboard.html", orders=orders)

# ------------------ API ------------------
@app.route("/api/order_status/<order_id>")
def get_status(order_id):
    order = Order.query.filter_by(order_id=order_id).first()
    if not order:
        return jsonify({"success": False}), 404
    return jsonify({
        "success": True,
        "order": {
            "order_id": order.order_id,
            "status": order.status,
            "otp": order.otp,
            "total_price": order.total_price()
        }
    })

# ------------------ DB INIT ------------------
with app.app_context():
    db.create_all()

# ------------------ RUN ------------------
if __name__ == "__main__":
    app.run(debug=True)
