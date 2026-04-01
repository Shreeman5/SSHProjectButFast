#!/usr/bin/env python3
"""
IP Clustering Script - PATTERN DISCOVERY
Pre-computes behavioral clusters for all IPs using k-means
Enables fast "find similar IPs" queries
"""

import duckdb
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import time
import sys

DB_PATH = './attack_data.db'


def extract_features(conn):
    """Extract clustering features for all IPs - ALL 17 FEATURES"""
    
    print("\n📊 Extracting features for clustering...")
    sys.stdout.flush()
    
    query = """
        WITH day_over_day AS (
            SELECT 
                ip,
                date,
                attacks,
                attacks - LAG(attacks) OVER (PARTITION BY ip ORDER BY date) as absolute_change,
                CASE 
                    WHEN LAG(attacks) OVER (PARTITION BY ip ORDER BY date) = 0 
                    THEN (attacks - 1.0) / 1.0 * 100
                    ELSE (attacks - LAG(attacks) OVER (PARTITION BY ip ORDER BY date)) 
                         / LAG(attacks) OVER (PARTITION BY ip ORDER BY date) * 100
                END as pct_change,
                country,
                asn_name
            FROM daily_ip_attacks
        ),
        ip_metrics AS (
            SELECT 
                i.ip,
                i.total_attacks,
                i.avg_daily,
                i.persistence_pct,
                i.max_daily,
                i.country,
                i.asn_name,
                i.first_seen,
                i.last_seen,
                dod.max_absolute_change,
                dod.max_pct_change,
                i.recent_attacks,
                
                -- From stability metrics
                sm.unique_usernames,
                sm.username_stability,
                sm.username_rotation,
                sm.username_top1_pct,
                
                -- Computed
                CASE WHEN i.avg_daily > 0 
                    THEN LEAST(i.max_daily::FLOAT / i.avg_daily, 10.0)
                    ELSE 0 
                END as burst_intensity
                
            FROM (
                SELECT 
                    ip,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    MAX(attacks) as max_daily,
                    COUNT(DISTINCT date) as active_days,
                    MIN(date) as first_seen,
                    MAX(date) as last_seen,
                    MODE() WITHIN GROUP (ORDER BY country) as country,
                    MODE() WITHIN GROUP (ORDER BY asn_name) as asn_name,
                    ROUND((COUNT(DISTINCT date)::FLOAT / 69.0) * 100, 1) as persistence_pct,
                    (SELECT SUM(attacks) 
                     FROM daily_ip_attacks sub 
                     WHERE sub.ip = main.ip 
                     AND sub.date >= (SELECT MAX(date) FROM daily_ip_attacks) - 6) as recent_attacks
                FROM daily_ip_attacks main
                GROUP BY ip
            ) i
            LEFT JOIN (
                SELECT 
                    ip,
                    MAX(absolute_change) as max_absolute_change,
                    MAX(pct_change) as max_pct_change
                FROM day_over_day
                WHERE absolute_change IS NOT NULL
                GROUP BY ip
            ) dod ON i.ip = dod.ip
            LEFT JOIN ip_stability_metrics sm ON i.ip = sm.ip
        )
        SELECT 
            ip,
            total_attacks,
            avg_daily,
            persistence_pct,
            max_daily,
            COALESCE(max_absolute_change, 0) as max_absolute_change,
            COALESCE(max_pct_change, 0) as max_pct_change,
            COALESCE(recent_attacks, 0) as recent_attacks,
            first_seen,
            last_seen,
            burst_intensity,
            COALESCE(username_stability, 0.5) as username_stability,
            COALESCE(username_rotation, 1.0) as username_rotation,
            COALESCE(unique_usernames, 1) as unique_usernames,
            COALESCE(username_top1_pct, 50.0) as username_top1_pct,
            country,
            asn_name
        FROM ip_metrics
        ORDER BY ip
    """
    
    result = conn.execute(query).fetchall()
    
    print(f"   Found {len(result):,} IPs")
    
    # Also get sparkline data for trend slope
    print("   Fetching sparkline data for trend analysis...")
    sparkline_query = """
        SELECT 
            ip,
            STRING_AGG(CAST(total_attacks AS VARCHAR), ',' ORDER BY week_num) as sparkline_values
        FROM (
            SELECT 
                ip,
                FLOOR((date - (SELECT MIN(date) FROM daily_ip_attacks)) / 7) as week_num,
                SUM(attacks) as total_attacks
            FROM daily_ip_attacks
            GROUP BY ip, week_num
        ) intervals
        GROUP BY ip
    """
    sparklines = {row[0]: row[1] for row in conn.execute(sparkline_query).fetchall()}
    
    print(f"   Retrieved sparklines for {len(sparklines):,} IPs")
    
    return result, sparklines


