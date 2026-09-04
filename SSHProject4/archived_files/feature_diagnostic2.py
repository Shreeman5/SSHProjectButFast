#!/usr/bin/env python3
"""
Two questions, one run. READ-ONLY.

  PART A -- why does ip_top1_pct contain values below 0 and above 100?
  PART B -- does the pruned 9-feature set actually fix the PC1 dominance?

Run from the project root:  python3 feature_diagnostic2.py
"""

import duckdb
import numpy as np

DB_PATH = './attack_data.db'
TOTAL_DAYS = 69.0


# =============================================================================
# PART A -- ip_top1_pct sanity
# =============================================================================
def part_a(con):
    print("=" * 78)
    print("PART A -- ip_top1_pct OUT-OF-RANGE INVESTIGATION")
    print("=" * 78)

    r = con.execute("""
        SELECT
            COUNT(*),
            SUM(CASE WHEN ip_top1_pct < 0                    THEN 1 ELSE 0 END),
            SUM(CASE WHEN ip_top1_pct > 100                  THEN 1 ELSE 0 END),
            SUM(CASE WHEN ip_top1_pct BETWEEN 0 AND 100      THEN 1 ELSE 0 END),
            SUM(CASE WHEN ip_top1_pct IS NULL                THEN 1 ELSE 0 END)
        FROM username_stability_metrics
    """).fetchone()
    total, neg, over, ok, nul = r
    print(f"  rows                 : {total:,}")
    print(f"  ip_top1_pct <   0    : {neg:,}   ({neg/total*100:.2f}%)")
    print(f"  ip_top1_pct > 100    : {over:,}   ({over/total*100:.2f}%)")
    print(f"  ip_top1_pct in range : {ok:,}   ({ok/total*100:.2f}%)")
    print(f"  ip_top1_pct NULL     : {nul:,}")

    print("\n  Do the sibling top1 columns have the same problem?")
    for col in ('country_top1_pct', 'asn_top1_pct'):
        rr = con.execute(f"""
            SELECT MIN({col}), MAX({col}),
                   SUM(CASE WHEN {col} < 0 OR {col} > 100 THEN 1 ELSE 0 END)
            FROM username_stability_metrics
        """).fetchone()
        print(f"    {col:20s} min={rr[0]:>10.2f}  max={rr[1]:>10.2f}  out-of-range={rr[2]:,}")

    print("\n  Worst offenders, with the concentration string for comparison:")
    rows = con.execute("""
        SELECT username, ip_top1_pct, unique_ips, ip_concentration
        FROM username_stability_metrics
        WHERE ip_top1_pct < 0 OR ip_top1_pct > 100
        ORDER BY ABS(ip_top1_pct - 50) DESC
        LIMIT 8
    """).fetchall()
    for u, pct, n, conc in rows:
        print(f"    {str(u)[:22]:24s} pct={pct:>9.2f}  unique_ips={n:>7}  conc={str(conc)[:44]}")

    print("\n  Cross-check: recompute top-1 share from daily_ip_username_attacks")
    print("  (stored value vs. what the raw data actually says)")
    names = [r[0] for r in rows[:4]]
    if names:
        ph = ', '.join('?' for _ in names)
        chk = con.execute(f"""
            WITH per_ip AS (
                SELECT username, IP, SUM(attacks) AS a
                FROM daily_ip_username_attacks
                WHERE username IN ({ph})
                GROUP BY username, IP
            ),
            tot AS (SELECT username, SUM(a) AS t FROM per_ip GROUP BY username),
            top AS (SELECT username, MAX(a) AS m FROM per_ip GROUP BY username)
            SELECT t.username, top.m, t.t, ROUND(top.m * 100.0 / t.t, 2)
            FROM tot t JOIN top ON t.username = top.username
        """, names).fetchall()
        stored = {u: p for u, p, _, _ in rows}
        for u, m, t, pct in chk:
            print(f"    {str(u)[:22]:24s} stored={stored.get(u, float('nan')):>9.2f}   actual={pct:>7.2f}"
                  f"   (top IP {m:,} of {t:,})")
    print()


