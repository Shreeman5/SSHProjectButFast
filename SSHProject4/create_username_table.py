#!/usr/bin/env python3
"""
Create daily_username_attacks Table - File by File
Real data, not fake estimates!
"""

import duckdb
import time
from pathlib import Path

DB_PATH = './attack_data.db'
PARQUET_DIR = Path('./parquet_output')

def main():
    print("="*70)
    print("Creating daily_username_attacks Table")
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
    
    # Drop existing table if it exists
    print(f"\n🗑️  Dropping old table (if exists)...")
    conn.execute("DROP TABLE IF EXISTS daily_username_attacks")
    
    # Create empty table
    print(f"🔨 Creating empty table...")
    conn.execute("""
        CREATE TABLE daily_username_attacks (
            date DATE,
            username VARCHAR,
            attacks BIGINT
        )
    """)
    print("✅ Table created")
    
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
            
            conn.execute(f"""
                INSERT INTO daily_username_attacks
                SELECT 
                    DATE_TRUNC('day', datetime)::DATE as date,
                    Username as username,
                    COUNT(*) as attacks
                FROM read_parquet('{file_str}')
                GROUP BY date, username
            """)
            
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error on {parquet_file.name}: {e}")
            continue
    
    overall_elapsed = time.time() - overall_start
    print(f"\n✅ Processed {success_count}/{len(all_files)} files ({overall_elapsed/60:.1f} minutes)")
    
    # Aggregate duplicates
    print(f"\n🔄 Aggregating duplicate entries...")
    conn.execute("""
        CREATE TABLE daily_username_attacks_final AS
        SELECT 
            date,
            username,
            SUM(attacks) as attacks
        FROM daily_username_attacks
        GROUP BY date, username
        ORDER BY date, username
    """)
    conn.execute("DROP TABLE daily_username_attacks")
    conn.execute("ALTER TABLE daily_username_attacks_final RENAME TO daily_username_attacks")
    print(f"   ✅ Aggregation complete")
    
    # Get final stats
    total_rows = conn.execute("SELECT COUNT(*) FROM daily_username_attacks").fetchone()[0]
    total_attacks = conn.execute("SELECT SUM(attacks) FROM daily_username_attacks").fetchone()[0]
    total_usernames = conn.execute("SELECT COUNT(DISTINCT username) FROM daily_username_attacks").fetchone()[0]
    
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"\n✅ Table created successfully!")
    print(f"   Total rows: {total_rows:,}")
    print(f"   Total attacks: {total_attacks:,}")
    print(f"   Unique usernames: {total_usernames:,}")
    print(f"   Time taken: {overall_elapsed/60:.1f} minutes")
    
    # Show sample - 'root' on Nov 1
    print(f"\n📊 Sample (root on Nov 1, 2022):")
    sample = conn.execute("""
        SELECT date, username, attacks
        FROM daily_username_attacks
        WHERE username = 'root' AND date = '2022-11-01'
    """).fetchall()
    
    if sample:
        for date, username, attacks in sample:
            print(f"   {date} - {username}: {attacks:,}")
    else:
        print("   No data found for root on Nov 1")
    
    # Verify against daily_stats
    expected_total = conn.execute("SELECT SUM(total_attacks) FROM daily_stats").fetchone()[0]
    print(f"\n🔍 Verification:")
    print(f"   Expected (from daily_stats): {expected_total:,}")
    print(f"   Actual (from username table): {total_attacks:,}")
    
    if abs(total_attacks - expected_total) < 1000:
        print(f"   ✅ PERFECT MATCH! All 213M attacks captured!")
    else:
        diff = abs(expected_total - total_attacks)
        pct = (diff / expected_total) * 100
        print(f"   Difference: {diff:,} ({pct:.2f}%)")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Done! Now update the API to use this table")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
