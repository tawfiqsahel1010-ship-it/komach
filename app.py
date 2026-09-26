import os
import sqlite3
from functools import wraps
from datetime import datetime

from flask import Flask, request, redirect, url_for, session, render_template, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "KUMACH_PAZI_DEV_SECRET"
)

DATABASE_URL = os.environ.get("DATABASE_URL")
DB = "kumach.db"


# =========================
# DATABASE
# =========================

class DBConnection:
    def __init__(self):
        self.postgres = bool(DATABASE_URL)

        if self.postgres:
            import psycopg2
            from psycopg2.extras import DictCursor

            self.conn = psycopg2.connect(
                DATABASE_URL,
                cursor_factory=DictCursor
            )
        else:
            self.conn = sqlite3.connect(DB)
            self.conn.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        if self.postgres:
            sql = sql.replace("?", "%s")

        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def executescript(self, script):
        if self.postgres:
            statements = [
                x.strip()
                for x in script.split(";")
                if x.strip()
            ]

            for statement in statements:
                statement = statement.replace(
                    "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "SERIAL PRIMARY KEY"
                )
                self.conn.execute(statement)
        else:
            self.conn.executescript(script)


def db():
    return DBConnection()


# =========================
# DATABASE INIT
# =========================

def init_db():
    c = db()

    if DATABASE_URL:
        schema = """
        CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        );

        CREATE TABLE IF NOT EXISTS foods(
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            price INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sales(
            id SERIAL PRIMARY KEY,
            food_id INTEGER,
            quantity INTEGER,
            price INTEGER,
            total INTEGER,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS expenses(
            id SERIAL PRIMARY KEY,
            title TEXT,
            amount INTEGER,
            note TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS customers(
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            debt INTEGER DEFAULT 0
        );
        """
    else:
        schema = """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        );

        CREATE TABLE IF NOT EXISTS foods(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sales(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id INTEGER,
            quantity INTEGER,
            price INTEGER,
            total INTEGER,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            amount INTEGER,
            note TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            debt INTEGER DEFAULT 0
        );
        """

    c.executescript(schema)

    # Default owner
    owner = c.execute(
        "SELECT * FROM users WHERE username=?",
        ("owner",)
    ).fetchone()

    if not owner:
        c.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            (
                "owner",
                generate_password_hash("1234"),
                "owner"
            )
        )

    # Default worker
    worker = c.execute(
        "SELECT * FROM users WHERE username=?",
        ("worker",)
    ).fetchone()

    if not worker:
        c.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            (
                "worker",
                generate_password_hash("1234"),
                "worker"
            )
        )

    foods = [
        ("بولانی", 42),
        ("منتو", 80),
        ("آشک", 70),
        ("آی خانم", 50),
        ("گل خانم", 50),
        ("کوماچ", 50),
    ]

    for name, price in foods:
        try:
            c.execute(
                "INSERT INTO foods(name,price) VALUES(?,?)",
                (name, price)
            )
        except Exception:
            pass

    c.commit()
    c.close()


# =========================
# LOGIN HELPERS
# =========================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return wrapper


def owner_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "owner":
            flash("این بخش فقط برای مالک است.")
            return redirect(url_for("dashboard"))

        return f(*args, **kwargs)

    return wrapper


