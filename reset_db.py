from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# ------------------ APP & DB ------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orders.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ------------------ MODELS ------------------
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), unique=True, index=True)
    customer_name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    phone = db.Column(db.String(40))
    address = db.Column(db.String(400))
    item = db.Column(db.String(200))
    quantity = db.Column(db.Integer, default=1)
    status = db.Column(db.String(50), default="Pending")
    
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # ✅ You forgot this
    map_link = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ------------------ RESET DB ------------------
with app.app_context():  # <-- this is required!
    db.drop_all()       # drops all tables
    db.create_all()     # creates all tables according to models
    print("Database has been reset successfully.")
