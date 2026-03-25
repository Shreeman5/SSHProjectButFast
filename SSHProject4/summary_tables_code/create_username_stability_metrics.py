#!/usr/bin/env python3
"""
Create Username Stability Metrics Table - OPTIMIZED VERSION
Adds index first, then processes with better progress reporting
Computes country/ASN/IP-based metrics for each username
"""

import duckdb
import time
import sys
from collections import defaultdict

DB_PATH = './attack_data.db'


def jaccard_similarity(set1, set2):
    """Calculate Jaccard similarity between two sets"""
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def compute_stability(daily_sets):
    """Compute mean Jaccard similarity between consecutive days"""
    if len(daily_sets) < 2:
        return None
    
    similarities = []
    sorted_dates = sorted(daily_sets.keys())
    
    for i in range(len(sorted_dates) - 1):
        sim = jaccard_similarity(daily_sets[sorted_dates[i]], daily_sets[sorted_dates[i + 1]])
        similarities.append(sim)
    
    return sum(similarities) / len(similarities) if similarities else None


def format_top3(counter_dict, total):
    """Return formatted string of top 3 items with percentages"""
    if not counter_dict or total == 0:
        return None, None
    
    sorted_items = sorted(counter_dict.items(), key=lambda x: x[1], reverse=True)[:3]
    parts = []
    top_pct = None
    
    for i, (item, count) in enumerate(sorted_items):
        pct = (count / total) * 100
        if i == 0:
            top_pct = pct
        parts.append(f"{item} ({pct:.1f}%)")
    
    return ", ".join(parts), top_pct


def format_top3_asn(counter_dict, total):
    """Return formatted string of top 3 ASNs with percentages using ||| delimiter"""
    if not counter_dict or total == 0:
        return None, None
    
    sorted_items = sorted(counter_dict.items(), key=lambda x: x[1], reverse=True)[:3]
    parts = []
    top_pct = None
    
    for i, (item, count) in enumerate(sorted_items):
        pct = (count / total) * 100
        if i == 0:
            top_pct = pct
        parts.append(f"{item} ({pct:.1f}%)")
    
    return "|||".join(parts), top_pct  # Use ||| delimiter for ASN names (they can contain commas)


def process_single_username(conn, username):
    """Process ONE username and return its metrics - MINIMAL MEMORY"""
    
    # Initialize collectors
    countries_by_date = defaultdict(set)
    asns_by_date = defaultdict(set)
    ips_by_date = defaultdict(set)
    
    country_counts = defaultdict(int)
    asn_counts = defaultdict(int)
    ip_counts = defaultdict(int)
    
    active_days = set()
    
    # Process data (from daily_ip_username_attacks)
    data = conn.execute("""
        SELECT date, country, asn_name, ip, attacks
        FROM daily_ip_username_attacks
        WHERE username = ?
    """, [username]).fetchall()
    
    for date, country, asn_name, ip, attacks in data:
        if country:
            countries_by_date[date].add(country)
            country_counts[country] += attacks
        if asn_name:
            asns_by_date[date].add(asn_name)
            asn_counts[asn_name] += attacks
        if ip:
            ips_by_date[date].add(ip)
            ip_counts[ip] += attacks
        active_days.add(date)
    
    # Compute all metrics
    unique_countries = len(country_counts)
    unique_asns = len(asn_counts)
    unique_ips = len(ip_counts)
    
    total_attacks = sum(country_counts.values())  # Same as sum of asn_counts or ip_counts
    
    country_concentration, country_top1_pct = format_top3(country_counts, total_attacks)
    asn_concentration, asn_top1_pct = format_top3_asn(asn_counts, total_attacks)
    ip_concentration, ip_top1_pct = format_top3(ip_counts, total_attacks)
    
    country_stability = compute_stability(countries_by_date)
    asn_stability = compute_stability(asns_by_date)
    ip_stability = compute_stability(ips_by_date)
    
    active_days_count = len(active_days)
    country_rotation = unique_countries / active_days_count if active_days_count > 0 else None
    asn_rotation = unique_asns / active_days_count if active_days_count > 0 else None
    ip_rotation = unique_ips / active_days_count if active_days_count > 0 else None
    
    return {
        'username': username,
        'unique_countries': unique_countries,
        'unique_asns': unique_asns,
        'unique_ips': unique_ips,
        'country_concentration': country_concentration,
        'country_top1_pct': country_top1_pct,
        'asn_concentration': asn_concentration,
        'asn_top1_pct': asn_top1_pct,
        'ip_concentration': ip_concentration,
        'ip_top1_pct': ip_top1_pct,
        'country_stability': country_stability,
        'asn_stability': asn_stability,
        'ip_stability': ip_stability,
        'country_rotation': country_rotation,
        'asn_rotation': asn_rotation,
        'ip_rotation': ip_rotation
    }


