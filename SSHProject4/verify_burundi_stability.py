#!/usr/bin/env python3
"""
Verify Stability Metrics for Burundi
Shows daily ASN/IP/Username sets and computes Jaccard similarity step-by-step
"""

import duckdb
from pathlib import Path
from collections import defaultdict
import numpy as np

DB_PATH = './attack_data.db'
PARQUET_DIR = Path('./parquet_output')

def jaccard_similarity(set1, set2):
    """Compute Jaccard similarity between two sets"""
    if len(set1) == 0 and len(set2) == 0:
        return 1.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    if union == 0:
        return 0.0
    
    return intersection / union


def main():
    """Analyze Burundi attack patterns day-by-day"""
    
    print("="*80)
    print("BURUNDI ATTACK PATTERN VERIFICATION")
    print("="*80)
    
    # Connect to database
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    # Get all data for Burundi from parquet files
    print("\n📊 Loading Burundi attack data from parquet files...")
    
    parquet_pattern = str(PARQUET_DIR / "**/*.parquet")
    
    query = f"""
        SELECT 
            DATE_TRUNC('day', datetime)::DATE as date,
            asn_name,
            IP,
            Username,
            FLOOR(Time / 10000)::INTEGER as hour
        FROM read_parquet('{parquet_pattern}', hive_partitioning=1)
        WHERE country = 'Ethiopia'
        ORDER BY date
    """
    
    result = conn.execute(query).fetchall()
    
    if len(result) == 0:
        print("❌ No data found for Burundi!")
        conn.close()
        return
    
    print(f"✅ Found {len(result):,} attack records for Burundi")
    
    # Organize by date
    daily_data = defaultdict(lambda: {
        'asns': set(),
        'ips': set(),
        'usernames': set(),
        'hours': defaultdict(int)
    })
    
    for date, asn_name, ip, username, hour in result:
        if asn_name and asn_name != 'Unknown':
            daily_data[date]['asns'].add(asn_name)
        if ip:
            daily_data[date]['ips'].add(ip)
        if username:
            daily_data[date]['usernames'].add(username)
        if hour is not None:
            daily_data[date]['hours'][hour] += 1
    
    # Sort dates
    dates = sorted(daily_data.keys())
    
    print(f"\n📅 Date range: {dates[0]} to {dates[-1]}")
    print(f"📅 Total days with attacks: {len(dates)}")
    
    # Show daily breakdown
    print("\n" + "="*80)
    print("DAILY BREAKDOWN (First 10 Days)")
    print("="*80)
    print(f"{'Date':<12} {'ASNs':>6} {'IPs':>6} {'Users':>6} {'Total Attacks':>15}")
    print("-"*80)
    
    for i, date in enumerate(dates[:10]):
        data = daily_data[date]
        total_attacks = sum(data['hours'].values())
        print(f"{date} {len(data['asns']):>6} {len(data['ips']):>6} {len(data['usernames']):>6} {total_attacks:>15,}")
    
    if len(dates) > 10:
        print(f"... ({len(dates) - 10} more days)")
    
    # Show unique entities across ALL days
    print("\n" + "="*80)
    print("UNIQUE ENTITIES (Across All Days)")
    print("="*80)
    
    all_asns = set()
    all_ips = set()
    all_usernames = set()
    
    for data in daily_data.values():
        all_asns.update(data['asns'])
        all_ips.update(data['ips'])
        all_usernames.update(data['usernames'])
    
    print(f"Unique ASNs: {len(all_asns)}")
    print(f"Unique IPs: {len(all_ips)}")
    print(f"Unique Usernames: {len(all_usernames)}")
    
    # Show the actual entities
    print(f"\n🏢 ASNs attacking Burundi:")
    for asn in sorted(all_asns):
        print(f"   - {asn}")
    
    print(f"\n🌐 IPs attacking Burundi (first 20):")
    for ip in sorted(all_ips)[:20]:
        print(f"   - {ip}")
    if len(all_ips) > 20:
        print(f"   ... and {len(all_ips) - 20} more")
    
    print(f"\n👤 Usernames tried (first 20):")
    for username in sorted(all_usernames)[:20]:
        print(f"   - {username}")
    if len(all_usernames) > 20:
        print(f"   ... and {len(all_usernames) - 20} more")
    
    # Compute Jaccard similarity for consecutive days
    print("\n" + "="*80)
    print("JACCARD SIMILARITY (Consecutive Days)")
    print("="*80)
    
    if len(dates) < 2:
        print("Need at least 2 days to compute Jaccard similarity")
        conn.close()
        return
    
    asn_similarities = []
    ip_similarities = []
    username_similarities = []
    
    print(f"\n{'Day Pair':<25} {'ASN JS':>10} {'IP JS':>10} {'User JS':>10}")
    print("-"*80)
    
    # Show first 10 day-pairs
    for i in range(min(10, len(dates) - 1)):
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
        
        print(f"{date1} → {date2}  {asn_sim:>10.3f} {ip_sim:>10.3f} {username_sim:>10.3f}")
    
    # Compute remaining pairs (don't print)
    for i in range(10, len(dates) - 1):
        date1 = dates[i]
        date2 = dates[i + 1]
        
        asn_sim = jaccard_similarity(
            daily_data[date1]['asns'],
            daily_data[date2]['asns']
        )
        asn_similarities.append(asn_sim)
        
        ip_sim = jaccard_similarity(
            daily_data[date1]['ips'],
            daily_data[date2]['ips']
        )
        ip_similarities.append(ip_sim)
        
        username_sim = jaccard_similarity(
            daily_data[date1]['usernames'],
            daily_data[date2]['usernames']
        )
        username_similarities.append(username_sim)
    
    if len(dates) > 11:
        print(f"... ({len(dates) - 11} more day-pairs computed)")
    
    # Calculate means
    print("\n" + "="*80)
    print("FINAL STABILITY METRICS (Mean Jaccard Similarity)")
    print("="*80)
    
    asn_mean = np.mean(asn_similarities)
    ip_mean = np.mean(ip_similarities)
    username_mean = np.mean(username_similarities)
    
    print(f"\n🏢 ASN Stability:      {asn_mean:.3f}")
    print(f"🌐 IP Stability:       {ip_mean:.3f}")
    print(f"👤 Username Stability: {username_mean:.3f}")
    
    print(f"\nTotal consecutive day-pairs: {len(asn_similarities)}")
    
    # Compute peak hours
    print("\n" + "="*80)
    print("PEAK ATTACK HOURS")
    print("="*80)
    
    # Aggregate all hourly data
    hourly_totals = defaultdict(int)
    for data in daily_data.values():
        for hour, count in data['hours'].items():
            hourly_totals[hour] += count
    
    total_attacks = sum(hourly_totals.values())
    
    # Sort by attack count
    sorted_hours = sorted(hourly_totals.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n{'Hour':>6} {'Attacks':>12} {'Percentage':>12}")
    print("-"*35)
    
    for hour, count in sorted_hours[:10]:
        pct = (count / total_attacks) * 100
        print(f"{hour:02d}:00 {count:>12,} {pct:>11.1f}%")
    
    # Show top 3 formatted
    print("\n🔥 Top 3 Peak Hours (formatted):")
    top_3 = sorted_hours[:3]
    formatted_peaks = []
    for hour, count in top_3:
        pct = (count / total_attacks) * 100
        formatted_peaks.append(f"{hour:02d}:00 ({pct:.1f}%)")
    
    peak_hours_str = ", ".join(formatted_peaks)
    print(f"   {peak_hours_str}")
    
    # Compare with database values
    print("\n" + "="*80)
    print("DATABASE COMPARISON")
    print("="*80)
    
    db_result = conn.execute("""
        SELECT 
            asn_stability,
            ip_stability,
            username_stability,
            peak_hours
        FROM country_stability_metrics
        WHERE country = 'Ethiopia'
    """).fetchone()
    
    if db_result:
        db_asn, db_ip, db_user, db_peaks = db_result
        
        print("\n📊 Database Values:")
        print(f"   ASN Stability:      {db_asn:.3f}" if db_asn else "   ASN Stability:      NULL")
        print(f"   IP Stability:       {db_ip:.3f}" if db_ip else "   IP Stability:       NULL")
        print(f"   Username Stability: {db_user:.3f}" if db_user else "   Username Stability: NULL")
        print(f"   Peak Hours:         {db_peaks}" if db_peaks else "   Peak Hours:         NULL")
        
        print("\n✅ Verification:")
        if db_asn:
            diff_asn = abs(asn_mean - db_asn)
            status_asn = "✅ MATCH" if diff_asn < 0.001 else f"⚠️  DIFF: {diff_asn:.6f}"
            print(f"   ASN:      {status_asn}")
        
        if db_ip:
            diff_ip = abs(ip_mean - db_ip)
            status_ip = "✅ MATCH" if diff_ip < 0.001 else f"⚠️  DIFF: {diff_ip:.6f}"
            print(f"   IP:       {status_ip}")
        
        if db_user:
            diff_user = abs(username_mean - db_user)
            status_user = "✅ MATCH" if diff_user < 0.001 else f"⚠️  DIFF: {diff_user:.6f}"
            print(f"   Username: {status_user}")
        
        if db_peaks:
            status_peaks = "✅ MATCH" if db_peaks == peak_hours_str else "⚠️  DIFFERENT"
            print(f"   Peaks:    {status_peaks}")
            if db_peaks != peak_hours_str:
                print(f"      Expected: {peak_hours_str}")
                print(f"      Got:      {db_peaks}")
    else:
        print("❌ No data found in database for Burundi!")
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ Verification complete!")
    print("="*80)


if __name__ == "__main__":
    main()
