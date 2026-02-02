import duckdb

conn = duckdb.connect('./attack_data.db')
print("📊 Tables in attack_data.db:")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for table in tables:
    print(f"\n  Table: {table[0]}")
    count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
    print(f"    Rows: {count:,}")
    cols = conn.execute(f"PRAGMA table_info({table[0]})").fetchall()
    print(f"    Columns: {', '.join([c[1] for c in cols])}")
conn.close()
