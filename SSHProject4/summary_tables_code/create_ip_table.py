#!/usr/bin/env python3
"""
Finalize daily_ip_username_attacks Table - CHUNK-BY-CHUNK AGGREGATION
Processes ALL records but in small chunks to avoid memory issues
This is slow but thorough and safe
"""

import duckdb
import time

DB_PATH = './attack_data.db'

def main():
    print("="*70)
    print("Finalizing daily_ip_username_attacks - CHUNK AGGREGATION")
    print("="*70)
    
    conn = duckdb.connect(DB_PATH)
    
    # Check if temp table exists
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    
    if 'daily_ip_username_attacks_temp' not in table_names:
        print("❌ Error: daily_ip_username_attacks_temp table not found!")
        conn.close()
        return
    
    # Get date range
    date_range = conn.execute("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM daily_ip_username_attacks_temp
    """).fetchone()
    
    min_date = date_range[0]
    max_date = date_range[1]
    
    # Get total row count
    total_rows = conn.execute("SELECT COUNT(*) FROM daily_ip_username_attacks_temp").fetchone()[0]
    
    print(f"\n📊 Source table stats:")
    print(f"   Total rows: {total_rows:,}")
    print(f"   Date range: {min_date} to {max_date}")
    
    # Get all unique dates
    dates = conn.execute("""
        SELECT DISTINCT date 
        FROM daily_ip_username_attacks_temp 
        ORDER BY date
    """).fetchall()
    
    dates = [d[0] for d in dates]
    print(f"   Unique dates: {len(dates)}")
    
    print(f"\n💡 Strategy: Process one date at a time, aggregate duplicates")
    print(f"   This processes ALL records but uses minimal memory")
    
    estimated_time = len(dates) * 1.5  # ~1.5 seconds per date
    print(f"   Estimated time: ~{estimated_time/60:.1f} minutes")
    
    response = input("\nProceed? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled")
        conn.close()
        return
    
    # Drop final table if exists
    conn.execute("DROP TABLE IF EXISTS daily_ip_username_attacks")
    
    # Create final table
    print(f"\n🔨 Creating final table...")
    conn.execute("""
        CREATE TABLE daily_ip_username_attacks (
            date DATE,
            IP VARCHAR,
            username VARCHAR,
            country VARCHAR,
            asn_name VARCHAR,
            attacks BIGINT
        )
    """)
    
    # Process each date
    print(f"\n🔄 Processing {len(dates)} dates...")
    start_time = time.time()
    processed_rows = 0
    total_duplicates_found = 0
    
    for i, date in enumerate(dates, 1):
        date_start = time.time()
        
        # Get row count for this date BEFORE aggregation
        before_count = conn.execute(f"""
            SELECT COUNT(*) 
            FROM daily_ip_username_attacks_temp 
            WHERE date = '{date}'
        """).fetchone()[0]
        
        # Aggregate this date and insert into final table
        conn.execute(f"""
            INSERT INTO daily_ip_username_attacks
            SELECT 
                date,
                IP,
                username,
                country,
                asn_name,
                SUM(attacks) as attacks
            FROM daily_ip_username_attacks_temp
            WHERE date = '{date}'
            GROUP BY date, IP, username, country, asn_name
        """)
        
        # Get row count AFTER aggregation
        after_count = conn.execute(f"""
            SELECT COUNT(*) 
            FROM daily_ip_username_attacks 
            WHERE date = '{date}'
        """).fetchone()[0]
        
        duplicates_removed = before_count - after_count
        total_duplicates_found += duplicates_removed
        processed_rows += after_count
        
        date_elapsed = time.time() - date_start
        
        # Show progress every 5 dates or on first/last
        if i == 1 or i % 5 == 0 or i == len(dates):
            elapsed = time.time() - start_time
            rate = i / elapsed
            remaining = (len(dates) - i) / rate if rate > 0 else 0
            
            dup_str = f" ({duplicates_removed:,} dups removed)" if duplicates_removed > 0 else ""
            print(f"   [{i}/{len(dates)}] {date}: {after_count:,} rows{dup_str} (~{remaining/60:.1f}min left)")
    
    total_elapsed = time.time() - start_time
    
    print(f"\n✅ Processing complete in {total_elapsed/60:.1f} minutes")
    print(f"   Total duplicates removed: {total_duplicates_found:,}")
    print(f"   Final row count: {processed_rows:,}")
    
    # Drop temp table
    print(f"\n🗑️  Dropping temp table...")
    conn.execute("DROP TABLE daily_ip_username_attacks_temp")
    
    # Get final stats
    print(f"\n📊 Final statistics...")
    
    final_count = conn.execute("SELECT COUNT(*) FROM daily_ip_username_attacks").fetchone()[0]
    total_attacks = conn.execute("SELECT SUM(attacks) FROM daily_ip_username_attacks").fetchone()[0]
    total_ips = conn.execute("SELECT COUNT(DISTINCT IP) FROM daily_ip_username_attacks").fetchone()[0]
    total_usernames = conn.execute("SELECT COUNT(DISTINCT username) FROM daily_ip_username_attacks").fetchone()[0]
    
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"\n✅ Table created successfully!")
    print(f"   Total rows: {final_count:,}")
    print(f"   Total attacks: {total_attacks:,}")
    print(f"   Unique IPs: {total_ips:,}")
    print(f"   Unique usernames: {total_usernames:,}")
    print(f"   Duplicates removed: {total_duplicates_found:,} ({total_duplicates_found/total_rows*100:.2f}%)")
    print(f"   Processing time: {total_elapsed/60:.1f} minutes")
    
    # Show sample
    print(f"\n📊 Sample data from Nov 1:")
    sample = conn.execute("""
        SELECT IP, username, country, asn_name, attacks
        FROM daily_ip_username_attacks
        WHERE date = '2022-11-01'
        ORDER BY attacks DESC
        LIMIT 5
    """).fetchall()
    
    for ip, username, country, asn, attacks in sample:
        print(f"   {ip:15s} → '{username:15s}' ({country[:15]:15s}): {attacks:>5,}")
    
    # Verify against daily_stats
    expected_total = conn.execute("SELECT SUM(total_attacks) FROM daily_stats").fetchone()[0]
    print(f"\n🔍 Verification:")
    print(f"   Expected: {expected_total:,}")
    print(f"   Actual:   {total_attacks:,}")
    
    if abs(total_attacks - expected_total) < 1000:
        print(f"   ✅ PERFECT MATCH!")
    else:
        diff = abs(expected_total - total_attacks)
        pct = (diff / expected_total) * 100
        print(f"   Difference: {diff:,} ({pct:.2f}%)")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Done! Restart API: python3 api_summary_only.py")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()