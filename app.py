from flask import Flask, render_template, request, send_file, redirect, session
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

# ---------------- DATABASE CONNECTION ----------------
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
            session["user"] = user["username"]
            session["user_id"] = user["id"]
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
        "SELECT date, category, amount FROM expenses WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    # ---- TOTAL ----
    total = 0
    categories = {}

    safe_data = []

    for e in expenses:
        try:
            amount = float(e["amount"])
            total += amount

            categories[e["category"]] = categories.get(e["category"], 0) + amount

            safe_data.append({
                "date": e["date"],
                "amount": amount
            })
        except:
            continue   # skip broken rows safely

    top_category = max(categories, key=categories.get) if categories else "N/A"

    chart_labels = list(categories.keys())
    chart_values = list(categories.values())

    # ---- MONTHLY TREND (100% SAFE) ----
    monthly_labels = []
    monthly_values = []

    if safe_data:
        df = pd.DataFrame(safe_data)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna()

        if not df.empty:
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
            insight="No expenses added yet.",
            prediction="N/A",
            personality="Not enough data",
            personality_msg="Add expenses to see your spending personality."
        )

    # ---------------- BASIC CALCULATIONS ----------------
    avg_spend = df["amount"].mean()
    max_spend = df["amount"].max()

    # ---------------- PERSONALITY LOGIC ----------------
    if max_spend > 3 * avg_spend:
        personality = "🔥 Impulsive Spender"
        personality_msg = "You make sudden high-value purchases. Try planning expenses."
    elif avg_spend < 300:
        personality = "🐢 Saver"
        personality_msg = "You spend carefully and save well. Great discipline!"
    elif 300 <= avg_spend <= 800:
        personality = "⚖️ Balanced Spender"
        personality_msg = "Your spending is healthy and well-managed."
    else:
        personality = "🐅 Spender"
        personality_msg = "You spend more than average. Consider budgeting."

    # ---------------- SIMPLE INSIGHT ----------------
    insight = f"Your average spending per expense is ₹{round(avg_spend, 2)}."

    return render_template(
        "insights.html",
        insight=insight,
        prediction="N/A",
        personality=personality,
        personality_msg=personality_msg
    )


    # ----- PREPARE DATA -----
    df["date"] = pd.to_datetime(df["date"])

    # ----- CATEGORY ANALYSIS -----
    category_sum = df.groupby("category")["amount"].sum()
    total_expense = category_sum.sum()

    top_category = category_sum.idxmax()
    top_amount = category_sum.max()
    percentage = round((top_amount / total_expense) * 100, 2)

    if percentage >= 50:
        insight = f"⚠️ You are heavily overspending on {top_category} ({percentage}% of total expenses)."
    elif percentage >= 30:
        insight = f"⚠️ {top_category} is your major expense area ({percentage}%). Keep an eye on it."
    else:
        insight = f"✅ Your expenses are well balanced. Highest spending is on {top_category} ({percentage}%)."

    # ----- MONTHLY BUDGET CHECK -----
    monthly_budget = 10000  # you can change this
    current_month = df["date"].dt.to_period("M").max()
    current_month_total = df[df["date"].dt.to_period("M") == current_month]["amount"].sum()

    if current_month_total > monthly_budget:
        budget_msg = f"🚨 You have exceeded your monthly budget of ₹{monthly_budget}."
    else:
        budget_msg = f"✅ You are within your monthly budget of ₹{monthly_budget}."

    # ----- ML PREDICTION -----
    df = df.sort_values("date")
    df["day_index"] = range(len(df))

    model = LinearRegression()
    model.fit(df[["day_index"]], df["amount"])

    next_day = [[df["day_index"].max() + 1]]
    prediction = round(model.predict(next_day)[0], 2)

    prediction_note = "Prediction is based on your past spending trend using Linear Regression."

    return render_template(
        "insights.html",
        insight=insight,
        prediction=prediction,
        budget_msg=budget_msg,
        prediction_note=prediction_note
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


# ---------------- DELETE EXPENSE ----------------
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







