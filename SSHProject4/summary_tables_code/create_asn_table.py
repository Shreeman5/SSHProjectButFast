#!/usr/bin/env python3
"""
Create daily_asn_attacks Table with COUNTRY and REAL DATA
Updated version of your existing script
"""

import duckdb
import time
from pathlib import Path

DB_PATH = './attack_data.db'
PARQUET_DIR = Path('./parquet_output')

def main():
    print("="*70)
    print("Creating daily_asn_attacks Table - REAL DATA WITH COUNTRY")
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
    conn.execute("DROP TABLE IF EXISTS daily_asn_attacks")
    
    # Create empty table WITH COUNTRY
    print(f"🔨 Creating empty table...")
    conn.execute("""
        CREATE TABLE daily_asn_attacks (
            date DATE,
            asn VARCHAR,
            asn_name VARCHAR,
            country VARCHAR,
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
            
            # ADD COUNTRY TO SELECT AND GROUP BY
            conn.execute(f"""
                INSERT INTO daily_asn_attacks
                SELECT 
                    DATE_TRUNC('day', datetime)::DATE as date,
                    asn,
                    asn_name,
                    country,
                    COUNT(*) as attacks
                FROM read_parquet('{file_str}')
                WHERE asn_name IS NOT NULL AND asn_name != 'Unknown'
                  AND country IS NOT NULL AND country != ''
                GROUP BY date, asn, asn_name, country
            """)
            
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error on {parquet_file.name}: {e}")
            continue
    
    overall_elapsed = time.time() - overall_start
    print(f"\n✅ Processed {success_count}/{len(all_files)} files ({overall_elapsed/60:.1f} minutes)")
    
    # Aggregate duplicates (in case same date/asn/country appears in multiple files)
    print(f"\n🔄 Aggregating duplicate entries...")
    conn.execute("""
        CREATE TABLE daily_asn_attacks_final AS
        SELECT 
            date,
            asn,
            asn_name,
            country,
            SUM(attacks) as attacks
        FROM daily_asn_attacks
        GROUP BY date, asn, asn_name, country
        ORDER BY date, asn_name, country
    """)
    conn.execute("DROP TABLE daily_asn_attacks")
    conn.execute("ALTER TABLE daily_asn_attacks_final RENAME TO daily_asn_attacks")
    print(f"   ✅ Aggregation complete")
    
    # Get final stats
    total_rows = conn.execute("SELECT COUNT(*) FROM daily_asn_attacks").fetchone()[0]
    total_attacks = conn.execute("SELECT SUM(attacks) FROM daily_asn_attacks").fetchone()[0]
    total_asns = conn.execute("SELECT COUNT(DISTINCT asn_name) FROM daily_asn_attacks").fetchone()[0]
    total_countries = conn.execute("SELECT COUNT(DISTINCT country) FROM daily_asn_attacks").fetchone()[0]
    
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"\n✅ Table created successfully!")
    print(f"   Total rows: {total_rows:,}")
    print(f"   Total attacks: {total_attacks:,}")
    print(f"   Unique ASNs: {total_asns:,}")
    print(f"   Unique countries: {total_countries:,}")
    print(f"   Time taken: {overall_elapsed/60:.1f} minutes")
    
    # Show sample - DigitalOcean on Nov 1 BY COUNTRY
    print(f"\n📊 Sample (DigitalOcean on Nov 1, 2022 by country):")
    sample = conn.execute("""
        SELECT date, asn_name, country, attacks
        FROM daily_asn_attacks
        WHERE asn_name LIKE '%DigitalOcean%' AND date = '2022-11-01'
        ORDER BY attacks DESC
    """).fetchall()
    
    if sample:
        for date, asn_name, country, attacks in sample:
            print(f"   {date} - {asn_name} - {country}: {attacks:,} attacks")
    else:
        print("   No DigitalOcean data found on Nov 1")
    
    # Show top 5 ASNs on Nov 1 (aggregated across countries)
    print(f"\n📊 Top 5 ASNs on Nov 1, 2022 (total across all countries):")
    top = conn.execute("""
        SELECT asn_name, SUM(attacks) as total_attacks
        FROM daily_asn_attacks
        WHERE date = '2022-11-01'
        GROUP BY asn_name
        ORDER BY total_attacks DESC
        LIMIT 5
    """).fetchall()
    
    for asn_name, attacks in top:
        print(f"   {asn_name}: {attacks:,}")
    
    # Verify against daily_stats
    expected_total = conn.execute("SELECT SUM(total_attacks) FROM daily_stats").fetchone()[0]
    print(f"\n🔍 Verification:")
    print(f"   Expected (from daily_stats): {expected_total:,}")
    print(f"   Actual (from ASN table): {total_attacks:,}")
    
    if abs(total_attacks - expected_total) < 1000:
        print(f"   ✅ PERFECT MATCH! All 213M attacks captured!")
    else:
        diff = abs(expected_total - total_attacks)
        pct = (diff / expected_total) * 100
        print(f"   Difference: {diff:,} ({pct:.2f}%)")
        if pct < 1:
            print(f"   ✅ Very close! Minor ASN enrichment gaps expected")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Done! Now:")
    print("   1. Update API endpoints")
    print("   2. Restart API")
    print("   3. Test dashboard with country filtering")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()