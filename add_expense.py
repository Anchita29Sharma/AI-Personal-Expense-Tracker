import sqlite3

def add_expense(date, category, amount, description):
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # ✅ ALWAYS ensure table exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        category TEXT,
        amount REAL,
        description TEXT
    )
    """)

    # insert expense
    cursor.execute("""
    INSERT INTO expenses (date, category, amount, description)
    VALUES (?, ?, ?, ?)
    """, (date, category, amount, description))

    conn.commit()
    conn.close()

    print("Expense added successfully")

# ---------- ADD SAMPLE EXPENSES ----------
sample_expenses = [
    ("2025-01-05", "Food", 250, "Breakfast & lunch"),
    ("2025-01-06", "Travel", 120, "Auto fare"),
    ("2025-01-07", "Food", 180, "Dinner"),
    ("2025-01-08", "Entertainment", 300, "Movie"),
    ("2025-01-09", "Travel", 450, "Bus + cab"),
    ("2025-01-10", "Groceries", 900, "Monthly groceries"),
    ("2025-01-11", "Bills", 600, "Electricity bill"),
    ("2025-01-12", "Food", 220, "Snacks"),
    ("2025-01-13", "Shopping", 1500, "Clothes"),
    ("2025-01-14", "Health", 700, "Medicines"),
    ("2025-01-15", "Education", 1200, "Online course"),
    ("2025-01-16", "Travel", 300, "Weekend travel"),
]

for exp in sample_expenses:
    add_expense(*exp)


