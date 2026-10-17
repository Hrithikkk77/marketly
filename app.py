import os
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect

from config import Config
from models import CartItem, Category, Order, OrderItem, Product, User, db

STATUSES = ["placed", "packed", "shipped", "delivered", "cancelled"]


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if not current_user.is_admin:
            abort(403)
        return f(*a, **kw)
    return wrapper


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    CSRFProtect(app)
    lm = LoginManager(app)
    lm.login_view = "login"

    @lm.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    @app.context_processor
    def inject():
        count = 0
        if current_user.is_authenticated:
            count = sum(i.quantity for i in CartItem.query.filter_by(user_id=current_user.id))
        return {"cart_count": count, "categories": Category.query.order_by(Category.name).all()}

    @app.template_filter("money")
    def money(v):
        return f"₹{Decimal(v):,.2f}"

    @app.get("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok"}

    # ---------- storefront ----------
    @app.get("/")
    def index():
        q = request.args.get("q", "").strip()
        cat = request.args.get("category")
        sort = request.args.get("sort", "new")
        page = request.args.get("page", 1, type=int)
        query = Product.query
        if q:
            query = query.filter(Product.name.like(f"%{q}%") | Product.description.like(f"%{q}%"))
        if cat:
            query = query.join(Category).filter(Category.slug == cat)
        order = {"low": Product.price.asc(), "high": Product.price.desc()}.get(sort, Product.id.desc())
        pg = query.order_by(order).paginate(page=page, per_page=app.config["PER_PAGE"], error_out=False)
        return render_template("index.html", pg=pg, q=q, cat=cat, sort=sort)

    @app.get("/product/<int:pid>")
    def product(pid):
        return render_template("product.html", p=db.get_or_404(Product, pid))

    # ---------- auth ----------
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name, email, pw = (request.form.get(k, "").strip() for k in ("name", "email", "password"))
            if not name or "@" not in email or len(pw) < 8:
                flash("Enter your name, a valid email and a password of 8+ characters.", "error")
            elif User.query.filter_by(email=email.lower()).first():
                flash("That email already has an account. Sign in instead.", "error")
            else:
                u = User(name=name, email=email.lower())
                u.set_password(pw)
                db.session.add(u)
                db.session.commit()
                login_user(u)
                return redirect(url_for("index"))
        return render_template("auth.html", mode="register")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            u = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
            if u and u.check_password(request.form.get("password", "")):
                login_user(u)
                nxt = request.args.get("next", "")
                return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
            flash("Email or password is incorrect.", "error")
        return render_template("auth.html", mode="login")

    @app.post("/logout")
    def logout():
        logout_user()
        return redirect(url_for("index"))

    # ---------- cart ----------
    @app.get("/cart")
    @login_required
    def cart():
        items = CartItem.query.filter_by(user_id=current_user.id).all()
        total = sum(i.product.price * i.quantity for i in items)
        return render_template("cart.html", items=items, total=total)

    @app.post("/cart/add/<int:pid>")
    @login_required
    def cart_add(pid):
        p = db.get_or_404(Product, pid)
        qty = max(1, request.form.get("quantity", 1, type=int))
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
        new_qty = (item.quantity if item else 0) + qty
        if new_qty > p.stock:
            flash(f"Only {p.stock} of this item in stock.", "error")
            return redirect(url_for("product", pid=pid))
        if item:
            item.quantity = new_qty
        else:
            db.session.add(CartItem(user_id=current_user.id, product_id=pid, quantity=qty))
        db.session.commit()
        flash("Added to cart.", "ok")
        return redirect(url_for("cart"))

    @app.post("/cart/update/<int:item_id>")
    @login_required
    def cart_update(item_id):
        item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
        qty = request.form.get("quantity", 0, type=int)
        if qty <= 0:
            db.session.delete(item)
        elif qty > item.product.stock:
            flash(f"Only {item.product.stock} in stock.", "error")
        else:
            item.quantity = qty
        db.session.commit()
        return redirect(url_for("cart"))

    # ---------- checkout & orders ----------
    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        items = CartItem.query.filter_by(user_id=current_user.id).all()
        if not items:
            return redirect(url_for("cart"))
        total = sum(i.product.price * i.quantity for i in items)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            addr = request.form.get("address", "").strip()
            if not name or len(addr) < 10:
                flash("Enter a name and a full delivery address.", "error")
                return render_template("checkout.html", items=items, total=total)
            try:
                order = Order(user_id=current_user.id, total=0, shipping_name=name, shipping_address=addr)
                db.session.add(order)
                grand = Decimal("0")
                for i in items:
                    p = Product.query.filter_by(id=i.product_id).with_for_update().one()
                    if p.stock < i.quantity:
                        raise ValueError(f"{p.name} has only {p.stock} left.")
                    p.stock -= i.quantity
                    grand += p.price * i.quantity
                    order.items.append(OrderItem(product_id=p.id, name=p.name, price=p.price, quantity=i.quantity))
                    db.session.delete(i)
                order.total = grand
                db.session.commit()
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "error")
                return redirect(url_for("cart"))
            flash(f"Order #{order.id} placed. Pay on delivery.", "ok")
            return redirect(url_for("orders"))
        return render_template("checkout.html", items=items, total=total)

    @app.get("/orders")
    @login_required
    def orders():
        rows = Order.query.filter_by(user_id=current_user.id).order_by(Order.id.desc()).all()
        return render_template("orders.html", orders=rows)

    # ---------- admin ----------
    @app.get("/admin")
    @admin_required
    def admin():
        return render_template(
            "admin/dashboard.html",
            products=Product.query.order_by(Product.id.desc()).all(),
            orders=Order.query.order_by(Order.id.desc()).limit(50).all(),
            statuses=STATUSES,
        )

    @app.route("/admin/product/new", methods=["GET", "POST"])
    @app.route("/admin/product/<int:pid>", methods=["GET", "POST"])
    @admin_required
    def admin_product(pid=None):
        p = db.get_or_404(Product, pid) if pid else Product()
        if request.method == "POST":
            try:
                p.name = request.form["name"].strip()
                p.category_id = int(request.form["category_id"])
                p.price = Decimal(request.form["price"])
                p.stock = int(request.form["stock"])
                p.description = request.form.get("description", "")
                p.image_url = request.form.get("image_url", "").strip()
                if not p.name or p.price < 0 or p.stock < 0:
                    raise ValueError
            except (ValueError, KeyError, InvalidOperation):
                flash("Check the form: name, category, price and stock are required.", "error")
                return render_template("admin/product_form.html", p=p)
            db.session.add(p)
            db.session.commit()
            flash("Product saved.", "ok")
            return redirect(url_for("admin"))
        return render_template("admin/product_form.html", p=p)

    @app.post("/admin/product/<int:pid>/delete")
    @admin_required
    def admin_delete(pid):
        p = db.get_or_404(Product, pid)
        if OrderItem.query.filter_by(product_id=pid).first():
            p.stock = 0
            flash("Product has orders, so its stock was set to 0 instead of deleting.", "ok")
        else:
            db.session.delete(p)
            flash("Product deleted.", "ok")
        db.session.commit()
        return redirect(url_for("admin"))

    @app.post("/admin/order/<int:oid>/status")
    @admin_required
    def admin_status(oid):
        o = db.get_or_404(Order, oid)
        s = request.form.get("status")
        if s in STATUSES:
            o.status = s
            db.session.commit()
        return redirect(url_for("admin"))

    @app.cli.command("init-db")
    def init_db():
        """Create tables from the models (or run schema.sql instead)."""
        db.create_all()
        print("Tables created.")

    return app
