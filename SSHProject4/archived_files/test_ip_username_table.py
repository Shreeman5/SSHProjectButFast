#!/usr/bin/env python3
"""
Quick test to verify daily_ip_username_attacks table works
"""

import duckdb

DB_PATH = './attack_data.db'

def main():
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    print("="*70)
    print("TESTING daily_ip_username_attacks TABLE")
    print("="*70)
    
    # Check table exists
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    
    if 'daily_ip_username_attacks' not in table_names:
        print("\n❌ Table daily_ip_username_attacks NOT FOUND!")
        print("   Did you run the finalize script?")
        conn.close()
        return
    
    print("\n✅ Table exists")
    
    # Get a sample IP with lots of data
    sample_ip = conn.execute("""
        SELECT IP, SUM(attacks) as total
        FROM daily_ip_username_attacks
        GROUP BY IP
        ORDER BY total DESC
        LIMIT 1
    """).fetchone()
    
    if not sample_ip:
        print("\n❌ Table is EMPTY!")
        conn.close()
        return
    
    test_ip = sample_ip[0]
    total_attacks = sample_ip[1]
    
    print(f"\n📊 Testing with IP: {test_ip}")
    print(f"   Total attacks from this IP: {total_attacks:,}")
    
    # Get top usernames for this IP
    usernames = conn.execute(f"""
        SELECT username, SUM(attacks) as total
        FROM daily_ip_username_attacks
        WHERE IP = '{test_ip}'
        GROUP BY username
        ORDER BY total DESC
        LIMIT 10
    """).fetchall()
    
    print(f"\n✅ Top 10 usernames from {test_ip}:")
    for username, count in usernames:
        print(f"   {username:20s}: {count:>8,}")
    
    # Test the exact query the API will use
    print(f"\n🔍 Testing API query format:")
    api_test = conn.execute(f"""
        WITH top_usernames AS (
            SELECT username
            FROM daily_ip_username_attacks
            WHERE date BETWEEN '2022-11-01' AND '2023-01-08'
              AND IP = '{test_ip}'
            GROUP BY username
            ORDER BY SUM(attacks) DESC
            LIMIT 10
        )
        SELECT username, COUNT(*) as date_count
        FROM top_usernames
        GROUP BY username
    """).fetchall()
    
    print(f"   Found {len(api_test)} usernames")
    for username, date_count in api_test:
        print(f"   - {username}")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Table is working correctly!")
    print(f"\nNow test the API:")
    print(f"http://localhost:5000/api/username_attacks?start=2022-11-01&end=2023-01-08&ip={test_ip}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
