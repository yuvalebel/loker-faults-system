"""
בדיקה מהירה של הפונקציה get_faults_with_student_info
"""
from app import get_faults_with_student_info, get_all_faults

print("=" * 60)
print("בדיקת תקלות")
print("=" * 60)

# בדיקה 1: תקלות גולמיות
faults = get_all_faults()
print(f"\n1. Total faults (raw): {len(faults)}")
if faults:
    print(f"   First fault: {faults[0]}")

# בדיקה 2: תקלות עם מידע תלמידים
print("\n2. Getting faults with student info...")
try:
    df = get_faults_with_student_info()
    print(f"   DataFrame shape: {df.shape}")
    print(f"   DataFrame empty: {df.empty}")
    
    if not df.empty:
        print("\n   Columns:", list(df.columns))
        print("\n   First few rows:")
        print(df.head())
    else:
        print("   ❌ DataFrame is EMPTY!")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
