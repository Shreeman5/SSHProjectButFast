#!/usr/bin/env python3
"""
Create ASN Stability Metrics Table - ULTRA MEMORY EFFICIENT
Processes ONE ASN at a time to prevent freezing
"""

import duckdb
import time
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


def format_peak_hours(time_counts, total_attacks):
    """Format top 3 peak hours"""
    if not time_counts:
        return None, None
    
    hour_counts = defaultdict(int)
    for time_int, count in time_counts.items():
        hour = time_int // 10000
        hour_counts[hour] += count
    
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    parts = []
    top_pct = None
    
    for i, (hour, count) in enumerate(sorted_hours):
        pct = (count / total_attacks) * 100
        if i == 0:
            top_pct = pct
        
        period = "am" if hour < 12 else "pm"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        
        parts.append(f"{display_hour}{period} ({pct:.1f}%)")
    
    return ", ".join(parts), top_pct


def format_peak_minutes(time_counts, total_attacks):
    """Format top 3 peak minutes"""
    if not time_counts:
        return None, None
    
    minute_counts = defaultdict(int)
    for time_int, count in time_counts.items():
        hour_min = time_int // 100
        minute_counts[hour_min] += count
    
    sorted_mins = sorted(minute_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    parts = []
    top_pct = None
    
    for i, (hour_min, count) in enumerate(sorted_mins):
        pct = (count / total_attacks) * 100
        if i == 0:
            top_pct = pct
        
        hour = hour_min // 100
        minute = hour_min % 100
        
        period = "am" if hour < 12 else "pm"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        
        parts.append(f"{display_hour}:{minute:02d}{period} ({pct:.1f}%)")
    
    return ", ".join(parts), top_pct


def format_peak_seconds(time_counts, total_attacks):
    """Format top 3 peak seconds"""
    if not time_counts:
        return None, None
    
    sorted_times = sorted(time_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    parts = []
    top_pct = None
    
    for i, (time_int, count) in enumerate(sorted_times):
        pct = (count / total_attacks) * 100
        if i == 0:
            top_pct = pct
        
        hour = time_int // 10000
        minute = (time_int % 10000) // 100
        second = time_int % 100
        
        period = "am" if hour < 12 else "pm"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        
        parts.append(f"{display_hour}:{minute:02d}:{second:02d}{period} ({pct:.1f}%)")
    
    return ", ".join(parts), top_pct


def process_single_asn(conn, asn_name):
    """Process ONE ASN and return its metrics - MINIMAL MEMORY"""
    
    # Initialize collectors
    countries_by_date = defaultdict(set)
    ips_by_date = defaultdict(set)
    usernames_by_date = defaultdict(set)
    country_counts = defaultdict(int)
    ip_counts = defaultdict(int)
    username_counts = defaultdict(int)
    active_days = set()
    
    # Process countries (from daily_asn_attacks)
    countries = conn.execute("""
        SELECT date, country, attacks
        FROM daily_asn_attacks
        WHERE asn_name = ?
    """, [asn_name]).fetchall()
    
    for date, country, attacks in countries:
        if country:
            countries_by_date[date].add(country)
            country_counts[country] += attacks
    
    # Process IPs (from daily_ip_attacks) 
    ips = conn.execute("""
        SELECT date, ip, attacks
        FROM daily_ip_attacks
        WHERE asn_name = ?
    """, [asn_name]).fetchall()
    
    for date, ip, attacks in ips:
        if ip:
            ips_by_date[date].add(ip)
            ip_counts[ip] += attacks
            active_days.add(date)
    
    # Process usernames and times (from daily_ip_username_attacks)
    # Get IPs for this ASN first
    asn_ips = conn.execute("""
        SELECT DISTINCT ip FROM daily_ip_attacks WHERE asn_name = ?
    """, [asn_name]).fetchall()
    
    asn_ip_list = [str(ip[0]) for ip in asn_ips]
    
    if asn_ip_list:
        # Process in chunks of 1000 IPs to avoid query too large
        chunk_size = 1000
        for i in range(0, len(asn_ip_list), chunk_size):
            chunk = asn_ip_list[i:i+chunk_size]
            # Escape single quotes in IP strings
            escaped_chunk = [ip.replace("'", "''") for ip in chunk]
            ip_list_str = "', '".join(escaped_chunk)
            
            usernames = conn.execute(f"""
                SELECT date, username, attacks
                FROM daily_ip_username_attacks
                WHERE ip IN ('{ip_list_str}')
            """).fetchall()
            
            for date, username, attacks in usernames:
                if username:
                    usernames_by_date[date].add(username)
                    username_counts[username] += attacks
    
    # Compute all metrics
    unique_countries = len(country_counts)
    primary_country = max(country_counts.items(), key=lambda x: x[1])[0] if country_counts else None
    country_concentration, country_top1_pct = format_top3(country_counts, sum(country_counts.values()))
    
    unique_ips = len(ip_counts)
    ip_concentration, ip_top1_pct = format_top3(ip_counts, sum(ip_counts.values()))
    
    unique_usernames = len(username_counts)
    username_concentration, username_top1_pct = format_top3(username_counts, sum(username_counts.values()))
    
    active_days_count = len(active_days)
    country_rotation = unique_countries / active_days_count if active_days_count > 0 else None
    ip_rotation = unique_ips / active_days_count if active_days_count > 0 else None
    username_rotation = unique_usernames / active_days_count if active_days_count > 0 else None
    
    country_stability = compute_stability(countries_by_date)
    ip_stability = compute_stability(ips_by_date)
    username_stability = compute_stability(usernames_by_date)
    
    # Peak times - not available in daily tables, set to None
    peak_hours = None
    peak_hour_1_pct = None
    peak_minutes = None
    peak_minute_1_pct = None
    peak_seconds = None
    peak_second_1_pct = None
    
    return {
        'asn_name': asn_name,
        'unique_countries': unique_countries,
        'primary_country': primary_country,
        'unique_ips': unique_ips,
        'unique_usernames': unique_usernames,
        'country_concentration': country_concentration,
        'country_top1_pct': country_top1_pct,
        'ip_concentration': ip_concentration,
        'ip_top1_pct': ip_top1_pct,
        'username_concentration': username_concentration,
        'username_top1_pct': username_top1_pct,
        'country_rotation': country_rotation,
        'ip_rotation': ip_rotation,
        'username_rotation': username_rotation,
        'country_stability': country_stability,
        'ip_stability': ip_stability,
        'username_stability': username_stability,
        'peak_hours': peak_hours,
        'peak_hour_1_pct': peak_hour_1_pct,
        'peak_minutes': peak_minutes,
        'peak_minute_1_pct': peak_minute_1_pct,
        'peak_seconds': peak_seconds,
        'peak_second_1_pct': peak_second_1_pct
    }


def main():
    start_time = time.time()
    
    print(f"\n{'='*80}")
    print("ASN STABILITY METRICS - ULTRA MEMORY EFFICIENT (ONE ASN AT A TIME)")
    print(f"{'='*80}")
    
    conn = duckdb.connect(DB_PATH)
    
    # Get ASN list
    print("\n📊 Getting ASN list...")
    asn_list = conn.execute("""
        SELECT DISTINCT asn_name
        FROM daily_asn_attacks
        ORDER BY asn_name
    """).fetchall()
    
    asn_names = [row[0] for row in asn_list]
    total_asns = len(asn_names)
    
    print(f"   Found {total_asns:,} unique ASNs")
    print(f"   Processing ONE ASN at a time (minimal memory)")
    print(f"   ⏱️  Estimated time: ~25-30 minutes")
    
    response = input(f"\nProceed? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Create table
    print(f"\n📊 Creating table...")
    conn.execute("DROP TABLE IF EXISTS asn_stability_metrics")
    conn.execute("""
        CREATE TABLE asn_stability_metrics (
            asn_name VARCHAR PRIMARY KEY,
            unique_countries INTEGER,
            primary_country VARCHAR,
            unique_ips INTEGER,
            unique_usernames INTEGER,
            country_concentration VARCHAR,
            country_top1_pct DOUBLE,
            ip_concentration VARCHAR,
            ip_top1_pct DOUBLE,
            username_concentration VARCHAR,
            username_top1_pct DOUBLE,
            country_rotation DOUBLE,
            ip_rotation DOUBLE,
            username_rotation DOUBLE,
            country_stability DOUBLE,
            ip_stability DOUBLE,
            username_stability DOUBLE,
            peak_hours VARCHAR,
            peak_hour_1_pct DOUBLE,
            peak_minutes VARCHAR,
            peak_minute_1_pct DOUBLE,
            peak_seconds VARCHAR,
            peak_second_1_pct DOUBLE
        )
    """)
    
    # Process ONE ASN at a time
    print(f"\n📊 Processing ASNs (one at a time)...")
    
    for i, asn_name in enumerate(asn_names, 1):
        # Process this single ASN
        metrics = process_single_asn(conn, asn_name)
        
        if metrics:
            # Insert immediately
            conn.execute("""
                INSERT INTO asn_stability_metrics 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                metrics['asn_name'],
                metrics['unique_countries'],
                metrics['primary_country'],
                metrics['unique_ips'],
                metrics['unique_usernames'],
                metrics['country_concentration'],
                metrics['country_top1_pct'],
                metrics['ip_concentration'],
                metrics['ip_top1_pct'],
                metrics['username_concentration'],
                metrics['username_top1_pct'],
                metrics['country_rotation'],
                metrics['ip_rotation'],
                metrics['username_rotation'],
                metrics['country_stability'],
                metrics['ip_stability'],
                metrics['username_stability'],
                metrics['peak_hours'],
                metrics['peak_hour_1_pct'],
                metrics['peak_minutes'],
                metrics['peak_minute_1_pct'],
                metrics['peak_seconds'],
                metrics['peak_second_1_pct']
            ])
        
        # Progress update every 50 ASNs
        if i % 50 == 0 or i == total_asns:
            elapsed = time.time() - start_time
            progress = i / total_asns
            eta = (elapsed / progress - elapsed) / 60 if progress > 0 else 0
            print(f"   [{i}/{total_asns}] {progress*100:.1f}% | Elapsed: {elapsed/60:.1f}min | ETA: {eta:.1f}min")
    
    total_time = time.time() - start_time
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    row_count = conn.execute("SELECT COUNT(*) FROM asn_stability_metrics").fetchone()[0]
    print(f"\n✅ Table created: {row_count:,} ASNs")
    print(f"   Total time: {total_time/60:.1f} minutes")
    
    # Sample
    print(f"\n📊 Sample (Multi-Country ASNs):")
    print(f"{'ASN':<50} {'Countries':>10} {'Primary':<20}")
    print("-" * 85)
    
    sample = conn.execute("""
        SELECT asn_name, unique_countries, primary_country
        FROM asn_stability_metrics
        WHERE unique_countries > 1
        ORDER BY unique_countries DESC
        LIMIT 5
    """).fetchall()
    
    for asn_name, countries, primary in sample:
        asn_short = asn_name[:48] if len(asn_name) > 48 else asn_name
        primary_short = (primary[:18] if primary else "N/A")
        print(f"{asn_short:<50} {countries:>10} {primary_short:<20}")
    
    conn.close()
    
    print(f"\n{'='*80}")
    print("✅ Done! Restart API server")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()