def main():
    start_time = time.time()
    
    print(f"\n{'='*80}")
    print("USERNAME STABILITY METRICS - OPTIMIZED VERSION")
    print(f"{'='*80}")
    
    conn = duckdb.connect(DB_PATH, read_only=False)
    
    # Check if index exists
    print("\n📊 Checking for index on daily_ip_username_attacks...")
    sys.stdout.flush()
    
    # Check if index already exists
    existing_indexes = conn.execute("""
        SELECT index_name 
        FROM duckdb_indexes() 
        WHERE table_name = 'daily_ip_username_attacks' 
        AND index_name = 'idx_ip_username_username'
    """).fetchall()
    
    if existing_indexes:
        print("   ✅ Index already exists - skipping creation")
        sys.stdout.flush()
    else:
        print("   ⚠️  Index does NOT exist - creating now...")
        print("   ⏱️  This will take 2-3 minutes with NO progress updates")
        print("   💡 The process is NOT frozen - please wait patiently...")
        sys.stdout.flush()
        
        index_start = time.time()
        try:
            conn.execute("CREATE INDEX idx_ip_username_username ON daily_ip_username_attacks(username)")
            index_time = time.time() - index_start
            print(f"   ✅ Index created in {index_time/60:.1f} minutes")
            sys.stdout.flush()
        except Exception as e:
            print(f"   ⚠️  Index creation failed: {e}")
            print("   ⚠️  Continuing anyway (will be slower)...")
            sys.stdout.flush()
    
    # Get username list
    print("\n📊 Getting username list...")
    sys.stdout.flush()
    
    username_list = conn.execute("""
        SELECT DISTINCT username
        FROM daily_ip_username_attacks
        WHERE username IS NOT NULL
        ORDER BY username
    """).fetchall()
    
    usernames = [row[0] for row in username_list]
    total_usernames = len(usernames)
    
    print(f"   Found {total_usernames:,} unique usernames")
    print(f"   Processing with indexed lookups")
    print(f"   ⏱️  Estimated time: ~15-20 minutes (with index)")
    sys.stdout.flush()
    
    response = input(f"\nProceed? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Create table
    print(f"\n📊 Creating table...")
    sys.stdout.flush()
    
    conn.execute("DROP TABLE IF EXISTS username_stability_metrics")
    conn.execute("""
        CREATE TABLE username_stability_metrics (
            username VARCHAR PRIMARY KEY,
            unique_countries INTEGER,
            unique_asns INTEGER,
            unique_ips INTEGER,
            country_concentration VARCHAR,
            country_top1_pct DOUBLE,
            asn_concentration VARCHAR,
            asn_top1_pct DOUBLE,
            ip_concentration VARCHAR,
            ip_top1_pct DOUBLE,
            country_stability DOUBLE,
            asn_stability DOUBLE,
            ip_stability DOUBLE,
            country_rotation DOUBLE,
            asn_rotation DOUBLE,
            ip_rotation DOUBLE
        )
    """)
    
    # Process usernames
    print(f"\n📊 Processing usernames...")
    print(f"   Progress updates every 100 usernames")
    sys.stdout.flush()
    
    for i, username in enumerate(usernames, 1):
        # Process this single username
        metrics = process_single_username(conn, username)
        
        if metrics:
            # Insert immediately
            conn.execute("""
                INSERT INTO username_stability_metrics 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                metrics['username'],
                metrics['unique_countries'],
                metrics['unique_asns'],
                metrics['unique_ips'],
                metrics['country_concentration'],
                metrics['country_top1_pct'],
                metrics['asn_concentration'],
                metrics['asn_top1_pct'],
                metrics['ip_concentration'],
                metrics['ip_top1_pct'],
                metrics['country_stability'],
                metrics['asn_stability'],
                metrics['ip_stability'],
                metrics['country_rotation'],
                metrics['asn_rotation'],
                metrics['ip_rotation']
            ])
        
        # Progress update every 100 usernames
        if i % 100 == 0 or i == total_usernames:
            elapsed = time.time() - start_time
            progress = i / total_usernames
            eta = (elapsed / progress - elapsed) / 60 if progress > 0 else 0
            print(f"   [{i:6,}/{total_usernames:6,}] {progress*100:5.1f}% | Elapsed: {elapsed/60:5.1f}min | ETA: {eta:5.1f}min", flush=True)
    
    total_time = time.time() - start_time
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    row_count = conn.execute("SELECT COUNT(*) FROM username_stability_metrics").fetchone()[0]
    print(f"\n✅ Table created: {row_count:,} usernames")
    print(f"   Total time: {total_time/60:.1f} minutes")
    
    # Sample - high diversity
    print(f"\n📊 Sample (High Attack Diversity - Many Sources):")
    print(f"{'Username':<20} {'Countries':>10} {'ASNs':>10} {'IPs':>10}")
    print("-" * 55)
    
    sample = conn.execute("""
        SELECT username, unique_countries, unique_asns, unique_ips
        FROM username_stability_metrics
        ORDER BY unique_ips DESC
        LIMIT 5
    """).fetchall()
    
    for username, countries, asns, ips in sample:
        print(f"{username:<20} {countries:>10,} {asns:>10,} {ips:>10,}")
    
    # Sample - high stability
    print(f"\n📊 Sample (High IP Stability - Consistent Attackers):")
    print(f"{'Username':<20} {'IPs':>10} {'IP Stability':>14} {'Top Country':<30}")
    print("-" * 80)
    
    sample2 = conn.execute("""
        SELECT username, unique_ips, ip_stability, country_concentration
        FROM username_stability_metrics
        WHERE ip_stability IS NOT NULL AND ip_stability > 0.7
        ORDER BY ip_stability DESC
        LIMIT 5
    """).fetchall()
    
    for username, ips, stability, conc in sample2:
        conc_short = (conc.split(',')[0] if conc else "N/A")[:28]
        print(f"{username:<20} {ips:>10,} {stability:>14.3f} {conc_short:<30}")
    
    conn.close()
    
    print(f"\n{'='*80}")
    print("✅ Done! Restart API server")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()