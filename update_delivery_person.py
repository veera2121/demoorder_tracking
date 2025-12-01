from app import app, db, DeliveryPerson
from werkzeug.security import generate_password_hash

with app.app_context():
    # Step 1: Add new columns
    with db.engine.begin() as conn:
        try:
            conn.execute(
                "ALTER TABLE delivery_person ADD COLUMN password_hash VARCHAR(255);"
            )
            print("Added password_hash column")
        except Exception as e:
            print("password_hash column already exists or error:", e)

        try:
            conn.execute(
                "ALTER TABLE delivery_person ADD COLUMN username VARCHAR(100) UNIQUE;"
            )
            print("Added username column")
        except Exception as e:
            print("username column already exists or error:", e)

    # Step 2: Update existing delivery persons
    for dp in DeliveryPerson.query.all():
        if not dp.username:
            dp.username = dp.name.lower().replace(" ", "")
        if not dp.password_hash:
            dp.password_hash = generate_password_hash("default123")

    db.session.commit()
    print("Updated existing delivery persons with default username/password")