# =============================================================================
# PART B -- pruned feature set
# =============================================================================
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
    a.total_attacks, a.max_daily, a.avg_daily,
    ROUND((a.active_days::FLOAT / {TOTAL_DAYS}) * 100, 2) AS persistence_pct,
    COALESCE(GREATEST(v.max_pct_change, 0), 0) AS max_pct_change,
    (a.last_seen - a.first_seen) + 1 AS activity_span,
    COALESCE(sm.unique_ips, 1) AS unique_ips,
    COALESCE(sm.ip_stability, 0.0) AS ip_stability,
    COALESCE(sm.country_stability, 0.0) AS country_stability,
    COALESCE(sm.asn_stability, 0.0) AS asn_stability
FROM agg a
LEFT JOIN vol v ON a.username = v.username
LEFT JOIN username_stability_metrics sm ON a.username = sm.username
"""

PRUNED = [
    'g1_log_total_attacks', 'g2_log_attacks_per_ip', 'g3_persistence_pct',
    'g4_burst_intensity',   'g5_max_pct_change',     'g6_log_activity_span',
    'g7_ip_stability',      'g8_country_stability',
]


def part_b(con):
    print("=" * 78)
    print("PART B -- PRUNED FEATURE SET (8 features; ip_top1_pct held back)")
    print("=" * 78)

    rows = con.execute(QUERY).fetchall()
    print(f"  {len(rows):,} usernames\n")

    X = []
    for total, maxd, avgd, pers, pctc, span, uips, ipst, cst, ast in rows:
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
        ])
    X = np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)

    # sparsity of the churn features
    print("  Sparsity of the stability features (fraction exactly 0):")
    for i, nm in ((6, 'ip_stability'), (7, 'country_stability')):
        z = (X[:, i] == 0).mean()
        print(f"    {nm:22s} {z*100:5.1f}% zero   nonzero mean={X[X[:, i] > 0, i].mean():.3f}"
              if (X[:, i] > 0).any() else f"    {nm:22s} {z*100:5.1f}% zero")
    ast_arr = np.array([r[9] if r[9] is not None else 0.0 for r in rows], dtype=float)
    print(f"    {'asn_stability':22s} {(ast_arr == 0).mean()*100:5.1f}% zero  (dropped, shown for reference)")

    print(f"\n  {'feature':26s} {'mean':>11s} {'std':>11s} {'CV':>7s}")
    for i, nm in enumerate(PRUNED):
        c = X[:, i]
        cv = c.std() / abs(c.mean()) if c.mean() else 0
        print(f"  {nm:26s} {c.mean():>11.3f} {c.std():>11.3f} {cv:>7.3f}")

    Z = (X - X.mean(0)) / np.where(X.std(0) == 0, 1, X.std(0))
    C = np.corrcoef(Z, rowvar=False)

    print("\n  Remaining pairs with |r| > 0.70:")
    hits = [(C[i, j], PRUNED[i], PRUNED[j])
            for i in range(len(PRUNED)) for j in range(i + 1, len(PRUNED))
            if abs(C[i, j]) > 0.70]
    if hits:
        for r, a, b in sorted(hits, key=lambda t: -abs(t[0])):
            print(f"    r = {r:+.3f}   {a:26s} <-> {b}")
    else:
        print("    none")

    ev = np.clip(np.sort(np.linalg.eigvalsh(C))[::-1], 0, None)
    frac = ev / ev.sum()
    cum = np.cumsum(frac)
    print("\n  " + "-" * 60)
    print(f"  PC1 variance : {frac[0]*100:5.1f}%     (was 63.9% with 17 features)")
    print(f"  90% reached  : {int(np.searchsorted(cum, 0.90) + 1)} of {len(PRUNED)} components")
    print("  by component : " + ", ".join(f"{v*100:.0f}%" for v in frac))
    if frac[0] < 0.40:
        print("\n  OK -- no single direction dominates. Safe to cluster.")
    else:
        print("\n  !! still concentrated -- needs further pruning or whitening")


def main():
    con = duckdb.connect(DB_PATH, read_only=True)
    part_a(con)
    part_b(con)
    con.close()


if __name__ == "__main__":
    main()