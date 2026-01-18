from flask import Flask, render_template, request, send_file, redirect, session
import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

app = Flask(__name__)
app.secret_key = "expense-secret-key"

def init_db():
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------- DATABASE ----------------
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
            return render_template(
                "signup.html",
                error="Username already exists"
            )

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

    # SAFE monthly trend
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
        date = request.form["date"]
        category = request.form["category"]
        amount = request.form["amount"]
        description = request.form["description"]

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO expenses (date, category, amount, description) VALUES (?, ?, ?, ?)",
            (date, category, amount, description)
        )
        conn.commit()
        conn.close()

        return redirect("/history")

    return render_template("add_expense.html")

# ---------------- EXPENSE HISTORY ----------------
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
        search=search,
        page=page
    )

# ---------------- EDIT EXPENSE ----------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()

    if request.method == "POST":
        date = request.form["date"]
        category = request.form["category"]
        amount = request.form["amount"]
        description = request.form["description"]

        conn.execute(
            """
            UPDATE expenses
            SET date=?, category=?, amount=?, description=?
            WHERE id=?
            """,
            (date, category, amount, description, id)
        )
        conn.commit()
        conn.close()
        return redirect("/history")

    expense = conn.execute(
        "SELECT * FROM expenses WHERE id=?", (id,)
    ).fetchone()
    conn.close()

    return render_template("edit_expense.html", expense=expense)

# ---------------- DELETE EXPENSE ----------------
@app.route("/delete/<int:id>")
def delete(id):
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    conn.execute("DELETE FROM expenses WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/history")

# ---------------- AI INSIGHTS ----------------
@app.route("/insights")
def insights():
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()

    if df.empty:
        return render_template(
            "insights.html",
            insight="No data available for insights.",
            prediction="N/A"
        )

    category_sum = df.groupby("category")["amount"].sum()
    total_expense = category_sum.sum()

    top_category = category_sum.idxmax()
    top_percentage = round((category_sum.max() / total_expense) * 100, 2)

    if top_percentage >= 40:
        insight = f"⚠️ High spending detected on {top_category} ({top_percentage}%)."
    else:
        insight = f"✅ Spending is well balanced. Top category is {top_category}."

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df["day_index"] = np.arange(len(df))

    model = LinearRegression()
    model.fit(df[["day_index"]], df["amount"])

    next_day = [[df["day_index"].max() + 1]]
    predicted_amount = round(model.predict(next_day)[0], 2)

    return render_template(
        "insights.html",
        insight=insight,
        prediction=predicted_amount
    )

# ---------------- EXPORT CSV ----------------
@app.route("/export")
def export():
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()

    file_path = "expenses_export.csv"
    df.to_csv(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(host ="0.0.0.0", port=5000)



