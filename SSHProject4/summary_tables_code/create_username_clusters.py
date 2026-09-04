#!/usr/bin/env python3
"""
USERNAME Clustering Script - PATTERN DISCOVERY
Pre-computes behavioural clusters for usernames using k-means.
Enables fast "find similar usernames" queries.

Counterpart to create_ip_clusters.py, but INVERTED:
    IP clustering asks:       which usernames does this IP try?
    Username clustering asks: who attacks this username?

Writes:        username_clusters, username_cluster_profiles
Leaves alone:  ip_clusters, cluster_profiles

--------------------------------------------------------------------------------
DESIGN NOTES -- these differ from create_ip_clusters.py on purpose
--------------------------------------------------------------------------------
1. AGGREGATION. daily_username_attacks is keyed (date, username, country,
   asn_name), NOT (date, username). Row-level AVG/MAX/LAG on it produce fragment
   statistics, not daily ones. Everything rolls up through `ud` first.
   daily_ip_attacks does not have this problem, which is why the IP script can
   aggregate it directly.

2. FILTER: active_days >= 2. 46,935 usernames (48.1%) appear on exactly one day,
   median 32 attacks total. Consecutive-day Jaccard is undefined for them, so
   ip_stability / country_stability are placeholders rather than measurements.
   Left in, they form a dense heap at the origin that inflates PC1 from 39.5%
   to 51.7% -- a fake principal axis made of noise.

3. NINE FEATURES, not seventeen. The 17-feature analogue had eight measuring
   size (r = 0.996 between unique_ips and unique_asns), weighting size 8x
   against everything else. Survivors are one per correlated group, plus
   attacks_per_ip -- a ratio decorrelated from size by construction.

4. K SEARCH 8..30. The IP run searched 10..20 and selected k=20, the top of its
   own range, so silhouette may still have been climbing. A boundary selection
   is not a maximum; this script warns if it happens again.

5. PROFILES FROM THE MATRIX. The IP script builds `WHERE ip IN (?, ?, ...)`
   with one placeholder per cluster member -- a 20,000-parameter query for a
   large cluster. The same numbers come out of the in-memory arrays.
--------------------------------------------------------------------------------
"""

import duckdb
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from collections import Counter
import time
import sys

DB_PATH = './attack_data.db'
TOTAL_DAYS = 69.0
MIN_ACTIVE_DAYS = 2

MIN_K, MAX_K = 8, 30

FEATURE_NAMES = [
    'f1_log_total_attacks',
    'f2_log_attacks_per_ip',
    'f3_persistence_pct',
    'f4_burst_intensity',
    'f5_max_pct_change',
    'f6_log_activity_span',
    'f7_ip_stability',
    'f8_country_stability',
    'f9_ip_top1_pct',
]


