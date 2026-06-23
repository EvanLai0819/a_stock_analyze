import sqlite3

conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.cursor()

# Get table schema
cursor.execute("PRAGMA table_info(analysis_history)")
columns = cursor.fetchall()

print("analysis_history 表结构:")
print("="*80)
for col in columns:
    print(f"{col[1]} ({col[2]})")

conn.close()
