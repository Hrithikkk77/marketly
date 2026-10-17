"""Create tables, the admin user and sample catalog. Safe to re-run."""
import os

from app import create_app
from models import Category, Product, User, db

app = create_app()
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        raise SystemExit(f"Cannot reach the database: {e}\nRun 'python create_database.py' first and check your .env.")
    email = os.environ["ADMIN_EMAIL"].lower()
    if not User.query.filter_by(email=email).first():
        a = User(name="Admin", email=email, is_admin=True)
        a.set_password(os.environ["ADMIN_PASSWORD"])
        db.session.add(a)
    if not Category.query.first():
        cats = {s: Category(name=n, slug=s) for s, n in [
            ("electronics", "Electronics"), ("books", "Books"), ("home", "Home & Kitchen"), ("fashion", "Fashion")]}
        db.session.add_all(cats.values())
        db.session.flush()
        sample = [
            ("electronics", "Wireless Earbuds", "Bluetooth 5.3, 24-hour battery.", 1999, 50),
            ("electronics", "Mechanical Keyboard", "Hot-swappable switches, USB-C.", 4499, 25),
            ("electronics", "20,000 mAh Power Bank", "Fast charging, dual output.", 1799, 80),
            ("books", "Python Crash Course", "A hands-on introduction to programming.", 899, 120),
            ("books", "Atomic Habits", "Small changes, remarkable results.", 499, 200),
            ("home", "Stainless Steel Bottle", "1 litre, keeps drinks cold for 24 hours.", 649, 150),
            ("home", "Non-stick Cookware Set", "3-piece induction-friendly set.", 2299, 40),
            ("fashion", "Cotton Crew T-Shirt", "Soft 100% cotton, regular fit.", 499, 300),
            ("fashion", "Running Shoes", "Lightweight mesh, cushioned sole.", 2799, 60),
        ]
        for slug, name, desc, price, stock in sample:
            db.session.add(Product(category_id=cats[slug].id, name=name, description=desc, price=price, stock=stock))
    db.session.commit()
    print("Seed complete.")
