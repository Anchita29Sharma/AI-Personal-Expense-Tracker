import sqlite3
import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np

# ----------------- LOAD DATA -----------------
conn = sqlite3.connect("expenses.db")
df = pd.read_sql_query("SELECT * FROM expenses", conn)
conn.close()

if df.empty:
    print("No data available for insights")
    exit()

# ----------------- BASIC INSIGHTS -----------------
total_expense = df["amount"].sum()
highest_category = df.groupby("category")["amount"].sum().idxmax()
highest_category_amount = df.groupby("category")["amount"].sum().max()

print("----- AI INSIGHTS -----")
print(f"Total expense: ₹{total_expense}")
print(f"Highest spending category: {highest_category} (₹{highest_category_amount})")

# Overspending check
if highest_category_amount > 0.5 * total_expense:
    print(f"⚠️ You are overspending on {highest_category}")

# ----------------- EXPENSE PREDICTION -----------------
# Convert date to numeric (day index)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")

df["day_index"] = np.arange(len(df))

X = df[["day_index"]]
y = df["amount"]

model = LinearRegression()
model.fit(X, y)

next_day = pd.DataFrame(
    [[df["day_index"].max() + 1]],
    columns=["day_index"]
)
predicted_amount = model.predict(next_day)[0]



print(f"📈 Predicted next expense amount: ₹{round(predicted_amount, 2)}")
