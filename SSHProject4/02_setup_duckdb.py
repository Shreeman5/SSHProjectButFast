#!/usr/bin/env python3
"""
DuckDB Setup - No View Version
Only creates summary tables, no attacks view
API doesn't need the view anyway!
"""

import duckdb
from pathlib import Path
import configparser
import time

def create_database(parquet_directory, duckdb_path):
    """Create database with summary tables only"""
    
    print("="*70)
    print("DuckDB Setup - Summary Tables Only")
    print("No view creation - avoids file limit issues!")
    print("="*70)
    
    parquet_dir = Path(parquet_directory)
    
    # Find all files
    all_files = sorted(parquet_dir.glob("year=*/month=*/*.parquet"))
    print(f"\n📂 Found {len(all_files)} Parquet files")
    
    estimated_mins = (len(all_files) * 0.5) / 60
    print(f"⏱️  Estimated time: ~{estimated_mins:.0f} minutes")
    
    response = input("\nProceed? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled")
        return
    
    # Connect to database
    print(f"\n📂 Creating database: {duckdb_path}")
    conn = duckdb.connect(str(duckdb_path))
    conn.execute("SET threads TO 4")
    conn.execute("SET memory_limit = '4GB'")
    print("✅ Database created")
    
    # Create empty summary tables
    print("\n🔨 Creating empty summary tables...")
    
    conn.execute("DROP TABLE IF EXISTS daily_stats")
    conn.execute("""
        CREATE TABLE daily_stats (
            date DATE,
            total_attacks BIGINT,
            unique_ips BIGINT,
            unique_countries BIGINT,
            unique_usernames BIGINT
        )
    """)
    
    conn.execute("DROP TABLE IF EXISTS country_stats")
    conn.execute("""
        CREATE TABLE country_stats (
            country VARCHAR,
            country_code VARCHAR,
            continent VARCHAR,
            total_attacks BIGINT,
            unique_ips BIGINT,
            unique_usernames BIGINT,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            avg_latitude DOUBLE,
            avg_longitude DOUBLE
        )
    """)
    
    conn.execute("DROP TABLE IF EXISTS top_ips")
    conn.execute("""
        CREATE TABLE top_ips (
            IP VARCHAR,
            country VARCHAR,
            asn VARCHAR,
            asn_name VARCHAR,
            attack_count BIGINT,
            unique_usernames BIGINT,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP
        )
    """)
    
    conn.execute("DROP TABLE IF EXISTS username_stats")
    conn.execute("""
        CREATE TABLE username_stats (
            Username VARCHAR,
            attempt_count BIGINT,
            unique_ips BIGINT,
            unique_countries BIGINT,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP
        )
    """)
    
    conn.execute("DROP TABLE IF EXISTS hourly_patterns")
    conn.execute("""
        CREATE TABLE hourly_patterns (
            hour BIGINT,
            attack_count BIGINT,
            unique_ips BIGINT
        )
    """)
    
    print("✅ Empty tables created")
    
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
            
            # Daily stats
            conn.execute(f"""
                INSERT INTO daily_stats
                SELECT 
                    datetime::DATE as date,
                    COUNT(*) as total_attacks,
                    COUNT(DISTINCT IP) as unique_ips,
                    COUNT(DISTINCT country) as unique_countries,
                    COUNT(DISTINCT Username) as unique_usernames
                FROM read_parquet('{file_str}')
                GROUP BY date
            """)
            
            # Country stats
            conn.execute(f"""
                INSERT INTO country_stats
                SELECT 
                    country,
                    country_code,
                    continent,
                    COUNT(*) as total_attacks,
                    COUNT(DISTINCT IP) as unique_ips,
                    COUNT(DISTINCT Username) as unique_usernames,
                    MIN(datetime) as first_seen,
                    MAX(datetime) as last_seen,
                    AVG(latitude) as avg_latitude,
                    AVG(longitude) as avg_longitude
                FROM read_parquet('{file_str}')
                WHERE country IS NOT NULL
                GROUP BY country, country_code, continent
            """)
            
            # Top IPs
            conn.execute(f"""
                INSERT INTO top_ips
                SELECT 
                    IP,
                    COALESCE(country, 'Unknown') as country,
                    COALESCE(asn, 'Unknown') as asn,
                    COALESCE(asn_name, 'Unknown') as asn_name,
                    COUNT(*) as attack_count,
                    COUNT(DISTINCT Username) as unique_usernames,
                    MIN(datetime) as first_seen,
                    MAX(datetime) as last_seen
                FROM read_parquet('{file_str}')
                GROUP BY IP, country, asn, asn_name
            """)
            
            # Username stats
            conn.execute(f"""
                INSERT INTO username_stats
                SELECT 
                    Username,
                    COUNT(*) as attempt_count,
                    COUNT(DISTINCT IP) as unique_ips,
                    COUNT(DISTINCT country) as unique_countries,
                    MIN(datetime) as first_seen,
                    MAX(datetime) as last_seen
                FROM read_parquet('{file_str}')
                GROUP BY Username
            """)
            
            # Hourly patterns
            conn.execute(f"""
                INSERT INTO hourly_patterns
                SELECT 
                    EXTRACT(HOUR FROM datetime) as hour,
                    COUNT(*) as attack_count,
                    COUNT(DISTINCT IP) as unique_ips
                FROM read_parquet('{file_str}')
                GROUP BY hour
            """)
            
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error on {parquet_file.name}: {e}")
            continue
    
    total_elapsed = time.time() - overall_start
    print(f"\n✅ Processed {success_count}/{len(all_files)} files ({total_elapsed/60:.1f} minutes)")
    
    # Aggregate results
    print("\n🔄 Aggregating results...")
    
    print("   - daily_stats")
    conn.execute("""
        CREATE TABLE daily_stats_final AS
        SELECT 
            date,
            SUM(total_attacks) as total_attacks,
            MAX(unique_ips) as unique_ips,
            MAX(unique_countries) as unique_countries,
            MAX(unique_usernames) as unique_usernames
        FROM daily_stats
        GROUP BY date
        ORDER BY date
    """)
    conn.execute("DROP TABLE daily_stats")
    conn.execute("ALTER TABLE daily_stats_final RENAME TO daily_stats")
    
    print("   - country_stats")
    conn.execute("""
        CREATE TABLE country_stats_final AS
        SELECT 
            country,
            ANY_VALUE(country_code) as country_code,
            ANY_VALUE(continent) as continent,
            SUM(total_attacks) as total_attacks,
            SUM(unique_ips) as unique_ips,
            SUM(unique_usernames) as unique_usernames,
            MIN(first_seen) as first_seen,
            MAX(last_seen) as last_seen,
            AVG(avg_latitude) as avg_latitude,
            AVG(avg_longitude) as avg_longitude
        FROM country_stats
        GROUP BY country
        ORDER BY total_attacks DESC
    """)
    conn.execute("DROP TABLE country_stats")
    conn.execute("ALTER TABLE country_stats_final RENAME TO country_stats")
    
    print("   - top_ips")
    conn.execute("""
        CREATE TABLE top_ips_final AS
        SELECT 
            IP,
            ANY_VALUE(country) as country,
            ANY_VALUE(asn) as asn,
            ANY_VALUE(asn_name) as asn_name,
            SUM(attack_count) as attack_count,
            SUM(unique_usernames) as unique_usernames,
            MIN(first_seen) as first_seen,
            MAX(last_seen) as last_seen
        FROM top_ips
        GROUP BY IP
        ORDER BY attack_count DESC
        LIMIT 10000
    """)
    conn.execute("DROP TABLE top_ips")
    conn.execute("ALTER TABLE top_ips_final RENAME TO top_ips")
    
    print("   - username_stats")
    conn.execute("""
        CREATE TABLE username_stats_final AS
        SELECT 
            Username,
            SUM(attempt_count) as attempt_count,
            SUM(unique_ips) as unique_ips,
            SUM(unique_countries) as unique_countries,
            MIN(first_seen) as first_seen,
            MAX(last_seen) as last_seen
        FROM username_stats
        GROUP BY Username
        ORDER BY attempt_count DESC
        LIMIT 10000
    """)
    conn.execute("DROP TABLE username_stats")
    conn.execute("ALTER TABLE username_stats_final RENAME TO username_stats")
    
    print("   - hourly_patterns")
    conn.execute("""
        CREATE TABLE hourly_patterns_final AS
        SELECT 
            hour,
            SUM(attack_count) as attack_count,
            SUM(unique_ips) as unique_ips
        FROM hourly_patterns
        GROUP BY hour
        ORDER BY hour
    """)
    conn.execute("DROP TABLE hourly_patterns")
    conn.execute("ALTER TABLE hourly_patterns_final RENAME TO hourly_patterns")
    
    # Show summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    
    total = conn.execute("SELECT SUM(total_attacks) FROM daily_stats").fetchone()[0]
    countries = conn.execute("SELECT COUNT(*) FROM country_stats").fetchone()[0]
    ips = conn.execute("SELECT COUNT(*) FROM top_ips").fetchone()[0]
    usernames = conn.execute("SELECT COUNT(*) FROM username_stats").fetchone()[0]
    
    print(f"\n✅ Database created successfully!")
    print(f"   Total attacks: {total:,}")
    print(f"   Countries: {countries}")
    print(f"   Top IPs: {ips:,}")
    print(f"   Top usernames: {usernames:,}")
    print(f"   Processing rate: {len(all_files)/total_elapsed:.1f} files/sec")
    
    print(f"\n📊 Top 5 countries:")
    top5 = conn.execute("""
        SELECT country, total_attacks 
        FROM country_stats 
        ORDER BY total_attacks DESC 
        LIMIT 5
    """).fetchall()
    for country, attacks in top5:
        print(f"   {country}: {attacks:,}")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ Done! Next: create country table, then start API")
    print("="*70)


def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    try:
        parquet_directory = config['paths']['output_directory']
        duckdb_path = config['paths']['duckdb_path']
    except KeyError as e:
        print(f"❌ Missing config key: {e}")
        return
    
    create_database(parquet_directory, duckdb_path)


if __name__ == "__main__":
    main()