def calculate_trend_slope(sparkline_str):
    """Calculate linear trend slope from sparkline values"""
    if not sparkline_str:
        return 0.0
    
    try:
        values = [float(x) for x in sparkline_str.split(',')]
        if len(values) < 2:
            return 0.0
        
        # Simple linear regression slope
        x = np.arange(len(values))
        y = np.array(values)
        
        # Slope = covariance(x,y) / variance(x)
        slope = np.cov(x, y)[0, 1] / np.var(x) if np.var(x) > 0 else 0.0
        
        return slope
    except:
        return 0.0


def is_cloud_asn(asn_name):
    """Check if ASN is a major cloud provider"""
    if not asn_name:
        return 0
    
    cloud_providers = [
        'digitalocean', 'amazon', 'aws', 'google', 'microsoft', 'azure',
        'ovh', 'hetzner', 'linode', 'vultr', 'cloudflare'
    ]
    
    asn_lower = asn_name.lower()
    return 1 if any(provider in asn_lower for provider in cloud_providers) else 0


def is_major_country(country):
    """Check if country is in top 3 attack sources"""
    major_countries = ['united states', 'china', 'singapore']
    return 1 if country and country.lower() in major_countries else 0


def prepare_feature_matrix(data, sparklines):
    """Convert raw data to normalized feature matrix - ALL 17 FEATURES"""
    
    print("\n📐 Preparing feature matrix...")
    sys.stdout.flush()
    
    ips = [row[0] for row in data]
    countries = [row[15] for row in data]
    asns = [row[16] for row in data]
    
    # Extract all 17 features
    features = []
    for row in data:
        ip = row[0]
        
        # Row indices:
        # 0: ip, 1: total_attacks, 2: avg_daily, 3: persistence_pct, 4: max_daily,
        # 5: max_absolute_change, 6: max_pct_change, 7: recent_attacks,
        # 8: first_seen, 9: last_seen, 10: burst_intensity,
        # 11: username_stability, 12: username_rotation, 13: unique_usernames,
        # 14: username_top1_pct, 15: country, 16: asn_name
        
        # Derived features
        activity_span = (row[9] - row[8]).days if row[9] and row[8] else 1
        recency_ratio = row[7] / row[1] if row[1] > 0 else 0  # recent / total
        trend_slope = calculate_trend_slope(sparklines.get(ip, ''))
        cloud_asn = is_cloud_asn(row[16])
        major_country = is_major_country(row[15])
        
        features.append([
            # Volume (3)
            np.log1p(row[1]),              # 1. log(total_attacks)
            np.log1p(row[2]),              # 2. log(avg_daily)
            np.log1p(row[4]),              # 3. log(max_daily)
            
            # Temporal (4)
            row[3],                        # 4. persistence_pct (0-100)
            min(row[10], 10.0),            # 5. burst_intensity (capped)
            np.log1p(max(0, row[5])),      # 6. log(max_absolute_change) - force positive
            min(abs(row[6]), 1000.0),      # 7. max_pct_change (capped, abs value)
            
            # Targeting (4)
            row[11],                       # 8. username_stability (0-1)
            min(row[12], 20.0),            # 9. username_rotation (capped)
            np.log1p(row[13]),             # 10. log(unique_usernames)
            row[14],                       # 11. username_top1_pct (0-100)
            
            # Derived (6)
            trend_slope,                   # 12. trend_slope
            cloud_asn,                     # 13. is_cloud_asn (0/1)
            major_country,                 # 14. is_major_country (0/1)
            np.log1p(activity_span),       # 15. log(activity_span)
            recency_ratio,                 # 16. recency_ratio (0-1)
            np.log1p(row[7])               # 17. log(recent_attacks)
        ])
    
    X = np.array(features)
    
    # Replace any remaining NaN or inf with 0
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    
    print(f"   Feature matrix shape: {X.shape}")
    print(f"   Features (17): volume(3), temporal(4), targeting(4), derived(6)")
    
    return ips, X, countries, asns


