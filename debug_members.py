"""
Debug efinance get_members
"""
import efinance as ef

print("Testing efinance get_members...")
print("="*80)

# Test different board codes
board_codes = ['BK0465', 'BK1594', 'BK1216', 'BK0159']

for board_code in board_codes:
    print(f"\nTesting board: {board_code}")
    try:
        df = ef.stock.get_members(board_code)
        if df is not None and not df.empty:
            print(f"✅ Success! Got {len(df)} members")
            print(f"Columns: {list(df.columns)}")
            print(df.head(3))
        else:
            print("⚠️ No data returned")
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n" + "="*80)
