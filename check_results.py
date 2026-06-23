import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/stock_analysis.db')
cursor = conn.cursor()

# Query today's analysis results
today = datetime.now().strftime('%Y-%m-%d')
cursor.execute('''
    SELECT code, name, sentiment_score, operation_advice, trend_prediction, analysis_summary, created_at
    FROM analysis_history
    WHERE date(created_at) = ?
    ORDER BY sentiment_score DESC
''', (today,))

rows = cursor.fetchall()

if rows:
    print(f"\n{'='*80}")
    print(f"今日股票分析报告 ({today})")
    print(f"{'='*80}\n")
    
    for i, r in enumerate(rows, 1):
        # Score color
        score = r[2]
        if score >= 70:
            score_str = f"🟢 {score}/100"
        elif score >= 50:
            score_str = f"🟡 {score}/100"
        else:
            score_str = f"🔴 {score}/100"
        
        print(f"{i}. {r[0]} {r[1]}")
        print(f"   评分: {score_str}")
        print(f"   操作建议: {r[3]}")
        print(f"   趋势预测: {r[4]}")
        print(f"   分析时间: {r[6]}")
        print()
    
    print(f"{'='*80}")
    print(f"详细分析")
    print(f"{'='*80}\n")
    
    for r in rows:
        print(f"\n【{r[0]} {r[1]}】")
        print(f"评分: {r[2]}/100 | 操作建议: {r[3]} | 趋势预测: {r[4]}")
        print(f"分析时间: {r[6]}")
        if r[5]:
            print(f"\n{r[5]}")
        print("-"*80)
else:
    print(f"今日 ({today}) 暂无分析结果")

conn.close()