def find_optimal_k(X, min_k=8, max_k=25):
    """Find optimal number of clusters using elbow method and silhouette"""
    
    print(f"\n🔍 Finding optimal k (testing k={min_k} to {max_k})...")
    print("   This may take a few minutes...")
    sys.stdout.flush()
    
    inertias = []
    silhouettes = []
    k_range = range(min_k, max_k + 1)
    
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)
        
        inertias.append(kmeans.inertia_)
        
        # Silhouette score (sample for speed)
        sample_size = min(10000, len(X))
        indices = np.random.choice(len(X), sample_size, replace=False)
        sil_score = silhouette_score(X[indices], labels[indices])
        silhouettes.append(sil_score)
        
        print(f"   k={k:2d}: inertia={kmeans.inertia_:,.0f}, silhouette={sil_score:.3f}")
        sys.stdout.flush()
    
    # Find elbow using second derivative
    inertias_norm = np.array(inertias) / inertias[0]
    second_deriv = np.diff(inertias_norm, 2)
    elbow_k = min_k + np.argmax(second_deriv) + 1
    
    # Find best silhouette
    best_sil_k = min_k + np.argmax(silhouettes)
    
    print(f"\n   Elbow method suggests: k={elbow_k}")
    print(f"   Best silhouette score: k={best_sil_k} (score={max(silhouettes):.3f})")
    
    # Use silhouette score winner
    optimal_k = best_sil_k
    print(f"   ✅ Selected k={optimal_k}")
    
    return optimal_k


def cluster_ips(X, k):
    """Perform k-means clustering"""
    
    print(f"\n🎯 Clustering with k={k}...")
    sys.stdout.flush()
    
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=20, max_iter=500)
    labels = kmeans.fit_predict(X)
    
    # Calculate distance from each point to its centroid
    distances = np.min(kmeans.transform(X), axis=1)
    
    print(f"   ✅ Clustering complete")
    print(f"   Final inertia: {kmeans.inertia_:,.0f}")
    
    return labels, distances, kmeans


def auto_name_cluster(profile):
    """Automatically name cluster based on characteristics"""
    
    # High volume
    if profile['avg_total_attacks'] > 1_000_000:
        volume = "High-Volume"
    elif profile['avg_total_attacks'] > 100_000:
        volume = "Medium-Volume"
    else:
        volume = "Low-Volume"
    
    # Persistence
    if profile['avg_persistence_pct'] > 80:
        persistence = "Persistent"
    elif profile['avg_persistence_pct'] > 40:
        persistence = "Intermittent"
    else:
        persistence = "Sporadic"
    
    # Targeting
    if profile['avg_username_stability'] > 0.7:
        targeting = "Focused"
    elif profile['avg_username_stability'] > 0.3:
        targeting = "Mixed"
    else:
        targeting = "Exploratory"
    
    # Burst
    if profile['avg_burst_intensity'] > 5:
        burst = "Bursty"
    elif profile['avg_burst_intensity'] > 2:
        burst = "Variable"
    else:
        burst = "Steady"
    
    name = f"{volume} {persistence} {targeting}"
    description = f"{burst} attack pattern"
    
    return name, description


