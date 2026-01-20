#!/usr/bin/env python3
"""
Rebuild daily_stats Table
Carefully rebuilds from partitions to avoid duplicates
"""

import duckdb
from pathlib import Path
import configparser

def rebuild_daily_stats(duckdb_path, parquet_directory):
    """Rebuild daily_stats from individual partitions"""
    
    conn = duckdb.connect(str(duckdb_path))
    parquet_directory = Path(parquet_directory)
    
    print("="*70)
    print("Rebuilding daily_stats Table")
    print("="*70)
    
    # Find all partitions
    partitions = []
    for year_dir in sorted(parquet_directory.glob("year=*")):
        for month_dir in sorted(year_dir.glob("month=*")):
            partitions.append(month_dir)
    
    print(f"\n📂 Found {len(partitions)} partitions\n")
    
    # Drop existing daily_stats
    print("🗑️  Dropping old daily_stats table...")
    conn.execute("DROP TABLE IF EXISTS daily_stats")
    
    # Create new empty table
    print("📊 Creating new daily_stats table...")
    conn.execute("""
        CREATE TABLE daily_stats (
            date DATE,
            total_attacks BIGINT,
            unique_ips BIGINT,
            unique_countries BIGINT,
            unique_usernames BIGINT
        )
    """)
    
    # Process each partition separately
    for i, partition_dir in enumerate(partitions, 1):
        partition_name = partition_dir.relative_to(parquet_directory)
        print(f"\n[{i}/{len(partitions)}] Processing {partition_name}")
        
        # Check if consolidated file exists
        consolidated = partition_dir / "consolidated.parquet"
        if consolidated.exists():
            pattern = str(consolidated)
            print(f"   ✅ Using consolidated file")
        else:
            pattern = str(partition_dir / "*.parquet")
            file_count = len(list(partition_dir.glob("*.parquet")))
            print(f"   📁 Using {file_count} individual files")
        
        try:
            # Aggregate this partition and insert
            conn.execute(f"""
                INSERT INTO daily_stats
                SELECT 
                    DATE_TRUNC('day', datetime) as date,
                    COUNT(*) as total_attacks,
                    COUNT(DISTINCT IP) as unique_ips,
                    COUNT(DISTINCT country) as unique_countries,
                    COUNT(DISTINCT Username) as unique_usernames
                FROM read_parquet('{pattern}', union_by_name=true)
                GROUP BY date
            """)
            
            # Get row count for this partition
            result = conn.execute(f"""
                SELECT COUNT(*), SUM(total_attacks) 
                FROM daily_stats 
                WHERE date >= (
                    SELECT MIN(DATE_TRUNC('day', datetime)) 
                    FROM read_parquet('{pattern}', union_by_name=true, filename=true)
                    LIMIT 1
                )
            """).fetchone()
            
            print(f"   ✅ Added {result[1]:,} attacks")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue
    
    # Show summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    
    total = conn.execute("SELECT SUM(total_attacks) FROM daily_stats").fetchone()[0]
    days = conn.execute("SELECT COUNT(*) FROM daily_stats").fetchone()[0]
    
    print(f"\n✅ Total attacks: {total:,}")
    print(f"✅ Days: {days}")
    print(f"✅ Average per day: {total//days:,}")
    
    # Show first few days
    print("\n📅 First 5 days:")
    first_days = conn.execute("""
        SELECT date, total_attacks 
        FROM daily_stats 
        ORDER BY date 
        LIMIT 5
    """).fetchall()
    
    for date, attacks in first_days:
        print(f"   {date}: {attacks:,} attacks")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ daily_stats Rebuilt Successfully!")
    print("="*70)
    print("\nNext: Restart api_summary_only.py and refresh dashboard")


def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    duckdb_path = config['paths']['duckdb_path']
    parquet_directory = config['paths']['output_directory']
    
    print(f"\n📊 Database: {duckdb_path}")
    print(f"📂 Parquet: {parquet_directory}\n")
    
    response = input("Rebuild daily_stats? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled")
        return
    
    rebuild_daily_stats(duckdb_path, parquet_directory)


if __name__ == "__main__":
    main()
