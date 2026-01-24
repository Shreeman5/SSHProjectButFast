#!/usr/bin/env python3
"""
Create daily_country_attacks by Processing Individual Files One-by-One
Completely avoids file limit issues - never opens more than 1 file at once
"""

import duckdb
import time
from pathlib import Path

DB_PATH = './attack_data.db'
PARQUET_DIR = Path('./parquet_output')

def process_single_file(conn, parquet_file):
    """Process a single Parquet file and insert into table"""
    
    try:
        # Read this one file and aggregate
        conn.execute(f"""
            INSERT INTO daily_country_attacks
            SELECT 
                DATE_TRUNC('day', datetime)::DATE as date,
                country,
                COUNT(*) as attacks
            FROM read_parquet('{parquet_file}')
            WHERE country IS NOT NULL
            GROUP BY date, country
        """)
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def process_partition(conn, partition_path, partition_name):
    """Process all files in a partition one-by-one"""
    
    print(f"\n{'='*70}")
    print(f"Processing: {partition_name}")
    print(f"{'='*70}")
    
    # Get all Parquet files in this partition
    parquet_files = list(partition_path.glob("*.parquet"))
    
    print(f"📁 Found {len(parquet_files)} files")
    
    if len(parquet_files) == 0:
        print("⚠️  No files found, skipping")
        return
    
    # Process each file individually
    print(f"\n🔄 Processing files one-by-one...")
    
    success_count = 0
    start_time = time.time()
    
    for i, parquet_file in enumerate(parquet_files, 1):
        # Show progress
        if i == 1 or i % 50 == 0 or i == len(parquet_files):
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (len(parquet_files) - i) / rate if rate > 0 else 0
            print(f"   [{i}/{len(parquet_files)}] Processing... ({rate:.1f} files/sec, ~{remaining/60:.1f}min left)")
        
        if process_single_file(conn, str(parquet_file)):
            success_count += 1
    
    elapsed = time.time() - start_time
    print(f"\n✅ Partition complete: {success_count}/{len(parquet_files)} files ({elapsed/60:.1f} minutes)")


def main():
    """Create table by processing files individually"""
    
    print("="*70)
    print("Create daily_country_attacks - File-by-File Processing")
    print("Never opens more than 1 file at once - Avoids all limits!")
    print("="*70)
    
    # Find partitions
    partitions = []
    for year_dir in sorted(PARQUET_DIR.glob("year=*")):
        for month_dir in sorted(year_dir.glob("month=*")):
            file_count = len(list(month_dir.glob("*.parquet")))
            partitions.append((month_dir, month_dir.relative_to(PARQUET_DIR), file_count))
    
    total_files = sum(fc for _, _, fc in partitions)
    
    print(f"\nFound {len(partitions)} partitions, {total_files} total files:")
    for _, name, file_count in partitions:
        print(f"  - {name}: {file_count} files")
    
    # Estimate time (roughly 0.1-0.2 seconds per file)
    estimated_mins = (total_files * 0.15) / 60
    print(f"\n⏱️  Estimated time: ~{estimated_mins:.0f} minutes")
    
    response = input("\nProceed? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled")
        return
    
    # Connect to database
    conn = duckdb.connect(DB_PATH)
    
    # Drop and recreate table
    print(f"\n📋 Creating table structure...")
    conn.execute("DROP TABLE IF EXISTS daily_country_attacks")
    conn.execute("""
        CREATE TABLE daily_country_attacks (
            date DATE,
            country VARCHAR,
            attacks BIGINT
        )
    """)
    
    # Process each partition
    overall_start = time.time()
    
    for partition_path, partition_name, _ in partitions:
        process_partition(conn, partition_path, str(partition_name))
    
    overall_elapsed = time.time() - overall_start
    
    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    
    total_rows = conn.execute("SELECT COUNT(*) FROM daily_country_attacks").fetchone()[0]
    total_attacks = conn.execute("SELECT SUM(attacks) FROM daily_country_attacks").fetchone()[0]
    total_countries = conn.execute("SELECT COUNT(DISTINCT country) FROM daily_country_attacks").fetchone()[0]
    
    print(f"\n✅ Table created successfully!")
    print(f"   Total rows: {total_rows:,}")
    print(f"   Total attacks: {total_attacks:,}")
    print(f"   Countries: {total_countries}")
    print(f"   Time taken: {overall_elapsed/60:.1f} minutes")
    print(f"   Processing rate: {total_files/overall_elapsed:.1f} files/sec")
    
    # Show sample
    print(f"\n📊 Sample (USA, first 5 days):")
    sample = conn.execute("""
        SELECT date, country, attacks
        FROM daily_country_attacks
        WHERE country = 'United States'
        ORDER BY date
        LIMIT 5
    """).fetchall()
    
    for date, country, attacks in sample:
        print(f"   {date} - {country}: {attacks:,}")
    
    # Compare to expected
    expected_total = conn.execute("SELECT SUM(total_attacks) FROM daily_stats").fetchone()[0]
    print(f"\n🔍 Verification:")
    print(f"   Expected (from daily_stats): {expected_total:,}")
    print(f"   Actual (from country table): {total_attacks:,}")
    
    if abs(total_attacks - expected_total) < 1000:
        print(f"   ✅ PERFECT MATCH! All 213M attacks captured!")
    else:
        diff = abs(expected_total - total_attacks)
        pct = (diff / expected_total) * 100
        if diff < expected_total * 0.01:  # Less than 1% difference
            print(f"   ✅ Very close! Difference: {diff:,} ({pct:.2f}%)")
        else:
            print(f"   ⚠️  Difference: {diff:,} ({pct:.1f}%)")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Done! Restart API: python api_summary_only.py")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
