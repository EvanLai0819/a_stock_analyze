import sqlite3

conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("数据库中的表:")
print("="*80)
for table in tables:
    print(f"- {table[0]}")

conn.close()