# =============================================================================
# Extraction
# =============================================================================
def extract_features(conn):
    """Day-level metrics for every username with >= MIN_ACTIVE_DAYS active days."""

    print("\n[1/7] Extracting features...")
    sys.stdout.flush()

    query = f"""
        WITH ud AS (
            -- Collapse country/ASN fragments into one row per username-day.
            SELECT username, date, SUM(attacks) AS attacks
            FROM daily_username_attacks
            GROUP BY username, date
        ),
        agg AS (
            SELECT
                username,
                SUM(attacks)          AS total_attacks,
                AVG(attacks)          AS avg_daily,
                MAX(attacks)          AS max_daily,
                COUNT(DISTINCT date)  AS active_days,
                MIN(date)             AS first_seen,
                MAX(date)             AS last_seen
            FROM ud
            GROUP BY username
            HAVING COUNT(DISTINCT date) >= {MIN_ACTIVE_DAYS}
        ),
        dod AS (
            -- LAG is only meaningful now that date is unique within a username.
            SELECT
                username,
                CASE WHEN LAG(attacks) OVER (PARTITION BY username ORDER BY date) > 0
                     THEN (attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date))
                          / LAG(attacks) OVER (PARTITION BY username ORDER BY date) * 100
                     ELSE 0 END AS pct_change
            FROM ud
        ),
        vol AS (
            SELECT username, MAX(pct_change) AS max_pct_change
            FROM dod GROUP BY username
        )
        SELECT
            a.username,                                                        -- 0
            a.total_attacks,                                                   -- 1
            a.avg_daily,                                                       -- 2
            a.max_daily,                                                       -- 3
            a.active_days,                                                     -- 4
            ROUND((a.active_days::FLOAT / {TOTAL_DAYS}) * 100, 2),             -- 5  persistence_pct
            COALESCE(GREATEST(v.max_pct_change, 0), 0),                        -- 6  max_pct_change
            (a.last_seen - a.first_seen) + 1,                                  -- 7  activity_span
            COALESCE(sm.unique_ips, 1),                                        -- 8
            COALESCE(sm.unique_countries, 1),                                  -- 9
            COALESCE(sm.ip_stability, 0.0),                                    -- 10
            COALESCE(sm.country_stability, 0.0),                               -- 11
            -- 13 rows carry corrupted top1 percentages (negative / >100); clamp
            LEAST(GREATEST(COALESCE(sm.ip_top1_pct, 0.0), 0.0), 100.0),        -- 12
            sm.country_concentration                                           -- 13
        FROM agg a
        LEFT JOIN vol v ON a.username = v.username
        LEFT JOIN username_stability_metrics sm ON a.username = sm.username
        ORDER BY a.username
    """

    rows = conn.execute(query).fetchall()

    total_all = conn.execute(
        "SELECT COUNT(DISTINCT username) FROM daily_username_attacks"
    ).fetchone()[0]

    print(f"      {len(rows):,} usernames with >= {MIN_ACTIVE_DAYS} active days")
    print(f"      ({total_all - len(rows):,} of {total_all:,} excluded as single-day)")
    return rows


def top_of_concentration(s):
    """'China (21.4%), United States (17.8%)' -> 'China'."""
    if not s:
        return None
    return str(s).split(',')[0].split('(')[0].strip() or None


def prepare_feature_matrix(rows):
    """Build the 9-column raw feature matrix."""

    print("\n[2/7] Building feature matrix...")
    sys.stdout.flush()

    usernames = [r[0] for r in rows]
    top_countries = [top_of_concentration(r[13]) for r in rows]

    X = []
    for r in rows:
        total = float(r[1])
        avg_daily = float(r[2])
        max_daily = float(r[3])
        uips = max(float(r[8]), 1.0)

        X.append([
            np.log1p(total),                                              # f1
            np.log1p(total / uips),                                       # f2
            float(r[5]),                                                  # f3
            min(max_daily / avg_daily, 10.0) if avg_daily > 0 else 0.0,   # f4
            min(float(r[6]), 10000.0),                                    # f5
            np.log1p(float(r[7])),                                        # f6
            float(r[10]),                                                 # f7
            float(r[11]),                                                 # f8
            float(r[12]),                                                 # f9
        ])

    X = np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)

    print(f"      shape {X.shape}")
    for i, nm in enumerate(FEATURE_NAMES):
        print(f"        {nm:24s} mean={X[:, i].mean():>10.3f}  std={X[:, i].std():>10.3f}")

    return usernames, X, top_countries


# =============================================================================
# Clustering
# =============================================================================
def find_optimal_k(X, min_k=MIN_K, max_k=MAX_K):
    """Pick k by silhouette; report the elbow; warn on a boundary selection."""

    print(f"\n[3/7] Searching k = {min_k}..{max_k}")
    print("      (silhouette on a 10k sample for speed)")
    sys.stdout.flush()

    inertias, silhouettes = [], []
    ks = list(range(min_k, max_k + 1))
    rng = np.random.default_rng(42)

    for k in ks:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        inertias.append(km.inertia_)

        idx = rng.choice(len(X), min(10000, len(X)), replace=False)
        sil = silhouette_score(X[idx], labels[idx])
        silhouettes.append(sil)

        print(f"      k={k:2d}  inertia={km.inertia_:>12,.0f}  silhouette={sil:.4f}")
        sys.stdout.flush()

    best_i = int(np.argmax(silhouettes))
    best_k = ks[best_i]

    norm = np.array(inertias) / inertias[0]
    elbow_k = ks[int(np.argmax(np.diff(norm, 2))) + 1] if len(ks) > 2 else best_k

    print(f"\n      elbow suggests   k={elbow_k}")
    print(f"      best silhouette  k={best_k} ({silhouettes[best_i]:.4f})")

    if best_i in (0, len(ks) - 1):
        print(f"      !! k={best_k} sits at the EDGE of the search range.")
        print(f"      !! Silhouette may still be improving -- widen MIN_K/MAX_K and rerun.")

    print(f"      selected k={best_k}")
    return best_k


