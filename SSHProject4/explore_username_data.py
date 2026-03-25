#!/usr/bin/env python3
"""
Explore Username data available in the database
"""

import duckdb

DB_PATH = './attack_data.db'

print("="*80)
print("USERNAME DATA EXPLORATION")
print("="*80)

conn = duckdb.connect(DB_PATH)

# 1. Check if there's a daily_username_attacks table
print("\n🔍 CHECKING FOR USERNAME TABLES")
print("-"*80)

tables = conn.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'main'
    AND table_name LIKE '%username%'
""").fetchall()

print("\nTables with 'username' in name:")
for table in tables:
    print(f"  - {table[0]}")

# 2. Check daily_ip_username_attacks (we know this exists)
print("\n" + "="*80)
print("📊 TABLE: daily_ip_username_attacks")
print("-"*80)

schema = conn.execute("""
    DESCRIBE daily_ip_username_attacks
""").fetchall()

print("\nColumns:")
for col in schema:
    print(f"  - {col[0]:<20} {col[1]}")

# Sample data
print("\nSample data (3 rows):")
sample = conn.execute("""
    SELECT * FROM daily_ip_username_attacks LIMIT 3
""").fetchall()

for row in sample:
    print(f"  {row}")

# Count
count = conn.execute("SELECT COUNT(*) FROM daily_ip_username_attacks").fetchone()[0]
print(f"\nTotal rows: {count:,}")

# Unique usernames
unique_usernames = conn.execute("SELECT COUNT(DISTINCT username) FROM daily_ip_username_attacks").fetchone()[0]
print(f"Unique usernames: {unique_usernames:,}")

# 3. Check what data we can get for a specific username
print("\n" + "="*80)
print("🎯 DATA AVAILABLE FOR ONE USERNAME")
print("-"*80)

# Pick a common username
top_username = conn.execute("""
    SELECT username, SUM(attacks) as total
    FROM daily_ip_username_attacks
    GROUP BY username
    ORDER BY total DESC
    LIMIT 1
""").fetchone()

print(f"\nTop username: '{top_username[0]}' ({top_username[1]:,} total attacks)")

# Can we get country, ASN, IP data for this username?
print(f"\n📊 Attribution data for '{top_username[0]}':")

attribution = conn.execute(f"""
    SELECT 
        COUNT(DISTINCT country) as unique_countries,
        COUNT(DISTINCT asn_name) as unique_asns,
        COUNT(DISTINCT ip) as unique_ips,
        COUNT(DISTINCT date) as active_days
    FROM daily_ip_username_attacks
    WHERE username = '{top_username[0]}'
""").fetchone()

print(f"  Unique Countries: {attribution[0]:,}")
print(f"  Unique ASNs:      {attribution[1]:,}")
print(f"  Unique IPs:       {attribution[2]:,}")
print(f"  Active Days:      {attribution[3]:,}")

# Top 3 countries for this username
print(f"\n📍 Top 3 countries targeting '{top_username[0]}':")
top_countries = conn.execute(f"""
    SELECT country, SUM(attacks) as total_attacks
    FROM daily_ip_username_attacks
    WHERE username = '{top_username[0]}'
    GROUP BY country
    ORDER BY total_attacks DESC
    LIMIT 3
""").fetchall()

for country, attacks in top_countries:
    print(f"  {country:<20} {attacks:>12,} attacks")

# Top 3 ASNs for this username
print(f"\n🏢 Top 3 ASNs targeting '{top_username[0]}':")
top_asns = conn.execute(f"""
    SELECT asn_name, SUM(attacks) as total_attacks
    FROM daily_ip_username_attacks
    WHERE username = '{top_username[0]}'
    GROUP BY asn_name
    ORDER BY total_attacks DESC
    LIMIT 3
""").fetchall()

for asn, attacks in top_asns:
    print(f"  {asn[:50]:<50} {attacks:>12,} attacks")

# Top 3 IPs for this username
print(f"\n💻 Top 3 IPs targeting '{top_username[0]}':")
top_ips = conn.execute(f"""
    SELECT ip, SUM(attacks) as total_attacks
    FROM daily_ip_username_attacks
    WHERE username = '{top_username[0]}'
    GROUP BY ip
    ORDER BY total_attacks DESC
    LIMIT 3
""").fetchall()

for ip, attacks in top_ips:
    print(f"  {ip:<20} {attacks:>12,} attacks")

# 4. Check for timestamp data
print("\n" + "="*80)
print("⏰ TIMESTAMP DATA")
print("-"*80)

# Check if time field exists
try:
    time_check = conn.execute("""
        SELECT date, username, time, attacks
        FROM daily_ip_username_attacks
        WHERE time IS NOT NULL
        LIMIT 5
    """).fetchall()
    
    if time_check:
        print("\n✅ Time field exists! Sample data:")
        for row in time_check:
            print(f"  Date: {row[0]} | Username: {row[1]} | Time: {row[2]} | Attacks: {row[3]}")
    else:
        print("\n❌ Time field exists but all values are NULL")
except Exception as e:
    print(f"\n❌ No time field: {e}")

# 5. Check stability computation feasibility
print("\n" + "="*80)
print("🔬 STABILITY COMPUTATION FEASIBILITY")
print("-"*80)

# Can we track country/ASN/IP sets by date for a username?
stability_check = conn.execute(f"""
    SELECT 
        date,
        COUNT(DISTINCT country) as unique_countries,
        COUNT(DISTINCT asn_name) as unique_asns,
        COUNT(DISTINCT ip) as unique_ips,
        SUM(attacks) as daily_attacks
    FROM daily_ip_username_attacks
    WHERE username = '{top_username[0]}'
    GROUP BY date
    ORDER BY date
    LIMIT 10
