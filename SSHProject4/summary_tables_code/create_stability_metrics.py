#!/usr/bin/env python3
"""
Create country_stability_metrics table
Computes:
1. Jaccard similarity between consecutive days for ASN/IP/Username sets
2. Peak attack hours (top 3) with percentages
"""

import duckdb
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

DB_PATH = './attack_data.db'
PARQUET_DIR = Path('./parquet_output')

def jaccard_similarity(set1, set2):
    """Compute Jaccard similarity between two sets"""
    if len(set1) == 0 and len(set2) == 0:
        return 1.0  # Both empty = perfect similarity
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    if union == 0:
        return 0.0
    
    return intersection / union


def compute_stability_for_country(daily_data):
    """
    Compute mean Jaccard similarity across consecutive days
    daily_data: dict of {date: {'asns': set(), 'ips': set(), 'usernames': set()}}
    Returns: (asn_mean, ip_mean, username_mean)
    """
    
    # Sort dates
    dates = sorted(daily_data.keys())
    
    if len(dates) < 2:
        return (None, None, None)  # Need at least 2 days
    
    # Compute Jaccard for consecutive days
    asn_similarities = []
    ip_similarities = []
    username_similarities = []
    
    for i in range(len(dates) - 1):
        date1 = dates[i]
        date2 = dates[i + 1]
        
        # ASN Jaccard
        asn_sim = jaccard_similarity(
            daily_data[date1]['asns'],
            daily_data[date2]['asns']
        )
        asn_similarities.append(asn_sim)
        
        # IP Jaccard
        ip_sim = jaccard_similarity(
            daily_data[date1]['ips'],
            daily_data[date2]['ips']
        )
        ip_similarities.append(ip_sim)
        
        # Username Jaccard
        username_sim = jaccard_similarity(
            daily_data[date1]['usernames'],
            daily_data[date2]['usernames']
        )
        username_similarities.append(username_sim)
    
    # Compute means
    asn_mean = np.mean(asn_similarities) if asn_similarities else None
    ip_mean = np.mean(ip_similarities) if ip_similarities else None
    username_mean = np.mean(username_similarities) if username_similarities else None
    
    return (asn_mean, ip_mean, username_mean)


def compute_peak_hours(hourly_attacks):
    """
    Find top 3 peak hours with percentages
    hourly_attacks: dict of {hour: attack_count}
    Returns: "14:00 (25.3%), 15:00 (18.7%), 02:00 (12.1%)"
    """
    
    if not hourly_attacks:
        return None
    
    total_attacks = sum(hourly_attacks.values())
    
    # Sort by attack count descending
    sorted_hours = sorted(hourly_attacks.items(), key=lambda x: x[1], reverse=True)
    
    # Get top 3
    top_3 = sorted_hours[:3]
    
    # Format as "HH:00 (XX.X%)"
    formatted = []
    for hour, count in top_3:
        percentage = (count / total_attacks) * 100
        formatted.append(f"{hour:02d}:00 ({percentage:.1f}%)")
    
    return ", ".join(formatted)


def process_partition(conn, partition_path, partition_name, country_data, country_hours):
    """
    Process one partition and accumulate data
    country_data: dict of {country: {date: {'asns': set(), 'ips': set(), 'usernames': set()}}}
    country_hours: dict of {country: {hour: attack_count}}
    """
    
    print(f"📁 Processing: {partition_name}")
    
    parquet_files = list(partition_path.glob("*.parquet"))
    
    if len(parquet_files) == 0:
        print("   ⚠️  No files found, skipping")
        return
    
    print(f"   📊 {len(parquet_files)} files")
    
    for i, parquet_file in enumerate(parquet_files, 1):
        if i % 50 == 0:
            print(f"      [{i}/{len(parquet_files)}]")
        
        try:
            # Read file and extract needed data
            # NOTE: Time column is stored as integer HHMMSS format (e.g., 143059 = 14:30:59)
            result = conn.execute(f"""
                SELECT 
                    DATE_TRUNC('day', datetime)::DATE as date,
                    FLOOR(Time / 10000)::INTEGER as hour,  -- Extract HH from HHMMSS
                    country,
                    asn_name,
                    IP,
                    Username
                FROM read_parquet('{parquet_file}')
                WHERE country IS NOT NULL
                  AND country != 'Unknown'
            """).fetchall()
            
            # Accumulate data
            for date, hour, country, asn_name, ip, username in result:
                # Initialize country if new
                if country not in country_data:
                    country_data[country] = defaultdict(lambda: {
                        'asns': set(),
                        'ips': set(),
                        'usernames': set()
                    })
                    country_hours[country] = defaultdict(int)
                
                # Add to daily sets
                if asn_name and asn_name != 'Unknown':
                    country_data[country][date]['asns'].add(asn_name)
                if ip:
                    country_data[country][date]['ips'].add(ip)
                if username:
                    country_data[country][date]['usernames'].add(username)
                
                # Add to hourly counts
                if hour is not None:
                    country_hours[country][hour] += 1
        
        except Exception as e:
            print(f"   ❌ Error in {parquet_file.name}: {e}")
    
    print(f"   ✅ Complete")


