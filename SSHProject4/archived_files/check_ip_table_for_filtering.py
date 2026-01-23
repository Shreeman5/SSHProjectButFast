#!/usr/bin/env python3
"""
Check if daily_ip_attacks table can support filtering by IP
for Country, Volatile, and ASN charts
"""

import duckdb

DB_PATH = './attack_data.db'

def main():
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    print("="*70)
    print("CHECKING daily_ip_attacks TABLE FOR IP FILTERING")
    print("="*70)
    
    # Show schema
    print("\n1. TABLE SCHEMA:")
    print("-" * 70)
    schema = conn.execute("DESCRIBE daily_ip_attacks").fetchall()
    for col_name, col_type, *_ in schema:
        print(f"   {col_name:20s} ({col_type})")
    
    # Get a sample IP with lots of data
    sample_ip = conn.execute("""
        SELECT IP, SUM(attacks) as total
        FROM daily_ip_attacks
        GROUP BY IP
        ORDER BY total DESC
        LIMIT 1
    """).fetchone()
    
    test_ip = sample_ip[0]
    total_attacks = sample_ip[1]
    
    print(f"\n2. TESTING WITH IP: {test_ip}")
    print(f"   Total attacks: {total_attacks:,}")
    print("-" * 70)
    
    # Check country data for this IP
    print(f"\n3. COUNTRY CHART - Can we show which country this IP is from?")
    country_data = conn.execute(f"""
        SELECT country, SUM(attacks) as total
        FROM daily_ip_attacks
        WHERE IP = '{test_ip}'
        GROUP BY country
        ORDER BY total DESC
    """).fetchall()
    
    if country_data:
        print(f"   ✅ YES - This IP belongs to:")
        for country, attacks in country_data:
            print(f"      {country}: {attacks:,} attacks")
    else:
        print(f"   ❌ NO - No country data")
    
    # Check if we can get daily data for this IP (for volatile chart)
    print(f"\n4. VOLATILE CHART - Can we show day-to-day changes for this IP's country?")
    daily_data = conn.execute(f"""
        SELECT date, country, attacks
        FROM daily_ip_attacks
        WHERE IP = '{test_ip}'
        ORDER BY date
        LIMIT 5
    """).fetchall()
    
    if daily_data:
        print(f"   ✅ YES - Sample daily data:")
        for date, country, attacks in daily_data:
            print(f"      {date}: {country} - {attacks:,} attacks")
    else:
        print(f"   ❌ NO - No daily data")
    
    # Check ASN data for this IP
    print(f"\n5. ASN CHART - Can we show which ASN this IP belongs to?")
    asn_data = conn.execute(f"""
        SELECT asn_name, SUM(attacks) as total
        FROM daily_ip_attacks
        WHERE IP = '{test_ip}'
        GROUP BY asn_name
        ORDER BY total DESC
    """).fetchall()
    
    if asn_data:
        print(f"   ✅ YES - This IP belongs to:")
        for asn, attacks in asn_data:
            print(f"      {asn}: {attacks:,} attacks")
    else:
        print(f"   ❌ NO - No ASN data")
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY - What can we filter when an IP is selected?")
    print(f"{'='*70}")
    
    has_country = len(country_data) > 0
    has_daily = len(daily_data) > 0
    has_asn = len(asn_data) > 0
    
    print(f"\n✅ Country Chart: {'YES - Show this IPs country' if has_country else 'NO'}")
    print(f"✅ Volatile Chart: {'YES - Show this IPs country volatility' if has_daily else 'NO'}")
    print(f"✅ ASN Chart: {'YES - Show this IPs ASN' if has_asn else 'NO'}")
    
    if has_country and has_daily and has_asn:
        print(f"\n🎉 ALL CHARTS CAN BE FILTERED BY IP!")
        print(f"\nNote: Most IPs belong to ONE country and ONE ASN")
        print(f"      So these charts will typically show just 1 line each")
    
    # Show expected behavior
    print(f"\n{'='*70}")
    print("EXPECTED BEHAVIOR WHEN IP IS SELECTED:")
    print(f"{'='*70}")
    print(f"""
When user clicks IP {test_ip}:
- Date Chart: Shows attacks from this IP over time (orange line)
- Country Chart: Shows {country_data[0][0] if country_data else '?'} (this IP's country)
- Volatile Chart: Shows {country_data[0][0] if country_data else '?'} (this IP's country, day-to-day)
- ASN Chart: Shows {asn_data[0][0] if asn_data else '?'} (this IP's ASN)
- IP Chart: Shows only {test_ip}
- Username Chart: Shows top 10 usernames from {test_ip}
""")
    
    conn.close()
    print("="*70)

if __name__ == "__main__":
    main()