def cluster(X, k):
    print(f"\n[4/7] Clustering, k={k}...")
    sys.stdout.flush()

    km = KMeans(n_clusters=k, random_state=42, n_init=20, max_iter=500)
    labels = km.fit_predict(X)
    distances = np.min(km.transform(X), axis=1)

    print(f"      inertia {km.inertia_:,.0f}")
    print(f"      distance-to-centroid: mean={distances.mean():.3f} "
          f"p50={np.percentile(distances, 50):.3f} "
          f"p95={np.percentile(distances, 95):.3f} max={distances.max():.3f}")
    return labels, distances


# =============================================================================
# Naming
#
# Fixed bands, deliberately NOT percentiles of the current run.
#
# Percentile thresholds move every time the data changes, so "High-Volume"
# would mean something different after each rerun and cluster names would not be
# comparable across runs. Fixed cutoffs keep the taxonomy stable.
#
# The absolute values differ from create_ip_clusters.py because the
# distributions differ: p99 of username total_attacks is ~14k, so the IP
# script's 1,000,000 "High-Volume" line would label every username cluster
# Low-Volume.
# =============================================================================
def volume_band(a):
    """Log-spaced. Real cluster averages run 16 -> 105,322; coarse bands merge
    genuinely different clusters."""
    if a >= 50_000: return "Massive-Volume"
    if a >= 5_000:  return "High-Volume"
    if a >= 1_000:  return "Elevated-Volume"
    if a >= 500:    return "Moderate-Volume"
    if a >= 50:     return "Low-Volume"
    return "Minimal-Volume"


def sourcing_band(n):
    """Size of the attacking IP population."""
    if n >= 2000: return "Botnet-Scale"
    if n >= 200:  return "Broadly-Sourced"
    if n >= 20:   return "Multi-Sourced"
    return "Narrowly-Sourced"


def temporal_band(pers, span):
    """
    Persistence and span answer different questions -- "on how many days?" and
    "across how wide a window?" -- and they can diverge sharply. Clusters at
    ~104 vs ~102 attacks from ~46 vs ~47 IPs are otherwise indistinguishable but
    span 32.0d vs 2.2d. Naming on persistence alone merged 62% of all usernames
    under one label.
    """
    if pers > 60:  return "Persistent"      # active most days in the window
    if pers > 25:  return "Intermittent"    # active a substantial fraction
    if span >= 21: return "Long-Tail"       # sparse, but spread over weeks
    if span >= 7:  return "Recurring"       # sparse over a short window
    return "Short-Lived"                    # appeared and vanished


def churn_band(s):
    """ip_stability: do the same IPs come back day after day?"""
    if s > 0.50: return "stable attacker set"
    if s > 0.15: return "rotating attacker set"
    return "volatile attacker set"


def burst_band(b):
    if b > 5: return "bursty"
    if b > 2: return "variable"
    return "steady"


def build_name(p):
    """Returns (profile_name, profile_description)."""
    name = (f"{volume_band(p['avg_total_attacks'])} "
            f"{temporal_band(p['avg_persistence_pct'], p['avg_activity_span'])} "
            f"{sourcing_band(p['avg_unique_ips'])}")

    desc = (f"{churn_band(p['avg_ip_stability'])}, "
            f"{burst_band(p['avg_burst_intensity'])} · "
            f"~{p['avg_total_attacks']:,} attacks from ~{p['avg_unique_ips']:,} IPs "
            f"({p['avg_attacks_per_ip']:,.0f}/IP) · "
            f"active {p['avg_persistence_pct']:.0f}% of days "
            f"over ~{p['avg_activity_span']:.0f}d")
    return name, desc