def main():
    """Create stability metrics table"""
    
    print("="*70)
    print("Create country_stability_metrics Table")
    print("Computes Jaccard similarity + Peak hours")
    print("="*70)
    
    # Find partitions
    partitions = []
    for year_dir in sorted(PARQUET_DIR.glob("year=*")):
        for month_dir in sorted(year_dir.glob("month=*")):
            file_count = len(list(month_dir.glob("*.parquet")))
            partitions.append((month_dir, month_dir.relative_to(PARQUET_DIR), file_count))
    
    total_files = sum(fc for _, _, fc in partitions)
    
    print(f"\nFound {len(partitions)} partitions, {total_files} total files")
    
    # Estimate time
    estimated_mins = (total_files * 0.2) / 60
    print(f"⏱️  Estimated time: ~{estimated_mins:.0f} minutes")
    
    response = input("\nProceed? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled")
        return
    
    # Connect to database
    conn = duckdb.connect(DB_PATH)
    
    print(f"\n📊 Step 1: Collecting daily sets and hourly patterns...")
    print("="*70)
    
    # Data structures
    country_data = {}  # {country: {date: {'asns': set(), 'ips': set(), 'usernames': set()}}}
    country_hours = {}  # {country: {hour: attack_count}}
    
    start_time = time.time()
    
    # Process each partition
    for partition_path, partition_name, _ in partitions:
        process_partition(conn, partition_path, str(partition_name), country_data, country_hours)
    
    collection_time = time.time() - start_time
    
    print(f"\n✅ Data collection complete ({collection_time/60:.1f} minutes)")
    print(f"   Countries: {len(country_data)}")
    
    # Step 2: Compute stability metrics
    print(f"\n📊 Step 2: Computing Jaccard similarities...")
    print("="*70)
    
    stability_data = []
    
    for i, country in enumerate(sorted(country_data.keys()), 1):
        if i % 20 == 0 or i == len(country_data):
            print(f"   [{i}/{len(country_data)}] Processing {country}...")
        
        # Compute stability
        asn_stab, ip_stab, username_stab = compute_stability_for_country(country_data[country])
        
        # Compute peak hours
        peak_hours_str = compute_peak_hours(country_hours[country])
        
        stability_data.append({
            'country': country,
            'asn_stability': asn_stab,
            'ip_stability': ip_stab,
            'username_stability': username_stab,
            'peak_hours': peak_hours_str
        })
    
    print(f"\n✅ Stability computed for {len(stability_data)} countries")
    
    # Step 3: Create table and insert
    print(f"\n📊 Step 3: Creating table and inserting data...")
    print("="*70)
    
    conn.execute("DROP TABLE IF EXISTS country_stability_metrics")
    conn.execute("""
        CREATE TABLE country_stability_metrics (
            country VARCHAR PRIMARY KEY,
            asn_stability DOUBLE,
            ip_stability DOUBLE,
            username_stability DOUBLE,
            peak_hours VARCHAR
        )
    """)
    
    # Insert data
    for data in stability_data:
        conn.execute("""
            INSERT INTO country_stability_metrics 
            VALUES (?, ?, ?, ?, ?)
        """, [
            data['country'],
            data['asn_stability'],
            data['ip_stability'],
            data['username_stability'],
            data['peak_hours']
        ])
    
    total_time = time.time() - start_time
    
    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    
    row_count = conn.execute("SELECT COUNT(*) FROM country_stability_metrics").fetchone()[0]
    
    print(f"\n✅ Table created successfully!")
    print(f"   Total countries: {row_count:,}")
    print(f"   Total time: {total_time/60:.1f} minutes")
    
    # Show sample
    print(f"\n📊 Sample (Top 10 by ASN stability):")
    print(f"{'Country':<30} {'ASN Stab':>10} {'IP Stab':>10} {'User Stab':>10} {'Peak Hours':<40}")
    print("-" * 110)
    
    sample = conn.execute("""
        SELECT country, asn_stability, ip_stability, username_stability, peak_hours
        FROM country_stability_metrics
        ORDER BY asn_stability DESC NULLS LAST
        LIMIT 10
    """).fetchall()
    
    for country, asn_stab, ip_stab, user_stab, peak_hours in sample:
        asn_str = f"{asn_stab:.3f}" if asn_stab is not None else "N/A"
        ip_str = f"{ip_stab:.3f}" if ip_stab is not None else "N/A"
        user_str = f"{user_stab:.3f}" if user_stab is not None else "N/A"
        print(f"{country:<30} {asn_str:>10} {ip_str:>10} {user_str:>10} {peak_hours:<40}")
    
    # Show countries with low stability (volatile)
    print(f"\n📊 Most Volatile (Bottom 5 by ASN stability):")
    print(f"{'Country':<30} {'ASN Stab':>10} {'IP Stab':>10} {'User Stab':>10}")
    print("-" * 70)
    
    volatile = conn.execute("""
        SELECT country, asn_stability, ip_stability, username_stability
        FROM country_stability_metrics
        WHERE asn_stability IS NOT NULL
        ORDER BY asn_stability ASC
        LIMIT 5
    """).fetchall()
    
    for country, asn_stab, ip_stab, user_stab in volatile:
        asn_str = f"{asn_stab:.3f}"
        ip_str = f"{ip_stab:.3f}" if ip_stab is not None else "N/A"
        user_str = f"{user_stab:.3f}" if user_stab is not None else "N/A"
        print(f"{country:<30} {asn_str:>10} {ip_str:>10} {user_str:>10}")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Done! Restart API to use new data")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()