import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# connect to database
conn = sqlite3.connect("expenses.db")

# read data into pandas dataframe
df = pd.read_sql_query("SELECT * FROM expenses", conn)
conn.close()

print(df)

# --------- CATEGORY WISE ANALYSIS ---------
category_sum = df.groupby("category")["amount"].sum()

plt.figure()
category_sum.plot(kind="pie", autopct="%1.1f%%")
plt.title("Category-wise Expense Distribution")
plt.ylabel("")
plt.show()

# --------- DATE WISE ANALYSIS ---------
df["date"] = pd.to_datetime(df["date"])
date_sum = df.groupby("date")["amount"].sum()

plt.figure()
sns.barplot(x=date_sum.index.astype(str), y=date_sum.values)
plt.xticks(rotation=45)
plt.title("Date-wise Expenses")
plt.xlabel("Date")
plt.ylabel("Amount")
plt.show()
