#!/usr/bin/env python3
"""
Verify terminal data vs API data for Countries, IPs, and Usernames
"""

import duckdb
import requests
import json

conn = duckdb.connect('./attack_data.db', read_only=True)

START_DATE = '2022-11-10'
END_DATE = '2022-12-01'

print("="*80)
print(f"DATABASE vs API COMPARISON: {START_DATE} to {END_DATE}")
print("="*80)

# ============================================================================
# 1. COUNTRIES
# ============================================================================
print("\n1️⃣  COUNTRIES")
print("-"*80)

# Database query
db_countries = conn.execute(f"""
    SELECT country, SUM(attacks) as total_attacks
    FROM daily_country_attacks
    WHERE date BETWEEN '{START_DATE}' AND '{END_DATE}'
    GROUP BY country
    ORDER BY total_attacks DESC
    LIMIT 10
""").fetchall()

print("DATABASE TOP 10:")
for i, (country, attacks) in enumerate(db_countries, 1):
    print(f"  {i:2d}. {country[:30]:30s} {attacks:>12,}")

# API query
try:
    response = requests.get(f'http://localhost:5000/api/country_attacks?start={START_DATE}&end={END_DATE}')
    api_data = response.json()
    
    # Aggregate by country
    country_totals = {}
    for item in api_data:
        country = item['country']
        attacks = item['attacks']
        country_totals[country] = country_totals.get(country, 0) + attacks
    
    api_countries = sorted(country_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    
    print("\nAPI TOP 10:")
    for i, (country, attacks) in enumerate(api_countries, 1):
        print(f"  {i:2d}. {country[:30]:30s} {attacks:>12,}")
    
    # Compare
    db_set = set([c for c, _ in db_countries])
    api_set = set([c for c, _ in api_countries])
    
    if db_set == api_set:
        print("\n✅ MATCH - Same countries in database and API")
    else:
        print("\n❌ MISMATCH!")
        print(f"   In DB but not API: {db_set - api_set}")
        print(f"   In API but not DB: {api_set - db_set}")
except Exception as e:
    print(f"\n❌ API Error: {e}")

# ============================================================================
# 2. IPs
# ============================================================================
print("\n\n2️⃣  IPs")
print("-"*80)

# Database query
db_ips = conn.execute(f"""
    SELECT IP, SUM(attacks) as total_attacks
    FROM daily_ip_attacks
    WHERE date BETWEEN '{START_DATE}' AND '{END_DATE}'
    GROUP BY IP
    ORDER BY total_attacks DESC
    LIMIT 10
""").fetchall()

print("DATABASE TOP 10:")
for i, (ip, attacks) in enumerate(db_ips, 1):
    print(f"  {i:2d}. {ip:30s} {attacks:>12,}")

# API query
try:
    response = requests.get(f'http://localhost:5000/api/ip_attacks?start={START_DATE}&end={END_DATE}')
    api_data = response.json()
    
    # Aggregate by IP
    ip_totals = {}
    for item in api_data:
        ip = item['IP']
        attacks = item['attacks']
        ip_totals[ip] = ip_totals.get(ip, 0) + attacks
    
    api_ips = sorted(ip_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    
    print("\nAPI TOP 10:")
    for i, (ip, attacks) in enumerate(api_ips, 1):
        print(f"  {i:2d}. {ip:30s} {attacks:>12,}")
    
    # Compare
    db_set = set([ip for ip, _ in db_ips])
    api_set = set([ip for ip, _ in api_ips])
    
    if db_set == api_set:
        print("\n✅ MATCH - Same IPs in database and API")
    else:
        print("\n❌ MISMATCH!")
        print(f"   In DB but not API: {db_set - api_set}")
        print(f"   In API but not DB: {api_set - db_set}")
except Exception as e:
    print(f"\n❌ API Error: {e}")

# ============================================================================
# 3. USERNAMES
# ============================================================================
print("\n\n3️⃣  USERNAMES")
print("-"*80)

# Database query
db_usernames = conn.execute(f"""
    SELECT username, SUM(attacks) as total_attacks
    FROM daily_username_attacks
    WHERE date BETWEEN '{START_DATE}' AND '{END_DATE}'
    GROUP BY username
    ORDER BY total_attacks DESC
    LIMIT 10
""").fetchall()

print("DATABASE TOP 10:")
for i, (username, attacks) in enumerate(db_usernames, 1):
    print(f"  {i:2d}. {username[:30]:30s} {attacks:>12,}")

# API query
try:
    response = requests.get(f'http://localhost:5000/api/username_attacks?start={START_DATE}&end={END_DATE}')
    api_data = response.json()
    
    # Aggregate by username
    username_totals = {}
    for item in api_data:
        username = item['username']
        attacks = item['attacks']
        username_totals[username] = username_totals.get(username, 0) + attacks
    
    api_usernames = sorted(username_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    
    print("\nAPI TOP 10:")
    for i, (username, attacks) in enumerate(api_usernames, 1):
        print(f"  {i:2d}. {username[:30]:30s} {attacks:>12,}")
    
    # Compare
    db_set = set([u for u, _ in db_usernames])
    api_set = set([u for u, _ in api_usernames])
    
    if db_set == api_set:
        print("\n✅ MATCH - Same usernames in database and API")
    else:
        print("\n❌ MISMATCH!")
        print(f"   In DB but not API: {db_set - api_set}")
        print(f"   In API but not DB: {api_set - db_set}")
except Exception as e:
    print(f"\n❌ API Error: {e}")

conn.close()

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("Run this script to see if database and API return the same top 10 entities.")
print("If there are mismatches, the API endpoints need to be fixed.")
print("="*80)
