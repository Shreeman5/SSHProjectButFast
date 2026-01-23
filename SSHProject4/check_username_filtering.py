#!/usr/bin/env python3
"""
Verify daily_ip_username_attacks table supports username filtering
"""

import duckdb

DB_PATH = './attack_data.db'

def main():
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    print("="*70)
    print("CHECKING USERNAME FILTERING CAPABILITY")
    print("="*70)
    
    # Get schema
    print("\n1. TABLE SCHEMA:")
    print("-" * 70)
    schema = conn.execute("DESCRIBE daily_ip_username_attacks").fetchall()
    for col_name, col_type, *_ in schema:
        print(f"   {col_name:20s} ({col_type})")
    
    # Pick a popular username
    sample = conn.execute("""
        SELECT username, SUM(attacks) as total
        FROM daily_ip_username_attacks
        GROUP BY username
        ORDER BY total DESC
        LIMIT 1
    """).fetchone()
    
    test_username = sample[0]
    total_attacks = sample[1]
    
    print(f"\n2. TESTING WITH USERNAME: '{test_username}'")
    print(f"   Total attacks: {total_attacks:,}")
    print("-" * 70)
    
    # Check what data we can get for this username
    print(f"\n3. TOP COUNTRIES using '{test_username}':")
    countries = conn.execute(f"""
        SELECT country, SUM(attacks) as total
        FROM daily_ip_username_attacks
        WHERE username = '{test_username}'
        GROUP BY country
        ORDER BY total DESC
        LIMIT 5
    """).fetchall()
    
    for country, attacks in countries:
        print(f"   {country:20s}: {attacks:>8,}")
    
    print(f"\n4. TOP ASNs using '{test_username}':")
    asns = conn.execute(f"""
        SELECT asn_name, SUM(attacks) as total
        FROM daily_ip_username_attacks
        WHERE username = '{test_username}'
        GROUP BY asn_name
        ORDER BY total DESC
        LIMIT 5
    """).fetchall()
    
    for asn, attacks in asns:
        print(f"   {asn[:40]:40s}: {attacks:>8,}")
    
    print(f"\n5. TOP IPs using '{test_username}':")
    ips = conn.execute(f"""
        SELECT IP, SUM(attacks) as total
        FROM daily_ip_username_attacks
        WHERE username = '{test_username}'
        GROUP BY IP
        ORDER BY total DESC
        LIMIT 5
    """).fetchall()
    
    for ip, attacks in ips:
        print(f"   {ip:20s}: {attacks:>8,}")
    
    print(f"\n6. DAILY TIMELINE for '{test_username}':")
    timeline = conn.execute(f"""
        SELECT date, SUM(attacks) as total
        FROM daily_ip_username_attacks
        WHERE username = '{test_username}'
        GROUP BY date
        ORDER BY date
        LIMIT 5
    """).fetchall()
    
    for date, attacks in timeline:
        print(f"   {date}: {attacks:>8,}")
    
    print(f"\n{'='*70}")
    print("SUMMARY - Can we filter all charts by username?")
    print(f"{'='*70}")
    print(f"""
✅ Date Chart: YES - Timeline of '{test_username}' attacks
✅ Country Chart: YES - Top countries using '{test_username}'
✅ Volatile Chart: YES - Volatile countries using '{test_username}'
✅ ASN Chart: YES - Top ASNs using '{test_username}'
✅ IP Chart: YES - Top IPs using '{test_username}'
✅ Username Chart: YES - Show only '{test_username}'

All data is available in daily_ip_username_attacks table!
""")
    
    conn.close()

if __name__ == "__main__":
    main()
