#!/usr/bin/env python3
"""
ASN Data Explorer
Analyze what data we have available for ASN dimension and suggest new columns
"""

import duckdb
from pathlib import Path

DB_PATH = './attack_data.db'

def main():
    print("="*80)
    print("ASN DATA STRUCTURE EXPLORER")
    print("="*80)
    
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    # 1. Check what ASN tables exist
    print("\n📊 Step 1: Available ASN Tables")
    print("-"*80)
    
    tables = conn.execute("""
        SELECT name 
        FROM sqlite_master 
        WHERE type='table' 
          AND name LIKE '%asn%'
        ORDER BY name
    """).fetchall()
    
    for table in tables:
        table_name = table[0]
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"  📋 {table_name}: {count:,} rows")
        
        # Show columns
        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        col_names = [c[1] for c in cols]
        print(f"     Columns: {', '.join(col_names)}")
    
    # 2. Check daily_asn_attacks structure
    print("\n📊 Step 2: daily_asn_attacks Sample Data")
    print("-"*80)
    
    sample = conn.execute("""
        SELECT *
        FROM daily_asn_attacks
        LIMIT 3
    """).fetchall()
    
    cols = conn.execute("PRAGMA table_info(daily_asn_attacks)").fetchall()
    col_names = [c[1] for c in cols]
    
    print(f"Columns: {col_names}")
    print("\nSample rows:")
    for row in sample:
        print(f"  {dict(zip(col_names, row))}")
    
    # 3. Analyze ASN diversity
    print("\n📊 Step 3: ASN Statistics")
    print("-"*80)
    
    stats = conn.execute("""
        SELECT 
            COUNT(DISTINCT asn_name) as total_asns,
            COUNT(DISTINCT country) as countries_with_asns,
            COUNT(DISTINCT date) as days_in_data,
            SUM(attacks) as total_attacks,
            MIN(date) as first_date,
            MAX(date) as last_date
        FROM daily_asn_attacks
    """).fetchone()
    
    print(f"  Total unique ASNs: {stats[0]:,}")
    print(f"  Countries represented: {stats[1]:,}")
    print(f"  Days in dataset: {stats[2]:,}")
    print(f"  Total attacks: {stats[3]:,}")
    print(f"  Date range: {stats[4]} to {stats[5]}")
    
    # 4. Sample ASN with detailed info
    print("\n📊 Step 4: Sample ASN Deep Dive")
    print("-"*80)
    
    # Pick a moderately active ASN
    sample_asn = conn.execute("""
        SELECT 
            asn_name,
            SUM(attacks) as total_attacks,
            COUNT(DISTINCT country) as countries,
            COUNT(DISTINCT date) as active_days
        FROM daily_asn_attacks
        GROUP BY asn_name
        ORDER BY total_attacks DESC
        LIMIT 1 OFFSET 50
    """).fetchone()
    
    print(f"\nSample ASN: {sample_asn[0]}")
    print(f"  Total attacks: {sample_asn[1]:,}")
    print(f"  Countries: {sample_asn[2]}")
    print(f"  Active days: {sample_asn[3]}")
    
    asn_name = sample_asn[0]
    
    # Countries this ASN attacks from
    countries = conn.execute(f"""
        SELECT 
            country,
            SUM(attacks) as attacks,
            COUNT(DISTINCT date) as days
        FROM daily_asn_attacks
        WHERE asn_name = ?
        GROUP BY country
        ORDER BY attacks DESC
    """, [asn_name]).fetchall()
    
    print(f"\n  Countries this ASN operates from:")
    for country, attacks, days in countries[:5]:
        pct = (attacks / sample_asn[1]) * 100
        print(f"    - {country}: {attacks:,} attacks ({pct:.1f}%) over {days} days")
    
    # 5. Check if we have IP data for ASNs
    print("\n📊 Step 5: Cross-Reference with Other Tables")
    print("-"*80)
    
    # Check daily_ip_attacks
    ip_with_asn = conn.execute("""
        SELECT COUNT(*), COUNT(DISTINCT IP), COUNT(DISTINCT asn_name)
        FROM daily_ip_attacks
        WHERE asn_name IS NOT NULL
    """).fetchone()
    
    print(f"  daily_ip_attacks:")
    print(f"    Rows: {ip_with_asn[0]:,}")
    print(f"    Unique IPs: {ip_with_asn[1]:,}")
    print(f"    Unique ASNs: {ip_with_asn[2]:,}")
    
    # Check daily_ip_username_attacks
    username_check = conn.execute("""
        SELECT COUNT(*), COUNT(DISTINCT IP), COUNT(DISTINCT username)
        FROM daily_ip_username_attacks
        LIMIT 1
    """).fetchone()
    
    print(f"  daily_ip_username_attacks:")
    print(f"    Rows: {username_check[0]:,}")
    print(f"    Unique IPs: {username_check[1]:,}")
    print(f"    Unique Usernames: {username_check[2]:,}")
    
    # 6. Possible new columns for ASN
    print("\n📊 Step 6: Possible New Columns for ASN Table")
    print("-"*80)
    
    print("\n🔹 COUNTRY-RELATED:")
    print("  ✅ unique_countries - Number of countries ASN operates from")
    print("  ✅ country_concentration - Top 3 countries (with %)")
    print("  ✅ country_diversity - Entropy/Herfindahl index")
    
    print("\n🔹 IP-RELATED:")
    print("  ✅ unique_ips - Number of unique IP addresses")
    print("  ✅ ip_rotation - Avg IPs per active day")
    print("  ✅ ip_concentration - Top 3 IPs (with %)")
    
    print("\n🔹 USERNAME-RELATED:")
    print("  ✅ unique_usernames - Number of unique usernames tried")
    print("  ✅ username_rotation - Avg usernames per active day")
    print("  ✅ username_concentration - Top 3 usernames (with %)")
    
    print("\n🔹 TEMPORAL:")
    print("  ✅ peak_hours - Top 3 hours (same as country)")
    print("  ✅ peak_minutes - Top 3 minutes")
    print("  ✅ peak_seconds - Top 3 seconds")
    
    print("\n🔹 STABILITY:")
    print("  ✅ country_stability - Jaccard similarity of country sets")
    print("  ✅ ip_stability - Jaccard similarity of IP sets")
    print("  ✅ username_stability - Jaccard similarity of username sets")
    
    print("\n🔹 GEOGRAPHIC:")
    print("  ✅ primary_country - Country with most attacks")
    print("  ✅ multi_country - Boolean: operates from 2+ countries")
    
    # 7. Test query for one ASN
    print("\n📊 Step 7: Test Query for Sample ASN Metrics")
    print("-"*80)
    
    test_query = f"""
        WITH asn_data AS (
            SELECT 
                asn_name,
                SUM(attacks) as total_attacks,
                COUNT(DISTINCT country) as unique_countries,
                COUNT(DISTINCT date) as active_days,
                MAX(attacks) as max_daily
            FROM daily_asn_attacks
            WHERE asn_name = ?
            GROUP BY asn_name
        ),
        ip_data AS (
            SELECT 
                asn_name,
                COUNT(DISTINCT IP) as unique_ips
            FROM daily_ip_attacks
            WHERE asn_name = ?
            GROUP BY asn_name
        )
        SELECT 
            a.*,
            i.unique_ips
        FROM asn_data a
        LEFT JOIN ip_data i ON a.asn_name = i.asn_name
    """
    
    result = conn.execute(test_query, [asn_name, asn_name]).fetchone()
    
    print(f"\nSample query result for: {asn_name}")
    print(f"  Total attacks: {result[1]:,}")
    print(f"  Unique countries: {result[2]}")
    print(f"  Active days: {result[3]}")
    print(f"  Max daily: {result[4]:,}")
    print(f"  Unique IPs: {result[5]:,}")
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ Exploration Complete!")
    print("="*80)
    
    print("\n💡 RECOMMENDATIONS:")
    print("  1. Start with Country-related columns (unique_countries, country_concentration)")
    print("  2. Add IP columns (unique_ips, ip_rotation)")
    print("  3. Add Username columns (unique_usernames, username_rotation)")
    print("  4. Add Stability metrics (country_stability, ip_stability, username_stability)")
    print("  5. Add Peak time columns (peak_hours, peak_minutes, peak_seconds)")
    print("  6. Add Concentration columns (country_concentration, ip_concentration, username_concentration)")


if __name__ == "__main__":
    main()
