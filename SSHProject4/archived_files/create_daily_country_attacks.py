#!/usr/bin/env python3
"""
Create daily_country_attacks Table
Processes one country at a time to avoid memory issues
"""

import duckdb
import time

DB_PATH = './attack_data.db'

def create_table_for_top_countries():
    """Create daily_country_attacks for ALL countries"""
    
    conn = duckdb.connect(DB_PATH)
    
    print("="*70)
    print("Creating daily_country_attacks Table")
    print("Processing ALL countries individually")
    print("="*70)
    
    # Get ALL countries
    print("\n📊 Finding all countries...")
    all_countries = conn.execute("""
        SELECT country, total_attacks
        FROM country_stats
        ORDER BY total_attacks DESC
    """).fetchall()
    
    print(f"Found {len(all_countries)} countries")
    print(f"Top 10:")
    for country, attacks in all_countries[:10]:
        print(f"  - {country}: {attacks:,} total attacks")
    print(f"... and {len(all_countries) - 10} more countries")
    
    estimated_time = len(all_countries) * 30 / 60  # ~30 seconds per country
    print(f"\n⏱️  Estimated time: {estimated_time:.0f} minutes")
    
    response = input("\nProcess all countries? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled")
        conn.close()
        return
    
    # Drop existing table if any
    conn.execute("DROP TABLE IF EXISTS daily_country_attacks")
    
    # Create empty table
    print("\n📋 Creating table structure...")
    conn.execute("""
        CREATE TABLE daily_country_attacks (
            date DATE,
            country VARCHAR,
            attacks BIGINT
        )
    """)
    
    # Process each country individually
    print(f"\n🔄 Processing {len(all_countries)} countries...")
    
    success_count = 0
    error_count = 0
    
    for i, (country, total) in enumerate(all_countries, 1):
        # Show progress every 10 countries
        if i % 10 == 1 or i <= 10:
            print(f"\n[{i}/{len(all_countries)}] {country}: {total:,} attacks")
        
        start = time.time()
        
        try:
            # Query just this country's data
            conn.execute(f"""
                INSERT INTO daily_country_attacks
                SELECT 
                    DATE_TRUNC('day', datetime)::DATE as date,
                    country,
                    COUNT(*) as attacks
                FROM attacks
                WHERE country = '{country}'
                GROUP BY date, country
            """)
            
            success_count += 1
            
            # Brief status for non-displayed countries
            if i % 10 != 1 and i > 10:
                if i % 50 == 0:
                    print(f"  ... processed {i}/{len(all_countries)} countries")
        
        except Exception as e:
            print(f"      ❌ Error for {country}: {e}")
            error_count += 1
            continue
    
    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    
    total_rows = conn.execute("SELECT COUNT(*) FROM daily_country_attacks").fetchone()[0]
    total_attacks = conn.execute("SELECT SUM(attacks) FROM daily_country_attacks").fetchone()[0]
    countries_in_table = conn.execute("SELECT COUNT(DISTINCT country) FROM daily_country_attacks").fetchone()[0]
    
    print(f"\n✅ Created daily_country_attacks")
    print(f"   Countries processed: {countries_in_table}")
    print(f"   Total rows: {total_rows:,}")
    print(f"   Total attacks: {total_attacks:,}")
    print(f"   Success: {success_count}")
    print(f"   Errors: {error_count}")
    
    # Show sample
    print("\n📅 Sample data (first 5 days, USA):")
    sample = conn.execute("""
        SELECT date, country, attacks
        FROM daily_country_attacks
        WHERE country = 'United States'
        ORDER BY date
        LIMIT 5
    """).fetchall()
    
    for date, country, attacks in sample:
        print(f"   {date} - {country}: {attacks:,}")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ Done! Restart API to see real data.")
    print("="*70)


if __name__ == "__main__":
    create_table_for_top_countries()
