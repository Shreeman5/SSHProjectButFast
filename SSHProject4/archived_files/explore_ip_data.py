#!/usr/bin/env python3
"""
Explore IP data available in the database
"""

import duckdb

DB_PATH = './attack_data.db'

print("="*80)
print("IP DATA EXPLORATION")
print("="*80)

conn = duckdb.connect(DB_PATH)

# 1. Check daily_ip_attacks table structure
print("\n📊 TABLE: daily_ip_attacks")
print("-"*80)
schema = conn.execute("""
    DESCRIBE daily_ip_attacks
""").fetchall()

print("\nColumns:")
for col in schema:
    print(f"  - {col[0]:<20} {col[1]}")

# Sample data
print("\nSample data (3 rows):")
sample = conn.execute("""
    SELECT * FROM daily_ip_attacks LIMIT 3
""").fetchall()

for row in sample:
    print(f"  {row}")

# Count
count = conn.execute("SELECT COUNT(*) FROM daily_ip_attacks").fetchone()[0]
print(f"\nTotal rows: {count:,}")

# Unique IPs
unique_ips = conn.execute("SELECT COUNT(DISTINCT ip) FROM daily_ip_attacks").fetchone()[0]
print(f"Unique IPs: {unique_ips:,}")

# 2. Check daily_ip_username_attacks table structure
print("\n" + "="*80)
print("📊 TABLE: daily_ip_username_attacks")
print("-"*80)
schema2 = conn.execute("""
    DESCRIBE daily_ip_username_attacks
""").fetchall()

print("\nColumns:")
for col in schema2:
    print(f"  - {col[0]:<20} {col[1]}")

# Sample data
print("\nSample data (3 rows):")
sample2 = conn.execute("""
    SELECT * FROM daily_ip_username_attacks LIMIT 3
""").fetchall()

for row in sample2:
    print(f"  {row}")

# Count
count2 = conn.execute("SELECT COUNT(*) FROM daily_ip_username_attacks").fetchone()[0]
print(f"\nTotal rows: {count2:,}")

# 3. Check if we can get ASN and country for IPs
print("\n" + "="*80)
print("🔍 IP ATTRIBUTION DATA")
print("-"*80)

# Can we get ASN name from daily_ip_attacks?
asn_check = conn.execute("""
    SELECT ip, asn_name, date, attacks
    FROM daily_ip_attacks
    WHERE ip IS NOT NULL
    LIMIT 5
""").fetchall()

print("\nSample IPs with ASN attribution:")
for row in asn_check:
    print(f"  IP: {row[0]:<20} ASN: {row[1]:<40} Attacks: {row[3]}")

# Can we get country from daily_asn_attacks by joining?
country_check = conn.execute("""
    SELECT 
        i.ip,
        i.asn_name,
        a.country,
        i.attacks
    FROM daily_ip_attacks i
    LEFT JOIN daily_asn_attacks a 
        ON i.date = a.date AND i.asn_name = a.asn_name
    WHERE i.ip IS NOT NULL
    LIMIT 5
""").fetchall()

print("\nSample IPs with ASN + Country (via join):")
for row in country_check:
    print(f"  IP: {row[0]:<20} ASN: {row[1]:<35} Country: {row[2]:<15} Attacks: {row[3]}")

# 4. Check username data for a specific IP
print("\n" + "="*80)
print("🎯 USERNAME TARGETING DATA (for one IP)")
print("-"*80)

# Pick an IP with lots of attacks
top_ip = conn.execute("""
    SELECT ip, SUM(attacks) as total
    FROM daily_ip_attacks
    GROUP BY ip
    ORDER BY total DESC
    LIMIT 1
""").fetchone()

print(f"\nTop attacking IP: {top_ip[0]} ({top_ip[1]:,} total attacks)")

# Get username data for this IP
usernames = conn.execute(f"""
    SELECT username, SUM(attacks) as total_attacks
    FROM daily_ip_username_attacks
    WHERE ip = '{top_ip[0]}'
    GROUP BY username
    ORDER BY total_attacks DESC
    LIMIT 10
""").fetchall()

print(f"\nTop 10 usernames tried by {top_ip[0]}:")
for username, attacks in usernames:
    print(f"  {username:<20} {attacks:>10,} attacks")

# Check if time field exists
print("\n" + "="*80)
print("⏰ TIMESTAMP DATA")
print("-"*80)

time_check = conn.execute("""
    SELECT date, ip, username, time, attacks
    FROM daily_ip_username_attacks
    WHERE time IS NOT NULL
    LIMIT 5
""").fetchall()

if time_check:
    print("\n✅ Time field exists! Sample data:")
    for row in time_check:
        print(f"  Date: {row[0]} | IP: {row[1]} | Time: {row[2]} | Attacks: {row[4]}")
else:
    print("\n❌ No time field or all NULL values")

# 5. Summary of what we can compute
print("\n" + "="*80)
print("📋 AVAILABLE IP METRICS")
print("-"*80)

print("\n✅ CAN COMPUTE:")
print("  - ASN Name (from daily_ip_attacks.asn_name)")
print("  - Country (join daily_ip_attacks → daily_asn_attacks)")
print("  - Unique Usernames (COUNT DISTINCT from daily_ip_username_attacks)")
print("  - Username Concentration (GROUP BY username, top 3)")
print("  - Username Rotation (unique usernames / active days)")
print("  - Trend Sparkline (SUM attacks by week)")
print("  - Burst Intensity (MAX daily / AVG daily)")

if time_check:
    print("  - Peak Hours (from daily_ip_username_attacks.time)")
    print("  - Peak Minutes (from daily_ip_username_attacks.time)")
    print("  - Peak Seconds (from daily_ip_username_attacks.time)")
else:
    print("\n❌ CANNOT COMPUTE (no timestamp data):")
    print("  - Peak Hours")
    print("  - Peak Minutes")
    print("  - Peak Seconds")

print("\n❌ NOT APPLICABLE:")
print("  - Unique IPs (we're already looking at one IP)")
print("  - Unique Countries (one IP = one country)")
print("  - Unique ASNs (one IP = one ASN)")

# Check username stability feasibility
print("\n" + "="*80)
print("🔬 USERNAME STABILITY COMPUTATION FEASIBILITY")
print("-"*80)

# Can we track username sets by date?
stability_check = conn.execute(f"""
    SELECT 
        date,
        COUNT(DISTINCT username) as unique_usernames,
        SUM(attacks) as daily_attacks
    FROM daily_ip_username_attacks
    WHERE ip = '{top_ip[0]}'
    GROUP BY date
    ORDER BY date
    LIMIT 10
""").fetchall()

print(f"\nUsername sets by date for {top_ip[0]} (first 10 days):")
for row in stability_check:
    print(f"  {row[0]} | {row[1]:>3} unique usernames | {row[2]:>6,} attacks")

print("\n✅ Username stability IS computable!")
print("   (Track unique username sets per day, compute Jaccard similarity)")

conn.close()

print("\n" + "="*80)
print("✅ EXPLORATION COMPLETE")
print("="*80)