def compute_cluster_profiles(conn, ips, labels, X_raw, countries, asns, k):
    """Compute characteristics for each cluster"""
    
    print(f"\n📊 Computing cluster profiles...")
    sys.stdout.flush()
    
    profiles = []
    
    for cluster_id in range(k):
        mask = labels == cluster_id
        cluster_ips = [ips[i] for i in range(len(ips)) if mask[i]]
        cluster_countries = [countries[i] for i in range(len(countries)) if mask[i]]
        cluster_asns = [asns[i] for i in range(len(asns)) if mask[i]]
        
        # Get detailed metrics for cluster members
        placeholders = ','.join(['?' for _ in cluster_ips])
        query = f"""
            SELECT 
                AVG(i.total_attacks) as avg_attacks,
                AVG(i.persistence_pct) as avg_persistence,
                AVG(i.burst_intensity) as avg_burst,
                AVG(COALESCE(sm.username_stability, 0.5)) as avg_username_stability,
                AVG(COALESCE(sm.username_rotation, 1.0)) as avg_username_rotation,
                AVG(COALESCE(sm.unique_usernames, 1)) as avg_usernames
            FROM (
                SELECT 
                    ip,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    MAX(attacks) as max_daily,
                    ROUND((COUNT(DISTINCT date)::FLOAT / 69.0) * 100, 1) as persistence_pct,
                    CASE WHEN AVG(attacks) > 0 
                        THEN LEAST(MAX(attacks)::FLOAT / AVG(attacks), 10.0)
                        ELSE 0 
                    END as burst_intensity
                FROM daily_ip_attacks
                WHERE ip IN ({placeholders})
                GROUP BY ip
            ) i
            LEFT JOIN ip_stability_metrics sm ON i.ip = sm.ip
        """
        
        result = conn.execute(query, cluster_ips).fetchone()
        
        # Find dominant country and ASN
        from collections import Counter
        country_counts = Counter(cluster_countries)
        asn_counts = Counter(cluster_asns)
        
        dominant_country = country_counts.most_common(1)[0] if country_counts else (None, 0)
        dominant_asn = asn_counts.most_common(1)[0] if asn_counts else (None, 0)
        
        profile = {
            'cluster_id': cluster_id,
            'cluster_size': len(cluster_ips),
            'avg_total_attacks': int(result[0]),
            'avg_persistence_pct': round(result[1], 1),
            'avg_burst_intensity': round(result[2], 2),
            'avg_username_stability': round(result[3], 3),
            'avg_username_rotation': round(result[4], 1),
            'avg_unique_usernames': int(result[5]),
            'dominant_country': dominant_country[0],
            'dominant_country_pct': round(dominant_country[1] / len(cluster_countries) * 100, 1) if cluster_countries else 0,
            'dominant_asn': dominant_asn[0],
            'intra_cluster_variance': float(np.var(X_raw[mask]))
        }
        
        name, description = auto_name_cluster(profile)
        profile['profile_name'] = name
        profile['profile_description'] = description
        
        profiles.append(profile)
        
        print(f"   Cluster {cluster_id}: {name} ({len(cluster_ips):,} IPs)")
    
    return profiles