# =========================
# HOME / LOGIN
# =========================

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        c = db()

        user = c.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user:

            stored_password = user["password"]

            valid = False

            # Passwords created by the new system
            try:
                valid = check_password_hash(
                    stored_password,
                    password
                )
            except Exception:
                valid = False

            # Compatibility with old SQLite passwords
            if not valid and stored_password == password:

                new_password = generate_password_hash(password)

                c.execute(
                    "UPDATE users SET password=? WHERE id=?",
                    (new_password, user["id"])
                )

                c.commit()
                valid = True

            if valid:

                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]

                c.close()

                return redirect(url_for("dashboard"))

        c.close()

        flash("نام کاربری یا رمز اشتباه است.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
@login_required
def dashboard():

    c = db()

    sales = c.execute(
        "SELECT COALESCE(SUM(total),0) FROM sales"
    ).fetchone()[0]

    expenses = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses"
    ).fetchone()[0]

    debt = c.execute(
        "SELECT COALESCE(SUM(debt),0) FROM customers"
    ).fetchone()[0]

    foods = c.execute(
        "SELECT * FROM foods ORDER BY name"
    ).fetchall()

    recent_sales = c.execute("""
        SELECT sales.*, foods.name food_name
        FROM sales
        JOIN foods ON foods.id=sales.food_id
        ORDER BY sales.id DESC
        LIMIT 20
    """).fetchall()

    recent_expenses = c.execute("""
        SELECT * FROM expenses
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    customers = c.execute(
        "SELECT * FROM customers ORDER BY name"
    ).fetchall()

    c.close()

    return render_template(
        "dashboard.html",
        sales=sales,
        expenses=expenses,
        profit=sales - expenses,
        debt=debt,
        foods=foods,
        recent_sales=recent_sales,
        recent_expenses=recent_expenses,
        customers=customers
    )


# =========================
# FOODS
# =========================

@app.route("/food/add", methods=["POST"])
@login_required
def add_food():

    name = request.form["name"].strip()
    price = int(request.form["price"])

    c = db()

    try:
        c.execute(
            "INSERT INTO foods(name,price) VALUES(?,?)",
            (name, price)
        )

        c.commit()
        flash("غذا اضافه شد.")

    except Exception:
        flash("این غذا قبلاً وجود دارد.")

    c.close()

    return redirect(url_for("dashboard"))


@app.route("/food/edit/<int:id>", methods=["POST"])
@login_required
def edit_food(id):

    name = request.form["name"].strip()
    price = int(request.form["price"])

    c = db()

    c.execute(
        "UPDATE foods SET name=?,price=? WHERE id=?",
        (name, price, id)
    )

    c.commit()
    c.close()

    flash("غذا و قیمت آن تغییر کرد.")

    return redirect(url_for("dashboard"))


@app.route("/food/delete/<int:id>")
@owner_required
def delete_food(id):

    c = db()

    c.execute(
        "DELETE FROM foods WHERE id=?",
        (id,)
    )

    c.commit()
    c.close()

    flash("غذا حذف شد.")

    return redirect(url_for("dashboard"))


# =========================
# SALES
# =========================

@app.route("/sale/add", methods=["POST"])
@login_required
def add_sale():

    food_id = int(request.form["food_id"])
    quantity = int(request.form["quantity"])

    c = db()

    food = c.execute(
        "SELECT * FROM foods WHERE id=?",
        (food_id,)
    ).fetchone()

    if food:

        total = food["price"] * quantity

        c.execute("""
            INSERT INTO sales(
                food_id,
                quantity,
                price,
                total,
                created_at
            )
            VALUES(?,?,?,?,?)
        """, (
            food_id,
            quantity,
            food["price"],
            total,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

        c.commit()

        flash("فروش ثبت شد.")

    c.close()

    return redirect(url_for("dashboard"))


@app.route("/sale/delete/<int:id>")
@login_required
def delete_sale(id):

    c = db()

    c.execute(
        "DELETE FROM sales WHERE id=?",
        (id,)
    )

    c.commit()
    c.close()

    flash("فروش حذف شد.")

    return redirect(url_for("dashboard"))


# =========================
# EXPENSES
# =========================

@app.route("/expense/add", methods=["POST"])
@login_required
def add_expense():

    title = request.form["title"].strip()
    amount = int(request.form["amount"])
    note = request.form.get("note", "").strip()

    c = db()

    c.execute("""
        INSERT INTO expenses(
            title,
            amount,
            note,
            created_at
        )
        VALUES(?,?,?,?)
    """, (
        title,
        amount,
        note,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))

    c.commit()
    c.close()

    flash("مصرف ثبت شد.")

    return redirect(url_for("dashboard"))


@app.route("/expense/delete/<int:id>")
@login_required
def delete_expense(id):

    c = db()

    c.execute(
        "DELETE FROM expenses WHERE id=?",
        (id,)
    )

    c.commit()
    c.close()

    flash("مصرف حذف شد.")

    return redirect(url_for("dashboard"))


# =========================
# CUSTOMERS
# =========================

@app.route("/customer/add", methods=["POST"])
@login_required
def add_customer():

    name = request.form["name"].strip()
    debt = int(request.form["debt"])

    c = db()

    try:

        c.execute(
            "INSERT INTO customers(name,debt) VALUES(?,?)",
            (name, debt)
        )

        c.commit()

        flash("مشتری ثبت شد.")

    except Exception:

        flash("این مشتری قبلاً ثبت شده.")

    c.close()

    return redirect(url_for("dashboard"))


@app.route("/customer/pay/<int:id>", methods=["POST"])
@login_required
def customer_pay(id):

    amount = int(request.form["amount"])

    c = db()

    customer = c.execute(
        "SELECT * FROM customers WHERE id=?",
        (id,)
    ).fetchone()

    if customer:

        new_debt = max(
            0,
            customer["debt"] - amount
        )

        c.execute(
            "UPDATE customers SET debt=? WHERE id=?",
            (new_debt, id)
        )

        c.commit()

    c.close()

    flash("پرداخت ثبت شد.")

    return redirect(url_for("dashboard"))


@app.route("/customer/delete/<int:id>")
@login_required
def delete_customer(id):

    c = db()

    c.execute(
        "DELETE FROM customers WHERE id=?",
        (id,)
    )

    c.commit()
    c.close()

    flash("مشتری حذف شد.")

    return redirect(url_for("dashboard"))


# =========================
# USERS / OWNER
# =========================

@app.route("/users", methods=["GET", "POST"])
@owner_required
def users():

    c = db()

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        try:

            hashed_password = generate_password_hash(password)

            c.execute(
                """
                INSERT INTO users(
                    username,
                    password,
                    role
                )
                VALUES(?,?,?)
                """,
                (
                    username,
                    hashed_password,
                    "worker"
                )
            )

            c.commit()

            flash("کاربر جدید ساخته شد.")

        except Exception:

            flash("این نام کاربری قبلاً وجود دارد.")

    users = c.execute(
        "SELECT id,username,role FROM users"
    ).fetchall()

    c.close()

    return render_template(
        "users.html",
        users=users
    )


@app.route("/user/delete/<int:id>")
@owner_required
def delete_user(id):

    c = db()

    user = c.execute(
        "SELECT * FROM users WHERE id=?",
        (id,)
    ).fetchone()

    if user and user["role"] != "owner":

        c.execute(
            "DELETE FROM users WHERE id=?",
            (id,)
        )

        c.commit()

    c.close()

    return redirect(url_for("users"))


# =========================
# START
# =========================

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