# =============================================================================
# Profiles
# =============================================================================
def compute_profiles(raw, labels, X_raw, top_countries, k):
    """All from in-memory arrays -- no per-cluster SQL."""

    print("\n[5/7] Computing cluster profiles...")
    sys.stdout.flush()

    stats = np.array([[
        float(r[1]),                                              # total_attacks
        float(r[5]),                                              # persistence_pct
        min(float(r[3]) / float(r[2]), 10.0) if r[2] else 0.0,    # burst_intensity
        float(r[8]),                                              # unique_ips
        float(r[10]),                                             # ip_stability
        float(r[11]),                                             # country_stability
        float(r[1]) / max(float(r[8]), 1.0),                      # attacks_per_ip
        float(r[7]),                                              # activity_span
    ] for r in raw], dtype=float)

    profiles = []
    print()
    for cid in range(k):
        mask = labels == cid
        size = int(mask.sum())
        if size == 0:
            continue

        s = stats[mask]
        countries = [top_countries[i] for i in np.flatnonzero(mask) if top_countries[i]]
        counts = Counter(countries)
        dom, dom_n = counts.most_common(1)[0] if counts else (None, 0)

        p = {
            'cluster_id': cid,
            'cluster_size': size,
            'avg_total_attacks': int(s[:, 0].mean()),
            'avg_persistence_pct': round(float(s[:, 1].mean()), 2),
            'avg_burst_intensity': round(float(s[:, 2].mean()), 3),
            'avg_unique_ips': int(s[:, 3].mean()),
            'avg_ip_stability': round(float(s[:, 4].mean()), 4),
            'avg_country_stability': round(float(s[:, 5].mean()), 4),
            'avg_attacks_per_ip': round(float(s[:, 6].mean()), 2),
            'avg_activity_span': round(float(s[:, 7].mean()), 1),
            'dominant_country': dom,
            'dominant_country_pct': round(dom_n / len(countries) * 100, 1) if countries else 0.0,
            'intra_cluster_variance': float(np.var(X_raw[mask])),
        }
        p['profile_name'], p['profile_description'] = build_name(p)
        profiles.append(p)

        print(f"      cluster {cid:2d}: {size:6,}  {p['profile_name']}")
        print(f"                    {p['profile_description']}")

    # A duplicate name means two clusters are indistinguishable in the search
    # panel headline. The description still separates them, but it is worth
    # knowing about.
    names = [p['profile_name'] for p in profiles]
    dupes = sorted({n for n in names if names.count(n) > 1})
    print(f"\n      distinct names: {len(set(names))} of {len(profiles)} clusters")
    if dupes:
        print(f"      !! duplicated: {dupes}")
        print("      !! adjust the band cutoffs above if this matters")

    return profiles


# =============================================================================
# Persistence
# =============================================================================
def save(conn, usernames, labels, distances, Xn, profiles):
    print("\n[6/7] Writing tables...")
    sys.stdout.flush()

    conn.execute("DROP TABLE IF EXISTS username_clusters")
    conn.execute("DROP TABLE IF EXISTS username_cluster_profiles")

    cols = ",\n            ".join(f"{n} DOUBLE" for n in FEATURE_NAMES)
    conn.execute(f"""
        CREATE TABLE username_clusters (
            username VARCHAR PRIMARY KEY,
            cluster_id INTEGER NOT NULL,
            distance_from_centroid DOUBLE,
            {cols}
        )
    """)

    conn.execute("""
        CREATE TABLE username_cluster_profiles (
            cluster_id INTEGER PRIMARY KEY,
            cluster_size INTEGER,
            avg_total_attacks BIGINT,
            avg_persistence_pct DOUBLE,
            avg_burst_intensity DOUBLE,
            avg_unique_ips INTEGER,
            avg_ip_stability DOUBLE,
            avg_country_stability DOUBLE,
            avg_attacks_per_ip DOUBLE,
            avg_activity_span DOUBLE,
            dominant_country VARCHAR,
            dominant_country_pct DOUBLE,
            profile_name VARCHAR,
            profile_description VARCHAR,
            intra_cluster_variance DOUBLE
        )
    """)

    ph = ", ".join(["?"] * (3 + len(FEATURE_NAMES)))
    conn.executemany(
        f"INSERT INTO username_clusters VALUES ({ph})",
        [[usernames[i], int(labels[i]), float(distances[i])] + [float(v) for v in Xn[i]]
         for i in range(len(usernames))]
    )

    conn.executemany(
        "INSERT INTO username_cluster_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [[p['cluster_id'], p['cluster_size'], p['avg_total_attacks'],
          p['avg_persistence_pct'], p['avg_burst_intensity'], p['avg_unique_ips'],
          p['avg_ip_stability'], p['avg_country_stability'], p['avg_attacks_per_ip'],
          p['avg_activity_span'], p['dominant_country'], p['dominant_country_pct'],
          p['profile_name'], p['profile_description'], p['intra_cluster_variance']]
         for p in profiles]
    )

    conn.execute("CREATE INDEX idx_username_clusters_cid ON username_clusters(cluster_id)")
    print(f"      username_clusters: {len(usernames):,} rows")
    print(f"      username_cluster_profiles: {len(profiles)} rows")