def save_to_database(conn, ips, labels, distances, X_normalized, profiles):
    """Save cluster assignments and profiles to database"""
    
    print(f"\n💾 Saving to database...")
    sys.stdout.flush()
    
    # Create tables
    conn.execute("DROP TABLE IF EXISTS ip_clusters")
    conn.execute("DROP TABLE IF EXISTS cluster_profiles")
    
    conn.execute("""
        CREATE TABLE ip_clusters (
            ip VARCHAR PRIMARY KEY,
            cluster_id INTEGER NOT NULL,
            distance_from_centroid DOUBLE,
            -- All 17 normalized features for similarity calculation
            f1_log_total_attacks DOUBLE,
            f2_log_avg_daily DOUBLE,
            f3_log_max_daily DOUBLE,
            f4_persistence_pct DOUBLE,
            f5_burst_intensity DOUBLE,
            f6_log_max_abs_change DOUBLE,
            f7_max_pct_change DOUBLE,
            f8_username_stability DOUBLE,
            f9_username_rotation DOUBLE,
            f10_log_unique_usernames DOUBLE,
            f11_username_top1_pct DOUBLE,
            f12_trend_slope DOUBLE,
            f13_is_cloud_asn DOUBLE,
            f14_is_major_country DOUBLE,
            f15_log_activity_span DOUBLE,
            f16_recency_ratio DOUBLE,
            f17_log_recent_attacks DOUBLE
        )
    """)
    
    conn.execute("""
        CREATE TABLE cluster_profiles (
            cluster_id INTEGER PRIMARY KEY,
            cluster_size INTEGER,
            avg_total_attacks BIGINT,
            avg_persistence_pct DOUBLE,
            avg_burst_intensity DOUBLE,
            avg_username_stability DOUBLE,
            avg_username_rotation DOUBLE,
            avg_unique_usernames INTEGER,
            dominant_country VARCHAR,
            dominant_country_pct DOUBLE,
            dominant_asn VARCHAR,
            profile_name VARCHAR,
            profile_description VARCHAR,
            intra_cluster_variance DOUBLE
        )
    """)
    
    # Insert IP cluster assignments
    print("   Inserting cluster assignments...")
    for i, ip in enumerate(ips):
        conn.execute("""
            INSERT INTO ip_clusters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ip,
            int(labels[i]),
            float(distances[i]),
            # All 17 normalized features
            float(X_normalized[i, 0]),
            float(X_normalized[i, 1]),
            float(X_normalized[i, 2]),
            float(X_normalized[i, 3]),
            float(X_normalized[i, 4]),
            float(X_normalized[i, 5]),
            float(X_normalized[i, 6]),
            float(X_normalized[i, 7]),
            float(X_normalized[i, 8]),
            float(X_normalized[i, 9]),
            float(X_normalized[i, 10]),
            float(X_normalized[i, 11]),
            float(X_normalized[i, 12]),
            float(X_normalized[i, 13]),
            float(X_normalized[i, 14]),
            float(X_normalized[i, 15]),
            float(X_normalized[i, 16])
        ])
    
    # Insert cluster profiles
    print("   Inserting cluster profiles...")
    for profile in profiles:
        conn.execute("""
            INSERT INTO cluster_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            profile['cluster_id'],
            profile['cluster_size'],
            profile['avg_total_attacks'],
            profile['avg_persistence_pct'],
            profile['avg_burst_intensity'],
            profile['avg_username_stability'],
            profile['avg_username_rotation'],
            profile['avg_unique_usernames'],
            profile['dominant_country'],
            profile['dominant_country_pct'],
            profile['dominant_asn'],
            profile['profile_name'],
            profile['profile_description'],
            profile['intra_cluster_variance']
        ])
    
    # Create indexes
    conn.execute("CREATE INDEX idx_ip_clusters_cluster_id ON ip_clusters(cluster_id)")
    
    print("   ✅ Database updated")


def main():
    start_time = time.time()
    
    print(f"\n{'='*80}")
    print("IP CLUSTERING - PATTERN DISCOVERY")
    print(f"{'='*80}")
    
    conn = duckdb.connect(DB_PATH)
    
    # Step 1: Extract features
    data, sparklines = extract_features(conn)
    
    # Step 2: Prepare feature matrix
    ips, X_raw, countries, asns = prepare_feature_matrix(data, sparklines)
    
    # Step 3: Normalize features
    print("\n🔧 Normalizing features...")
    scaler = StandardScaler()
    X_normalized = scaler.fit_transform(X_raw)
    print(f"   ✅ Features normalized (mean=0, std=1)")
    
    # Step 4: Find optimal k
    optimal_k = find_optimal_k(X_normalized, min_k=10, max_k=20)
    
    # Step 5: Cluster
    labels, distances, kmeans = cluster_ips(X_normalized, optimal_k)
    
    # Step 6: Compute profiles
    profiles = compute_cluster_profiles(conn, ips, labels, X_raw, countries, asns, optimal_k)
    
    # Step 7: Save to database
    save_to_database(conn, ips, labels, distances, X_normalized, profiles)
    
    conn.close()
    
    total_time = time.time() - start_time
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\n✅ Clustering complete!")
    print(f"   IPs clustered: {len(ips):,}")
    print(f"   Number of clusters: {optimal_k}")
    print(f"   Total time: {total_time/60:.1f} minutes")
    
    print(f"\n📊 Cluster Distribution:")
    for profile in sorted(profiles, key=lambda x: x['cluster_size'], reverse=True):
        print(f"   Cluster {profile['cluster_id']:2d}: {profile['cluster_size']:6,} IPs - {profile['profile_name']}")
    
    print(f"\n{'='*80}")
    print("✅ Done! Restart API server to use clustering")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()