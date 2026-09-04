#!/usr/bin/env python3
"""
Regenerate cluster names WITHOUT re-clustering.

The first naming pass produced only 4 distinct names for 9 clusters, so the
label shown in the search panel would be identical for 82% of usernames.
Cluster assignments and features are untouched -- this only rewrites
profile_name and profile_description in username_cluster_profiles.

Run from the project root:  python3 update_cluster_names.py
Takes a couple of seconds.
"""

import duckdb
import sys

DB_PATH = './attack_data.db'


def volume_band(a):
    """Log-spaced. The real cluster averages run 16 -> 105,322, so coarse bands
    collapse genuinely different clusters together."""
    if a >= 50_000: return "Massive-Volume"
    if a >= 5_000:  return "High-Volume"
    if a >= 1_000:  return "Elevated-Volume"
    if a >= 500:    return "Moderate-Volume"
    if a >= 50:     return "Low-Volume"
    return "Minimal-Volume"


def sourcing_band(n):
    if n >= 2000: return "Botnet-Scale"
    if n >= 200:  return "Broadly-Sourced"
    if n >= 20:   return "Multi-Sourced"
    return "Narrowly-Sourced"


def intensity_band(per_ip):
    """
    Attacks per IP. The axis that separates a botnet spraying a username from a
    focused campaign hammering it from a handful of hosts.
    """
    if per_ip >= 100: return "Concentrated"
    if per_ip >= 10:  return "Moderate-Intensity"
    return "Diffuse"


def temporal_band(pers, span):
    """
    Persistence and span answer different questions -- "on how many days?" and
    "across how wide a window?" -- and clusters 1 and 8 differ almost entirely
    on span (32.0d vs 2.2d) at near-identical persistence. Naming on
    persistence alone merged 62% of all usernames into one label.
    """
    if pers > 60:  return "Persistent"      # active most days in the window
    if pers > 25:  return "Intermittent"    # active a substantial fraction
    if span >= 21: return "Long-Tail"       # sparse, but spread over weeks
    if span >= 7:  return "Recurring"       # sparse over a short window
    return "Short-Lived"                    # appeared and vanished


def churn_band(s):
    if s > 0.50: return "stable attacker set"
    if s > 0.15: return "rotating attacker set"
    return "volatile attacker set"


def burst_band(b):
    """Included in the description because for some cluster pairs it is the
    only thing that separates them."""
    if b > 5: return "bursty"
    if b > 2: return "variable"
    return "steady"


def build_name(p):
    (cid, size, total, pers, burst, uips, ipstab,
     cstab, per_ip, span) = p

    name = (f"{volume_band(total)} "
            f"{temporal_band(pers, span)} "
            f"{sourcing_band(uips)}")

    desc = (f"{churn_band(ipstab)}, {burst_band(burst)} · "
            f"~{total:,} attacks from ~{uips:,} IPs "
            f"({per_ip:,.0f}/IP) · "
            f"active {pers:.0f}% of days over ~{span:.0f}d")
    return name, desc


def main():
    con = duckdb.connect(DB_PATH)

    rows = con.execute("""
        SELECT cluster_id, cluster_size, avg_total_attacks, avg_persistence_pct,
               avg_burst_intensity, avg_unique_ips, avg_ip_stability,
               avg_country_stability, avg_attacks_per_ip, avg_activity_span
        FROM username_cluster_profiles
        ORDER BY cluster_id
    """).fetchall()

    if not rows:
        print("No rows in username_cluster_profiles. Run create_username_clusters.py first.")
        con.close()
        sys.exit(1)

    old = {r[0]: c for r, c in zip(rows, con.execute(
        "SELECT profile_name FROM username_cluster_profiles ORDER BY cluster_id"
    ).fetchall())}

    # ---- full stat table, so the naming choices are inspectable -------------
    print("=" * 108)
    print("CLUSTER STATS")
    print("=" * 108)
    print(f"{'id':>3} {'size':>7} {'attacks':>10} {'IPs':>7} {'per-IP':>9} "
          f"{'pers%':>7} {'burst':>7} {'ipStab':>7} {'ctryStab':>9} {'span':>6}")
    print("-" * 108)
    for r in rows:
        print(f"{r[0]:>3} {r[1]:>7,} {r[2]:>10,} {r[5]:>7,} {r[8]:>9,.1f} "
              f"{r[3]:>7.2f} {r[4]:>7.2f} {r[6]:>7.3f} {r[7]:>9.3f} {r[9]:>6.1f}")

    # ---- new names ---------------------------------------------------------
    named = [(r[0], *build_name(r)) for r in rows]

    counts = {}
    for _, n, _ in named:
        counts[n] = counts.get(n, 0) + 1
    dupes = {n for n, c in counts.items() if c > 1}

    print("\n" + "=" * 108)
    print("RENAMING")
    print("=" * 108)
    for cid, name, desc in named:
        mark = "  <-- STILL DUPLICATED" if name in dupes else ""
        print(f"\n  cluster {cid}")
        print(f"    was : {old[cid][0]}")
        print(f"    now : {name}{mark}")
        print(f"          {desc}")

    print("\n" + "-" * 108)
    print(f"  distinct names: {len(counts)} of {len(rows)} clusters")
    if dupes:
        print(f"  still colliding: {sorted(dupes)}")
        print("  (the description carries concrete numbers, so the panel stays distinguishable)")

    for cid, name, desc in named:
        con.execute(
            "UPDATE username_cluster_profiles SET profile_name = ?, profile_description = ? "
            "WHERE cluster_id = ?", [name, desc, cid]
        )

    con.close()
    print("\n  username_cluster_profiles updated. Cluster assignments untouched.")


if __name__ == "__main__":
    main()
