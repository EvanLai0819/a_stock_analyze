import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.cursor()

# Query all analysis results from today
today = datetime.now().strftime('%Y-%m-%d')
cursor.execute('''
    SELECT code, name, sentiment_score, operation_advice, trend_prediction, created_at
    FROM analysis_history
    WHERE date(created_at) = ?
    ORDER BY created_at DESC
''', (today,))

rows = cursor.fetchall()

print(f"\n今日分析统计 ({today}):")
print("="*80)
print(f"已分析股票数: {len(rows)}")
print(f"股票列表: {', '.join([r[0] for r in rows])}")
print()

# Check which stocks are missing
expected_stocks = ['600276', '600875', '002074', '002271', '002460']
analyzed_stocks = [r[0] for r in rows]
missing_stocks = [s for s in expected_stocks if s not in analyzed_stocks]

if missing_stocks:
    print(f"未分析股票: {', '.join(missing_stocks)}")
else:
    print("所有股票已分析完成")

conn.close()
