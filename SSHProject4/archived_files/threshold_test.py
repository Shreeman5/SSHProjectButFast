#!/usr/bin/env python3
"""
Where do we cut the noise floor? READ-ONLY.

~70% of usernames have ip_stability == 0 -- they are one-off probes with no
behavioural pattern to cluster on. This tests several inclusion thresholds and
reports, for each: how many usernames survive, how sparse the stability features
still are, and whether PC1 drops to a usable level.

Run from the project root:  python3 threshold_test.py
"""

import duckdb
import numpy as np

DB_PATH = './attack_data.db'
TOTAL_DAYS = 69.0

FEATURES = [
    'g1_log_total_attacks', 'g2_log_attacks_per_ip', 'g3_persistence_pct',
    'g4_burst_intensity',   'g5_max_pct_change',     'g6_log_activity_span',
    'g7_ip_stability',      'g8_country_stability',  'g9_ip_top1_pct',
]

QUERY = f"""
WITH ud AS (
    SELECT username, date, SUM(attacks) AS attacks
    FROM daily_username_attacks GROUP BY username, date
),
agg AS (
    SELECT username, SUM(attacks) AS total_attacks, MAX(attacks) AS max_daily,
           AVG(attacks) AS avg_daily, COUNT(DISTINCT date) AS active_days,
           MIN(date) AS first_seen, MAX(date) AS last_seen
    FROM ud GROUP BY username
),
dod AS (
    SELECT username,
        CASE WHEN LAG(attacks) OVER (PARTITION BY username ORDER BY date) > 0
             THEN (attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date))
                  / LAG(attacks) OVER (PARTITION BY username ORDER BY date) * 100
             ELSE 0 END AS pct_change
    FROM ud
),
vol AS (SELECT username, MAX(pct_change) AS max_pct_change FROM dod GROUP BY username)
SELECT
    a.total_attacks, a.max_daily, a.avg_daily, a.active_days,
    ROUND((a.active_days::FLOAT / {TOTAL_DAYS}) * 100, 2),
    COALESCE(GREATEST(v.max_pct_change, 0), 0),
    (a.last_seen - a.first_seen) + 1,
    COALESCE(sm.unique_ips, 1),
    COALESCE(sm.ip_stability, 0.0),
    COALESCE(sm.country_stability, 0.0),
    -- clamp the 13 corrupted rows into range
    LEAST(GREATEST(COALESCE(sm.ip_top1_pct, 0.0), 0.0), 100.0)
FROM agg a
LEFT JOIN vol v ON a.username = v.username
LEFT JOIN username_stability_metrics sm ON a.username = sm.username
"""

THRESHOLDS = [
    ("no filter (baseline)",       lambda r: True),
    ("active_days >= 2",           lambda r: r[3] >= 2),
    ("active_days >= 3",           lambda r: r[3] >= 3),
    ("active_days >= 5",           lambda r: r[3] >= 5),
    ("active_days >= 7",           lambda r: r[3] >= 7),
    ("total_attacks >= 100",       lambda r: r[0] >= 100),
    ("total_attacks >= 1000",      lambda r: r[0] >= 1000),
    ("active_days>=3 & total>=100", lambda r: r[3] >= 3 and r[0] >= 100),
]


def build(rows):
    X = []
    for total, maxd, avgd, days, pers, pctc, span, uips, ipst, cst, top1 in rows:
        total, uips = float(total), max(float(uips), 1.0)
        X.append([
            np.log1p(total),
            np.log1p(total / uips),
            float(pers),
            min(float(maxd) / float(avgd), 10.0) if avgd else 0.0,
            min(float(pctc), 10000.0),
            np.log1p(float(span)),
            float(ipst),
            float(cst),
            float(top1),
        ])
    return np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)


def pc1_of(X):
    sd = X.std(0)
    keep = sd > 0
    Z = (X[:, keep] - X[:, keep].mean(0)) / sd[keep]
    C = np.corrcoef(Z, rowvar=False)
    ev = np.clip(np.sort(np.linalg.eigvalsh(C))[::-1], 0, None)
    frac = ev / ev.sum()
    return frac, int(keep.sum())


def main():
    con = duckdb.connect(DB_PATH, read_only=True)
    print("Aggregating...")
    rows = con.execute(QUERY).fetchall()
    con.close()
    print(f"  {len(rows):,} usernames\n")

    # distribution context
    days = np.array([r[3] for r in rows])
    tot = np.array([float(r[0]) for r in rows])
    print("=" * 78)
    print("DISTRIBUTION")
    print("=" * 78)
    print(f"  active_days   : median={np.median(days):.0f}  p75={np.percentile(days,75):.0f}"
          f"  p90={np.percentile(days,90):.0f}  p99={np.percentile(days,99):.0f}  max={days.max()}")
    print(f"  total_attacks : median={np.median(tot):,.0f}  p75={np.percentile(tot,75):,.0f}"
          f"  p90={np.percentile(tot,90):,.0f}  p99={np.percentile(tot,99):,.0f}  max={tot.max():,.0f}")
    print(f"  exactly 1 active day : {(days==1).sum():,}  ({(days==1).mean()*100:.1f}%)")

    print("\n" + "=" * 78)
    print("THRESHOLD COMPARISON")
    print("=" * 78)
    print(f"  {'filter':30s} {'kept':>9s} {'%':>6s} {'g7=0':>7s} {'g8=0':>7s} {'PC1':>7s} {'PC1+2':>7s}")
    print("  " + "-" * 74)

    results = {}
    for label, pred in THRESHOLDS:
        sub = [r for r in rows if pred(r)]
        if len(sub) < 100:
            print(f"  {label:30s} {len(sub):>9,}  -- too few, skipped")
            continue
        X = build(sub)
        frac, nkept = pc1_of(X)
        z7 = (X[:, 6] == 0).mean() * 100
        z8 = (X[:, 7] == 0).mean() * 100
        flag = '  <--' if frac[0] < 0.40 else ''
        print(f"  {label:30s} {len(sub):>9,} {len(sub)/len(rows)*100:>5.1f}% "
              f"{z7:>6.1f}% {z8:>6.1f}% {frac[0]*100:>6.1f}% {(frac[0]+frac[1])*100:>6.1f}%{flag}")
        results[label] = (len(sub), frac)

    print("\n" + "=" * 78)
    print("VARIANCE BREAKDOWN for the two most promising filters")
    print("=" * 78)
    for label in ("active_days >= 3", "active_days>=3 & total>=100"):
        if label in results:
            n, frac = results[label]
            print(f"  {label}  (n={n:,})")
            print("    " + ", ".join(f"{v*100:.0f}%" for v in frac))
    print("\n  Rule of thumb: PC1 < 40% means no single direction dominates.")
    print("  Trade-off: a tighter filter means more usernames return 404 on search.")


if __name__ == "__main__":
    main()