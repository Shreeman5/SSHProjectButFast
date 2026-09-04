#!/usr/bin/env python3
"""
Username feature diagnostic -- READ-ONLY, no tables written, no clustering.

Computes the 17 proposed clustering features for all usernames and reports:
  1. Spread of each feature (are any effectively constant?)
  2. Correlation matrix (are we accidentally weighting "size" 5x?)

Run from the project root:  python3 feature_diagnostic.py
Takes ~1-2 minutes. Nothing is modified.
"""

import duckdb
import numpy as np

DB_PATH = './attack_data.db'
TOTAL_DAYS = 69.0

FEATURES = [
    'f1_log_total_attacks',   'f2_log_avg_daily',       'f3_log_max_daily',
    'f4_persistence_pct',     'f5_burst_intensity',     'f6_log_max_abs_change',
    'f7_max_pct_change',      'f8_ip_stability',        'f9_log_ip_rotation',
    'f10_log_unique_ips',     'f11_ip_top1_pct',        'f12_asn_stability',
    'f13_log_unique_asns',    'f14_country_stability',  'f15_log_unique_countries',
    'f16_log_activity_span',  'f17_log_recent_attacks',
]

QUERY = f"""
WITH ud AS (
    -- day-level rollup: collapses the country/ASN fragments
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
),
dod AS (
    SELECT
        username,
        attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date) AS abs_change,
        CASE WHEN LAG(attacks) OVER (PARTITION BY username ORDER BY date) > 0
             THEN (attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date))
                  / LAG(attacks) OVER (PARTITION BY username ORDER BY date) * 100
             ELSE 0 END AS pct_change
    FROM ud
),
vol AS (
    SELECT username,
           MAX(abs_change) AS max_abs_change,
           MAX(pct_change) AS max_pct_change
    FROM dod WHERE abs_change IS NOT NULL
    GROUP BY username
),
recent AS (
    SELECT username, SUM(attacks) AS recent_attacks
    FROM ud
    WHERE date > (SELECT MAX(date) FROM ud) - INTERVAL 7 DAY
    GROUP BY username
)
SELECT
    a.username,
    a.total_attacks,
    a.avg_daily,
    a.max_daily,
    ROUND((a.active_days::FLOAT / {TOTAL_DAYS}) * 100, 2)              AS persistence_pct,
    CASE WHEN a.avg_daily > 0 THEN a.max_daily::FLOAT / a.avg_daily
         ELSE 0 END                                                    AS burst_intensity,
    COALESCE(GREATEST(v.max_abs_change, 0), 0)                         AS max_abs_change,
    COALESCE(GREATEST(v.max_pct_change, 0), 0)                         AS max_pct_change,
    COALESCE(sm.ip_stability, 0.0)                                     AS ip_stability,
    COALESCE(sm.ip_rotation, 0.0)                                      AS ip_rotation,
    COALESCE(sm.unique_ips, 1)                                         AS unique_ips,
    COALESCE(sm.ip_top1_pct, 0.0)                                      AS ip_top1_pct,
    COALESCE(sm.asn_stability, 0.0)                                    AS asn_stability,
    COALESCE(sm.unique_asns, 1)                                        AS unique_asns,
    COALESCE(sm.country_stability, 0.0)                                AS country_stability,
    COALESCE(sm.unique_countries, 1)                                   AS unique_countries,
    (a.last_seen - a.first_seen) + 1                                   AS activity_span,
    COALESCE(r.recent_attacks, 0)                                      AS recent_attacks
FROM agg a
LEFT JOIN vol    v  ON a.username = v.username
LEFT JOIN recent r  ON a.username = r.username
LEFT JOIN username_stability_metrics sm ON a.username = sm.username
"""