def calibrate(X, labels):
    """
    Measure real within-cluster distances so the endpoint can map distance to a
    percentage from observed spread rather than from a formula.

    The IP endpoint hardcodes `100 - (d/4.1)*100`, justified as sqrt(17). But for
    two independent standardised points E[||x-y||^2] = 2*17 = 34, so a typical
    distance is ~5.8 -- well past 4.1, where everything clamps to 0. That is the
    84.6% -> 33.8% cliff in the IP results.
    """
    print("\n[7/7] Calibrating the similarity scale...")

    rng = np.random.default_rng(42)
    samples = []
    for cid in np.unique(labels):
        idx = np.flatnonzero(labels == cid)
        if len(idx) < 2:
            continue
        pick = rng.choice(idx, min(len(idx), 300), replace=False)
        P = X[pick]
        for _ in range(min(2000, len(pick) * 4)):
            a, b = rng.integers(0, len(P), 2)
            if a != b:
                samples.append(float(np.linalg.norm(P[a] - P[b])))

    d = np.array(samples)
    p50, p90, p99 = np.percentile(d, [50, 90, 99])
    print(f"      {len(d):,} within-cluster pairs sampled")
    print(f"        p50={p50:.3f}  p90={p90:.3f}  p99={p99:.3f}  max={d.max():.3f}")
    print(f"\n      >>> use MAX_DISTANCE = {p99:.2f} in the endpoint <<<")
    print("      (p99, so ~1% of same-cluster pairs floor at 0% rather than most)")
    return float(p99)


# =============================================================================
def main():
    t0 = time.time()
    print("=" * 78)
    print("USERNAME CLUSTERING - PATTERN DISCOVERY")
    print("=" * 78)

    conn = duckdb.connect(DB_PATH)

    raw = extract_features(conn)
    if len(raw) < MAX_K * 2:
        print(f"\nERROR: only {len(raw)} usernames; too few for k up to {MAX_K}.")
        conn.close()
        sys.exit(1)

    usernames, X_raw, top_countries = prepare_feature_matrix(raw)

    print("\n      normalising (StandardScaler)...")
    X = StandardScaler().fit_transform(X_raw)

    k = find_optimal_k(X)
    labels, distances = cluster(X, k)
    profiles = compute_profiles(raw, labels, X_raw, top_countries, k)
    save(conn, usernames, labels, distances, X, profiles)
    max_distance = calibrate(X, labels)

    conn.close()

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  usernames clustered : {len(usernames):,}")
    print(f"  clusters            : {k}")
    print(f"  features            : {len(FEATURE_NAMES)}")
    print(f"  MAX_DISTANCE        : {max_distance:.2f}  (needed by the endpoint)")
    print(f"  elapsed             : {(time.time() - t0) / 60:.1f} min")
    print("\n  cluster sizes:")
    for p in sorted(profiles, key=lambda x: -x['cluster_size']):
        print(f"    {p['cluster_size']:6,}  {p['profile_name']}")
    print("\n  Next: endpoints/similar_usernames_endpoint.py")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()