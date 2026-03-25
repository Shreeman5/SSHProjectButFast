#!/usr/bin/env python3
"""
Create IP Stability Metrics Table - OPTIMIZED VERSION
Adds index first, then processes with better progress reporting
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


def process_single_ip(conn, ip):
    """Process ONE IP and return its metrics"""
    
    # Initialize collectors
    usernames_by_date = defaultdict(set)
    username_counts = defaultdict(int)
    active_days = set()
    
    # Process usernames (from daily_ip_username_attacks)
    usernames = conn.execute("""
        SELECT date, username, attacks
        FROM daily_ip_username_attacks
        WHERE ip = ?
    """, [ip]).fetchall()
    
    for date, username, attacks in usernames:
        if username:
            usernames_by_date[date].add(username)
            username_counts[username] += attacks
            active_days.add(date)
    
    # Compute all metrics
    unique_usernames = len(username_counts)
    username_concentration, username_top1_pct = format_top3(username_counts, sum(username_counts.values()))
    
    active_days_count = len(active_days)
    username_rotation = unique_usernames / active_days_count if active_days_count > 0 else None
    
    username_stability = compute_stability(usernames_by_date)
    
    return {
        'ip': ip,
        'unique_usernames': unique_usernames,
        'username_concentration': username_concentration,
        'username_top1_pct': username_top1_pct,
        'username_rotation': username_rotation,
        'username_stability': username_stability
    }


def main():
    start_time = time.time()
    
    print(f"\n{'='*80}")
    print("IP STABILITY METRICS - OPTIMIZED VERSION")
    print(f"{'='*80}")
    
    conn = duckdb.connect(DB_PATH)
    
    # Check if index exists
    print("\n📊 Checking for index on daily_ip_username_attacks...")
    sys.stdout.flush()
    
    # Create index if it doesn't exist (this will speed up queries dramatically)
    print("   Creating index on ip column (one-time, ~2-3 minutes)...")
    sys.stdout.flush()
    
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_username_ip ON daily_ip_username_attacks(ip)")
        print("   ✅ Index created/verified")
        sys.stdout.flush()
    except Exception as e:
        print(f"   ⚠️  Index creation skipped: {e}")
        sys.stdout.flush()
    
    # Get IP list
    print("\n📊 Getting IP list...")
    sys.stdout.flush()
    
    ip_list = conn.execute("""
        SELECT DISTINCT ip
        FROM daily_ip_attacks
        ORDER BY ip
    """).fetchall()
    
    ip_addresses = [row[0] for row in ip_list]
    total_ips = len(ip_addresses)
    
    print(f"   Found {total_ips:,} unique IPs")
    print(f"   Processing with indexed lookups")
    print(f"   ⏱️  Estimated time: ~10-15 minutes (with index)")
    sys.stdout.flush()
    
    response = input(f"\nProceed? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Create table
    print(f"\n📊 Creating table...")
    sys.stdout.flush()
    
    conn.execute("DROP TABLE IF EXISTS ip_stability_metrics")
    conn.execute("""
        CREATE TABLE ip_stability_metrics (
            ip VARCHAR PRIMARY KEY,
            unique_usernames INTEGER,
            username_concentration VARCHAR,
            username_top1_pct DOUBLE,
            username_rotation DOUBLE,
            username_stability DOUBLE
        )
    """)
    
    # Process IPs
    print(f"\n📊 Processing IPs...")
    print(f"   Progress updates every 100 IPs")
    sys.stdout.flush()
    
    for i, ip in enumerate(ip_addresses, 1):
        # Process this single IP
        metrics = process_single_ip(conn, ip)
        
        if metrics:
            # Insert immediately
            conn.execute("""
                INSERT INTO ip_stability_metrics 
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                metrics['ip'],
                metrics['unique_usernames'],
                metrics['username_concentration'],
                metrics['username_top1_pct'],
                metrics['username_rotation'],
                metrics['username_stability']
            ])
        
        # Progress update every 100 IPs (more frequent!)
        if i % 100 == 0 or i == total_ips:
            elapsed = time.time() - start_time
            progress = i / total_ips
            eta = (elapsed / progress - elapsed) / 60 if progress > 0 else 0
            print(f"   [{i:6,}/{total_ips:6,}] {progress*100:5.1f}% | Elapsed: {elapsed/60:5.1f}min | ETA: {eta:5.1f}min", flush=True)
    
    total_time = time.time() - start_time
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    row_count = conn.execute("SELECT COUNT(*) FROM ip_stability_metrics").fetchone()[0]
    print(f"\n✅ Table created: {row_count:,} IPs")
    print(f"   Total time: {total_time/60:.1f} minutes")
    
    # Sample - high username diversity
    print(f"\n📊 Sample (High Username Diversity):")
    print(f"{'IP Address':<20} {'Usernames':>12} {'Rotation':>13} {'Stability':>10}")
    print("-" * 60)
    
    sample = conn.execute("""
        SELECT ip, unique_usernames, username_rotation, username_stability
        FROM ip_stability_metrics
        WHERE unique_usernames > 1
        ORDER BY unique_usernames DESC
        LIMIT 5
    """).fetchall()
    
    for ip, usernames, rotation, stability in sample:
        rot_str = f"{rotation:.1f}" if rotation else "N/A"
        stab_str = f"{stability:.3f}" if stability else "N/A"
        print(f"{ip:<20} {usernames:>12,} {rot_str:>13} {stab_str:>10}")
    
    conn.close()
    
    print(f"\n{'='*80}")
    print("✅ Done! Restart API server")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()