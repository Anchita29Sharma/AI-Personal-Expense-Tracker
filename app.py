from flask import Flask, render_template, request, send_file, redirect, session
import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import os

app = Flask(__name__)
app.secret_key = "expense-secret-key"

# ---------------- INIT DATABASE ----------------
def init_db():
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # EXPENSES TABLE ✅ (THIS WAS MISSING)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        category TEXT,
        amount REAL,
        description TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- DATABASE CONNECTION ----------------
def get_db_connection():
    conn = sqlite3.connect("expenses.db")
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = username
            return redirect("/")
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
            conn.close()
            return redirect("/login")
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("signup.html", error="Username already exists")

    return render_template("signup.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    expenses = conn.execute("SELECT * FROM expenses").fetchall()
    conn.close()

    total = sum(e["amount"] for e in expenses) if expenses else 0

    categories = {}
    for e in expenses:
        categories[e["category"]] = categories.get(e["category"], 0) + e["amount"]

    top_category = max(categories, key=categories.get) if categories else "N/A"

    chart_labels = list(categories.keys())
    chart_values = list(categories.values())

    monthly_labels, monthly_values = [], []
    if expenses:
        df = pd.DataFrame(expenses, columns=expenses[0].keys())
        df["date"] = pd.to_datetime(df["date"])
        monthly = df.groupby(df["date"].dt.to_period("M"))["amount"].sum()
        monthly_labels = [str(m) for m in monthly.index]
        monthly_values = monthly.values.tolist()

    return render_template(
        "dashboard.html",
        total=total,
        category=top_category,
        chart_labels=chart_labels,
        chart_values=chart_values,
        monthly_labels=monthly_labels,
        monthly_values=monthly_values
    )

# ---------------- ADD EXPENSE ----------------
@app.route("/add", methods=["GET", "POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO expenses (date, category, amount, description) VALUES (?, ?, ?, ?)",
            (
                request.form["date"],
                request.form["category"],
                request.form["amount"],
                request.form["description"]
            )
        )
        conn.commit()
        conn.close()
        return redirect("/history")

    return render_template("add_expense.html")

# ---------------- HISTORY ----------------
@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/login")

    page = int(request.args.get("page", 1))
    search = request.args.get("search", "")
    limit = 5
    offset = (page - 1) * limit

    conn = get_db_connection()
    expenses = conn.execute(
        """
        SELECT * FROM expenses
        WHERE category LIKE ? OR description LIKE ?
        ORDER BY date DESC
        LIMIT ? OFFSET ?
        """,
        (f"%{search}%", f"%{search}%", limit, offset)
    ).fetchall()
    conn.close()

    return render_template(
        "history.html",
        expenses=expenses,
        page=page,
        search=search
    )


    return render_template("history.html", expenses=expenses)

# ---------------- AI INSIGHTS ----------------
@app.route("/insights")
def insights():
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()

    if df.empty:
        return render_template("insights.html", insight="No data available", prediction="N/A")

    category_sum = df.groupby("category")["amount"].sum()
    top_category = category_sum.idxmax()

    df["day_index"] = np.arange(len(df))
    model = LinearRegression()
    model.fit(df[["day_index"]], df["amount"])

    prediction = round(model.predict([[df["day_index"].max() + 1]])[0], 2)

    return render_template(
        "insights.html",
        insight=f"Highest spending on {top_category}",
        prediction=prediction
    )

# ---------------- EXPORT ----------------
@app.route("/export")
def export():
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()

    df.to_csv("expenses_export.csv", index=False)
    return send_file("expenses_export.csv", as_attachment=True)

