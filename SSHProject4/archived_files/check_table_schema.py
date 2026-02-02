"""
Quick script to check what columns exist in the daily tables
Run this in your Flask environment to see available columns
"""

import duckdb

# Connect to your database
conn = duckdb.connect('/home/shreeman/Desktop/WayFasterLoad/SSHProject4/attack_data.db')

print("=" * 60)
print("DAILY_ASN_ATTACKS TABLE SCHEMA:")
print("=" * 60)
result = conn.execute("DESCRIBE daily_asn_attacks").fetchall()
for row in result:
    print(f"{row[0]:<20} {row[1]:<15}")

print("\n" + "=" * 60)
print("DAILY_IP_ATTACKS TABLE SCHEMA:")
print("=" * 60)
result = conn.execute("DESCRIBE daily_ip_attacks").fetchall()
for row in result:
    print(f"{row[0]:<20} {row[1]:<15}")

print("\n" + "=" * 60)
print("DAILY_IP_USERNAME_ATTACKS TABLE SCHEMA:")
print("=" * 60)
result = conn.execute("DESCRIBE daily_ip_username_attacks").fetchall()
for row in result:
    print(f"{row[0]:<20} {row[1]:<15}")

print("\n" + "=" * 60)
print("SAMPLE DATA FROM DAILY_ASN_ATTACKS (first 3 rows):")
print("=" * 60)
result = conn.execute("SELECT * FROM daily_asn_attacks LIMIT 3").fetchall()
cols = [desc[0] for desc in conn.execute("DESCRIBE daily_asn_attacks").fetchall()]
print("Columns:", ", ".join(cols))
for row in result:
    print(row)

conn.close()
