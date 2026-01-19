from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "expense-secret-key"

DB_NAME = "expenses.db"

# ---------------- INIT DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        category TEXT,
        amount REAL,
        description TEXT,
        user_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- DB CONNECTION ----------------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
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
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

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
    session.clear()
    return redirect("/login")

# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    expenses = conn.execute(
        "SELECT * FROM expenses WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()
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
        df = pd.DataFrame(expenses)
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
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO expenses (date, category, amount, description, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request.form["date"],
                request.form["category"],
                request.form["amount"],
                request.form["description"],
                session["user_id"]
            )
        )
        conn.commit()
        conn.close()
        return redirect("/history")

    return render_template("add_expense.html")

# ---------------- HISTORY ----------------
@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/login")

    page = int(request.args.get("page", 1))
    search = request.args.get("search", "")
    limit = 5
    offset = (page - 1) * limit

    conn = get_db_connection()
    expenses = conn.execute(
        """
        SELECT * FROM expenses
        WHERE user_id=?
        AND (category LIKE ? OR description LIKE ?)
        ORDER BY date DESC
        LIMIT ? OFFSET ?
        """,
        (session["user_id"], f"%{search}%", f"%{search}%", limit, offset)
    ).fetchall()
    conn.close()

    return render_template(
        "history.html",
        expenses=expenses,
        page=page,
        search=search
    )

# ---------------- DELETE EXPENSE (FIXED) ----------------
@app.route("/delete/<int:id>")
def delete(id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM expenses WHERE id=? AND user_id=?",
        (id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect("/history")

# ---------------- AI INSIGHTS ----------------
@app.route("/insights")
def insights():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM expenses WHERE user_id=?",
        conn,
        params=(session["user_id"],)
    )
    conn.close()

    if df.empty:
        return render_template(
            "insights.html",
            insight="No data available yet.",
            prediction="N/A",
            budget_msg="Add expenses to get insights.",
            prediction_note=""
        )

    df["date"] = pd.to_datetime(df["date"])
    category_sum = df.groupby("category")["amount"].sum()
    total_expense = category_sum.sum()

    top_category = category_sum.idxmax()
    percentage = round((category_sum.max() / total_expense) * 100, 2)

    insight = f"Highest spending on {top_category} ({percentage}%)."

    df = df.sort_values("date")
    df["day_index"] = range(len(df))

    model = LinearRegression()
    model.fit(df[["day_index"]], df["amount"])
    prediction = round(model.predict([[df["day_index"].max() + 1]])[0], 2)

    return render_template(
        "insights.html",
        insight=insight,
        prediction=prediction,
        budget_msg="",
        prediction_note="Prediction based on past expenses"
    )

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    expenses = conn.execute(
        "SELECT * FROM expenses WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    total = sum(e["amount"] for e in expenses) if expenses else 0
    count = len(expenses)

    # Category analysis
    categories = {}
    for e in expenses:
        categories[e["category"]] = categories.get(e["category"], 0) + e["amount"]

    top_category = max(categories, key=categories.get) if categories else "N/A"

    # Spending Personality Logic
    avg = total / count if count else 0

    if avg < 500:
        personality = "Saver 🐢"
        msg = "You spend carefully and avoid unnecessary expenses."
    elif avg < 1500:
        personality = "Balanced ⚖️"
        msg = "You maintain a healthy spending balance."
    else:
        personality = "Spender 🔥"
        msg = "You spend more than average. Consider budgeting."

    return render_template(
        "profile.html",
        username=session["user"],
        total=total,
        count=count,
        top_category=top_category,
        personality=personality,
        personality_msg=msg
    )

# ---------------- EXPORT ----------------
@app.route("/export")
def export():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM expenses WHERE user_id=?",
        conn,
        params=(session["user_id"],)
    )
    conn.close()

    df.to_csv("expenses_export.csv", index=False)
    return send_file("expenses_export.csv", as_attachment=True)



