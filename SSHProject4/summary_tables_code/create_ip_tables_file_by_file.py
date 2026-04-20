#!/usr/bin/env python3
"""
Create IP Tables - File by File Processing
Creates both daily_ip_attacks and daily_ip_username_attacks_temp tables
"""

import duckdb
import time
from pathlib import Path

DB_PATH = './attack_data.db'
PARQUET_DIR = Path('./parquet_output')

def main():
    print("="*70)
    print("Creating IP Tables - File by File")
    print("Creates: daily_ip_attacks + daily_ip_username_attacks_temp")
    print("="*70)
    
    # Find all Parquet files
    all_files = sorted(PARQUET_DIR.glob("year=*/month=*/*.parquet"))
    print(f"\n📂 Found {len(all_files)} Parquet files")
    
    estimated_mins = (len(all_files) * 0.5) / 60
    print(f"⏱️  Estimated time: ~{estimated_mins:.0f} minutes")
    
    response = input("\nProceed? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled")
        return
    
    # Connect to database
    conn = duckdb.connect(DB_PATH)
    
    # Drop existing tables if they exist
    print(f"\n🗑️  Dropping old tables (if exist)...")
    conn.execute("DROP TABLE IF EXISTS daily_ip_attacks")
    conn.execute("DROP TABLE IF EXISTS daily_ip_username_attacks_temp")
    
    # Create empty tables
    print(f"🔨 Creating empty tables...")
    
    # Table 1: Aggregated by IP
    conn.execute("""
        CREATE TABLE daily_ip_attacks (
            date DATE,
            ip VARCHAR,
            country VARCHAR,
            asn_name VARCHAR,
            attacks BIGINT
        )
    """)
    
    # Table 2: Detailed IP + username
    conn.execute("""
        CREATE TABLE daily_ip_username_attacks_temp (
            date DATE,
            IP VARCHAR,
            username VARCHAR,
            country VARCHAR,
            asn_name VARCHAR,
            attacks BIGINT
        )
    """)
    
    print("✅ Tables created")
    
    # Process files one by one
    print(f"\n🔄 Processing {len(all_files)} files...")
    
    overall_start = time.time()
    success_count = 0
    
    for i, parquet_file in enumerate(all_files, 1):
        
        if i == 1 or i % 100 == 0 or i == len(all_files):
            elapsed = time.time() - overall_start
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (len(all_files) - i) / rate if rate > 0 else 0
            print(f"   [{i}/{len(all_files)}] Processing... ({rate:.1f} files/sec, ~{remaining/60:.1f}min left)")
        
        try:
            file_str = str(parquet_file)
            
            # Insert into daily_ip_attacks (aggregated by IP)
            conn.execute(f"""
                INSERT INTO daily_ip_attacks
                SELECT 
                    DATE_TRUNC('day', datetime)::DATE as date,
                    IP as ip,
                    country,
                    asn_name,
                    COUNT(*) as attacks
                FROM read_parquet('{file_str}')
                WHERE IP IS NOT NULL 
                  AND country IS NOT NULL AND country != ''
                  AND asn_name IS NOT NULL AND asn_name != ''
                GROUP BY date, ip, country, asn_name
            """)
            
            # Insert into daily_ip_username_attacks_temp (detailed)
            conn.execute(f"""
                INSERT INTO daily_ip_username_attacks_temp
                SELECT 
                    DATE_TRUNC('day', datetime)::DATE as date,
                    IP,
                    Username as username,
                    country,
                    asn_name,
                    COUNT(*) as attacks
                FROM read_parquet('{file_str}')
                WHERE IP IS NOT NULL
                  AND Username IS NOT NULL AND Username != ''
                  AND country IS NOT NULL AND country != ''
                  AND asn_name IS NOT NULL AND asn_name != ''
                GROUP BY date, IP, username, country, asn_name
            """)
            
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error on {parquet_file.name}: {e}")
            continue
    
    overall_elapsed = time.time() - overall_start
    print(f"\n✅ Processed {success_count}/{len(all_files)} files ({overall_elapsed/60:.1f} minutes)")
    
    # Aggregate duplicates for daily_ip_attacks
    print(f"\n🔄 Aggregating daily_ip_attacks duplicates...")
    conn.execute("""
        CREATE TABLE daily_ip_attacks_final AS
        SELECT 
            date,
            ip,
            country,
            asn_name,
            SUM(attacks) as attacks
        FROM daily_ip_attacks
        GROUP BY date, ip, country, asn_name
        ORDER BY date, ip
    """)
    conn.execute("DROP TABLE daily_ip_attacks")
    conn.execute("ALTER TABLE daily_ip_attacks_final RENAME TO daily_ip_attacks")
    print(f"   ✅ daily_ip_attacks aggregation complete")
    
    # Get final stats
    ip_rows = conn.execute("SELECT COUNT(*) FROM daily_ip_attacks").fetchone()[0]
    ip_attacks = conn.execute("SELECT SUM(attacks) FROM daily_ip_attacks").fetchone()[0]
    unique_ips = conn.execute("SELECT COUNT(DISTINCT ip) FROM daily_ip_attacks").fetchone()[0]
    
    temp_rows = conn.execute("SELECT COUNT(*) FROM daily_ip_username_attacks_temp").fetchone()[0]
    temp_attacks = conn.execute("SELECT SUM(attacks) FROM daily_ip_username_attacks_temp").fetchone()[0]
    
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"\n✅ Tables created successfully!")
    
    print(f"\n📊 daily_ip_attacks:")
    print(f"   Total rows: {ip_rows:,}")
    print(f"   Total attacks: {ip_attacks:,}")
    print(f"   Unique IPs: {unique_ips:,}")
    
    print(f"\n📊 daily_ip_username_attacks_temp:")
    print(f"   Total rows: {temp_rows:,}")
    print(f"   Total attacks: {temp_attacks:,}")
    
    print(f"\n⏱️  Time taken: {overall_elapsed/60:.1f} minutes")
    
    # Show sample from daily_ip_attacks
    print(f"\n📊 Sample from daily_ip_attacks (Nov 1):")
    sample = conn.execute("""
        SELECT date, ip, country, asn_name, attacks
        FROM daily_ip_attacks
        WHERE date = '2022-11-01'
        ORDER BY attacks DESC
        LIMIT 5
    """).fetchall()
    
    for date, ip, country, asn, attacks in sample:
        print(f"   {ip:15s} ({country[:15]:15s}) - {asn[:30]:30s}: {attacks:>5,}")
    
    # Verify against daily_stats
    expected_total = conn.execute("SELECT SUM(total_attacks) FROM daily_stats").fetchone()[0]
    print(f"\n🔍 Verification:")
    print(f"   Expected (from daily_stats): {expected_total:,}")
    print(f"   Actual (daily_ip_attacks): {ip_attacks:,}")
    
    if abs(ip_attacks - expected_total) < 1000:
        print(f"   ✅ PERFECT MATCH!")
    else:
        diff = abs(expected_total - ip_attacks)
        pct = (diff / expected_total) * 100
        print(f"   Difference: {diff:,} ({pct:.2f}%)")
        if pct < 1:
            print(f"   ✅ Very close! Minor filtering expected")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Done! Next step:")
    print("   Run: python3 summary_tables_code/create_ip_table.py")
    print("   This will finalize daily_ip_username_attacks from the temp table")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
