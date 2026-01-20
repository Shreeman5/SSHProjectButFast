#!/usr/bin/env python3
"""
Create daily_country_attacks by Processing One Partition at a Time
Avoids memory issues and file limit problems
"""

import duckdb
import time
from pathlib import Path

DB_PATH = './attack_data.db'
PARQUET_DIR = Path('./parquet_output')

def process_partition(conn, partition_path, partition_name):
    """Process a single partition (month) and insert into table"""
    
    print(f"\n{'='*70}")
    print(f"Processing: {partition_name}")
    print(f"{'='*70}")
    
    # Check if consolidated file exists
    consolidated = partition_path / "consolidated.parquet"
    if consolidated.exists():
        pattern = str(consolidated)
        print(f"✅ Using consolidated file")
    else:
        pattern = str(partition_path / "*.parquet")
        file_count = len(list(partition_path.glob("*.parquet")))
        print(f"📁 Using {file_count} individual files")
    
    # Get all countries in this partition
    print(f"\n🔍 Finding countries in {partition_name}...")
    countries = conn.execute(f"""
        SELECT DISTINCT country
        FROM read_parquet('{pattern}', union_by_name=true)
        WHERE country IS NOT NULL
        ORDER BY country
    """).fetchall()
    
    country_list = [c[0] for c in countries]
    print(f"   Found {len(country_list)} countries")
    
    # Process each country individually for this partition
    print(f"\n🔄 Processing countries...")
    success_count = 0
    
    for i, country in enumerate(country_list, 1):
        if i % 20 == 1 or i <= 5:
            print(f"   [{i}/{len(country_list)}] {country}")
        
        try:
            # Query this country's data from this partition only
            conn.execute(f"""
                INSERT INTO daily_country_attacks
                SELECT 
                    DATE_TRUNC('day', datetime)::DATE as date,
                    country,
                    COUNT(*) as attacks
                FROM read_parquet('{pattern}', union_by_name=true)
                WHERE country = '{country}'
                GROUP BY date, country
            """)
            success_count += 1
            
            if i % 20 == 0:
                print(f"   ... processed {i}/{len(country_list)}")
        
        except Exception as e:
            print(f"   ❌ Error for {country}: {e}")
    
    print(f"\n✅ Partition complete: {success_count}/{len(country_list)} countries")
    
    # Verify
    partition_total = conn.execute(f"""
        SELECT SUM(attacks) 
        FROM daily_country_attacks
        WHERE date IN (
            SELECT DISTINCT DATE_TRUNC('day', datetime)::DATE
            FROM read_parquet('{pattern}', union_by_name=true)
            LIMIT 1
        )
    """).fetchone()[0]
    
    print(f"   Attacks in table: {partition_total:,}")


def main():
    """Create table by processing each partition separately"""
    
    print("="*70)
    print("Create daily_country_attacks - Partition by Partition")
    print("Avoids memory/file limit issues")
    print("="*70)
    
    # Find partitions
    partitions = []
    for year_dir in sorted(PARQUET_DIR.glob("year=*")):
        for month_dir in sorted(year_dir.glob("month=*")):
            partitions.append((month_dir, month_dir.relative_to(PARQUET_DIR)))
    
    print(f"\nFound {len(partitions)} partitions:")
    for _, name in partitions:
        print(f"  - {name}")
    
    print(f"\n⏱️  Estimated time: ~30-60 minutes")
    
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
    start_time = time.time()
    
    for partition_path, partition_name in partitions:
        process_partition(conn, partition_path, str(partition_name))
    
    elapsed = time.time() - start_time
    
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
    print(f"   Time taken: {elapsed/60:.1f} minutes")
    
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
        print(f"   ✅ MATCH! Data is complete!")
    else:
        diff = expected_total - total_attacks
        pct = (diff / expected_total) * 100
        print(f"   ⚠️  Missing {diff:,} attacks ({pct:.1f}%)")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Done! Restart API: python api_summary_only.py")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
