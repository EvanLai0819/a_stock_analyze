"""
Check available methods in efinance
"""
import efinance as ef

print("Checking Efinance Available Methods...")
print("="*80)

print("\n1. efinance.stock methods:")
stock_methods = [m for m in dir(ef.stock) if not m.startswith('_')]
for method in sorted(stock_methods):
    print(f"  - {method}")

print("\n2. efinance methods:")
ef_methods = [m for m in dir(ef) if not m.startswith('_')]
for method in sorted(ef_methods):
    print(f"  - {method}")

# Try to find board-related methods
print("\n3. Board-related methods:")
board_methods = [m for m in dir(ef.stock) if 'board' in m.lower() or 'sector' in m.lower() or 'industry' in m.lower()]
for method in sorted(board_methods):
    print(f"  - {method}")

print("\n" + "="*80)