""").fetchall()

print(f"\nAttribution sets by date for '{top_username[0]}' (first 10 days):")
print(f"{'Date':<12} {'Countries':>10} {'ASNs':>10} {'IPs':>10} {'Attacks':>10}")
print("-" * 60)
for row in stability_check:
    print(f"{str(row[0]):<12} {row[1]:>10} {row[2]:>10} {row[3]:>10} {row[4]:>10,}")

print("\n✅ Country/ASN/IP stability IS computable!")
print("   (Track unique country/ASN/IP sets per day, compute Jaccard similarity)")

# 6. Check rotation computation feasibility
print("\n" + "="*80)
print("🔄 ROTATION COMPUTATION FEASIBILITY")
print("-"*80)

rotation_data = conn.execute(f"""
    SELECT 
        COUNT(DISTINCT date) as active_days,
        COUNT(DISTINCT country) as total_countries,
        COUNT(DISTINCT asn_name) as total_asns,
        COUNT(DISTINCT ip) as total_ips
    FROM daily_ip_username_attacks
    WHERE username = '{top_username[0]}'
""").fetchone()

active_days = rotation_data[0]
country_rotation = rotation_data[1] / active_days if active_days > 0 else 0
asn_rotation = rotation_data[2] / active_days if active_days > 0 else 0
ip_rotation = rotation_data[3] / active_days if active_days > 0 else 0

print(f"\nRotation metrics for '{top_username[0]}':")
print(f"  Active days:      {active_days}")
print(f"  Country rotation: {country_rotation:.1f} countries/day")
print(f"  ASN rotation:     {asn_rotation:.1f} ASNs/day")
print(f"  IP rotation:      {ip_rotation:.1f} IPs/day")

print("\n✅ Rotation IS computable!")

# 7. Summary of what we can compute
print("\n" + "="*80)
print("📋 AVAILABLE USERNAME METRICS")
print("-"*80)

print("\n✅ CAN COMPUTE (from daily_ip_username_attacks):")
print("  Attribution:")
print("    - Unique Countries (COUNT DISTINCT country)")
print("    - Unique ASNs (COUNT DISTINCT asn_name)")
print("    - Unique IPs (COUNT DISTINCT ip)")
print("    - Country Concentration (GROUP BY country, top 3)")
print("    - ASN Concentration (GROUP BY asn_name, top 3)")
print("    - IP Concentration (GROUP BY ip, top 3)")
print("  Stability:")
print("    - Country Stability (Jaccard similarity of country sets by day)")
print("    - ASN Stability (Jaccard similarity of ASN sets by day)")
print("    - IP Stability (Jaccard similarity of IP sets by day)")
print("  Rotation:")
print("    - Country Rotation (unique countries / active days)")
print("    - ASN Rotation (unique ASNs / active days)")
print("    - IP Rotation (unique IPs / active days)")
print("  Other:")
print("    - Trend Sparkline (SUM attacks by week)")
print("    - Burst Intensity (MAX daily / AVG daily)")

# Check for time field status
try:
    has_time = conn.execute("SELECT COUNT(*) FROM daily_ip_username_attacks WHERE time IS NOT NULL").fetchone()[0] > 0
    if has_time:
        print("    - Peak Hours (from time field)")
        print("    - Peak Minutes (from time field)")
        print("    - Peak Seconds (from time field)")
except:
    has_time = False

if not has_time:
    print("\n❌ CANNOT COMPUTE (no timestamp data):")
    print("    - Peak Hours")
    print("    - Peak Minutes")
    print("    - Peak Seconds")

print("\n❌ NOT APPLICABLE:")
print("    - Unique Usernames (we're looking at one username)")
print("    - Username Concentration (N/A)")
print("    - Username Stability (N/A)")
print("    - Username Rotation (N/A)")

# 8. Show example of diverse vs. focused username
print("\n" + "="*80)
print("📊 COMPARISON: DIVERSE vs. FOCUSED TARGETING")
print("-"*80)

# Find a username with high IP diversity
diverse = conn.execute("""
    SELECT 
        username,
        COUNT(DISTINCT ip) as unique_ips,
        COUNT(DISTINCT country) as unique_countries,
        SUM(attacks) as total_attacks
    FROM daily_ip_username_attacks
    GROUP BY username
    HAVING COUNT(DISTINCT ip) > 100
    ORDER BY unique_ips DESC
    LIMIT 1
""").fetchone()

# Find a username with low IP diversity but high attacks
focused = conn.execute("""
    SELECT 
        username,
        COUNT(DISTINCT ip) as unique_ips,
        COUNT(DISTINCT country) as unique_countries,
        SUM(attacks) as total_attacks
    FROM daily_ip_username_attacks
    GROUP BY username
    HAVING COUNT(DISTINCT ip) < 10 AND SUM(attacks) > 10000
    ORDER BY total_attacks DESC
    LIMIT 1
""").fetchone()

print("\n🌍 DIVERSE: Widely targeted username")
if diverse:
    print(f"  Username:  '{diverse[0]}'")
    print(f"  IPs:       {diverse[1]:,}")
    print(f"  Countries: {diverse[2]:,}")
    print(f"  Attacks:   {diverse[3]:,}")
    print(f"  → Many sources try this username (distributed attack)")

print("\n🎯 FOCUSED: Narrowly targeted username")
if focused:
    print(f"  Username:  '{focused[0]}'")
    print(f"  IPs:       {focused[1]:,}")
    print(f"  Countries: {focused[2]:,}")
    print(f"  Attacks:   {focused[3]:,}")
    print(f"  → Few sources concentrate on this username (targeted)")

conn.close()

print("\n" + "="*80)
print("✅ EXPLORATION COMPLETE")
print("="*80)