def main():
    con = duckdb.connect(DB_PATH, read_only=True)

    print("Running aggregation over daily_username_attacks (this is the slow part)...")
    rows = con.execute(QUERY).fetchall()
    print(f"  {len(rows):,} usernames\n")

    missing = con.execute("""
        SELECT COUNT(*) FROM (SELECT DISTINCT username FROM daily_username_attacks) d
        LEFT JOIN username_stability_metrics s ON d.username = s.username
        WHERE s.username IS NULL
    """).fetchone()[0]
    con.close()

    X = np.array([[
        np.log1p(float(r[1])),   # f1  log total_attacks
        np.log1p(float(r[2])),   # f2  log avg_daily
        np.log1p(float(r[3])),   # f3  log max_daily
        float(r[4]),             # f4  persistence_pct
        min(float(r[5]), 10.0),  # f5  burst_intensity (capped)
        np.log1p(float(r[6])),   # f6  log max_abs_change
        min(float(r[7]), 10000), # f7  max_pct_change (capped)
        float(r[8]),             # f8  ip_stability
        np.log1p(float(r[9])),   # f9  log ip_rotation
        np.log1p(float(r[10])),  # f10 log unique_ips
        float(r[11]),            # f11 ip_top1_pct
        float(r[12]),            # f12 asn_stability
        np.log1p(float(r[13])),  # f13 log unique_asns
        float(r[14]),            # f14 country_stability
        np.log1p(float(r[15])),  # f15 log unique_countries
        np.log1p(float(r[16])),  # f16 log activity_span
        np.log1p(float(r[17])),  # f17 log recent_attacks
    ] for r in rows], dtype=float)

    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    if missing:
        print(f"!! {missing:,} usernames have NO row in username_stability_metrics")
        print("   (their f8-f15 defaulted to 0 and they will cluster together spuriously)\n")

    # ---- 1. spread -------------------------------------------------------
    print("=" * 78)
    print("1. FEATURE SPREAD  (low CV = near-constant = wasted dimension)")
    print("=" * 78)
    print(f"{'feature':26s} {'mean':>11s} {'std':>11s} {'min':>9s} {'max':>11s} {'CV':>7s}")
    for i, name in enumerate(FEATURES):
        col = X[:, i]
        mu, sd = col.mean(), col.std()
        cv = sd / abs(mu) if mu else 0.0
        flag = '  <-- LOW' if cv < 0.10 else ''
        print(f"{name:26s} {mu:>11.3f} {sd:>11.3f} {col.min():>9.2f} {col.max():>11.2f} {cv:>7.3f}{flag}")

    # ---- 2. correlation --------------------------------------------------
    Z = (X - X.mean(0)) / np.where(X.std(0) == 0, 1, X.std(0))
    C = np.corrcoef(Z, rowvar=False)

    print("\n" + "=" * 78)
    print("2. STRONGLY CORRELATED PAIRS  (|r| > 0.80)")
    print("=" * 78)
    pairs = [(abs(C[i, j]), C[i, j], FEATURES[i], FEATURES[j])
             for i in range(len(FEATURES)) for j in range(i + 1, len(FEATURES))
             if abs(C[i, j]) > 0.80]
    if pairs:
        for _, r, a, b in sorted(pairs, reverse=True):
            print(f"  r = {r:+.3f}   {a:26s} <-> {b}")
    else:
        print("  none -- features are reasonably independent")

    # ---- 3. effective dimensionality ------------------------------------
    ev = np.sort(np.linalg.eigvalsh(C))[::-1]
    ev = np.clip(ev, 0, None)
    cum = np.cumsum(ev) / ev.sum()
    n90 = int(np.searchsorted(cum, 0.90) + 1)

    print("\n" + "=" * 78)
    print("3. EFFECTIVE DIMENSIONALITY")
    print("=" * 78)
    print(f"  {n90} of 17 components explain 90% of variance")
    print(f"  first component alone: {cum[0]*100:.1f}%")
    print("  variance by component: " + ", ".join(f"{v*100:.0f}%" for v in (ev / ev.sum())[:8]))
    if cum[0] > 0.45:
        print("\n  !! first component dominates -- clusters will mostly sort by size")


if __name__ == "__main__":
    main()