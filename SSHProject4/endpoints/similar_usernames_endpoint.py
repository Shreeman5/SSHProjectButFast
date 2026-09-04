"""
Similar Usernames Endpoint - CLUSTERING-BASED
Finds usernames that are ATTACKED in a similar way to a target username.

Counterpart to similar_ips_endpoint.py. Register in app.py:

    from endpoints.similar_usernames_endpoint import register_similar_usernames
    register_similar_usernames(app)

Requires username_clusters and username_cluster_profiles, built by
summary_tables_code/create_username_clusters.py.

--------------------------------------------------------------------------------
DIFFERENCES FROM similar_ips_endpoint.py -- all deliberate
--------------------------------------------------------------------------------
1. CALIBRATED SIMILARITY SCALE. The IP endpoint uses `100 - (d/4.1)*100`,
   justified as sqrt(17). But for two independent standardised points
   E[||x-y||^2] = 2*17 = 34, so a typical distance is ~5.8 -- past 4.1, where
   everything clamps to 0. That is why a real IP search returns 8.2%, 4.6%,
   4.4%, then seventeen rows of 0%. MAX_DISTANCE here is measured, not derived.

2. TIE-BREAKING. Once scores clamp to 0 they all tie, and a stable sort then
   leaves whatever order the database returned -- which is why those seventeen
   0% IP rows come back in alphabetical order rather than by similarity. Ties
   here break on total_attacks so the ordering always means something.

3. DISPLAY METRICS FETCHED LAST. The IP endpoint aggregates its whole daily
   table for every member of the cluster on every request. daily_username_attacks
   is 15.6M rows and needs a two-level rollup, so that would be far worse here.
   Distances come from username_clusters alone (indexed, no aggregation), and
   only the ~20 survivors get the expensive query.

4. OUTLIER HONESTY. A username can sit far from its own centroid, in which case
   its "nearest" neighbours are not actually near. The response says so instead
   of presenting twenty rows that look like findings.

5. TWO-LEVEL AGGREGATION. daily_username_attacks is keyed
   (date, username, country, asn_name). Row-level AVG/MAX are fragment
   statistics, not daily ones -- off by ~1,680x for a username like 'root'.
--------------------------------------------------------------------------------
"""

from flask import jsonify, request
from utils.db import get_db
import numpy as np

TOTAL_DAYS = 69.0

# Nine normalised feature columns, in the order create_username_clusters.py
# wrote them. Order matters: distances are computed positionally.
FEATURE_COLS = [
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

# Measured, not derived. Step 7 of create_username_clusters.py sampled 10,775
# real within-cluster pairs: p50=2.043, p90=5.142, p99=6.968. Using p99 means
# ~1% of same-cluster pairs floor at 0% instead of most of them.
# Re-run the clustering script if the data changes; it prints an updated value.
MAX_DISTANCE = 6.97

# A target further than this from its own centroid is unusual for its cluster,
# so its nearest neighbours are not necessarily close. p95 of distance-to-
# centroid was 2.562 in the clustering run.
OUTLIER_DISTANCE = 2.56

# Below this, the best match is weak enough to be worth saying out loud.
WEAK_MATCH_SIMILARITY = 40.0


def _top_of_concentration(s):
    """'China (21.4%), United States (17.8%)' -> 'China'."""
    if not s:
        return None
    return str(s).split(',')[0].split('(')[0].strip() or None


def _ratio_within(a, b, lo=0.5, hi=2.0):
    """True when a and b are within a factor of two of each other."""
    if not a or not b:
        return False
    return lo <= (a / b) <= hi


def register_similar_usernames(app):
    """Register the similar-usernames endpoints."""

    @app.route('/api/find_similar_usernames', methods=['GET'])
    def find_similar_usernames():
        # '' is a real username in SSH logs, so test for None, not falsiness.
        target = request.args.get('username')
        limit = request.args.get('limit', type=int, default=20)

        if target is None:
            return jsonify({'error': 'Missing username parameter'}), 400

        limit = max(1, min(limit, 200))
        conn = get_db()
        n_feat = len(FEATURE_COLS)
        feat_sql = ', '.join(f'c.{c}' for c in FEATURE_COLS)

        # ------------------------------------------------------------------
        # 1. Target's cluster and feature vector
        # ------------------------------------------------------------------
        target_row = conn.execute(f"""
            SELECT
                c.cluster_id,
                c.distance_from_centroid,
                {feat_sql},
                p.profile_name,
                p.profile_description,
                p.cluster_size
            FROM username_clusters c
            JOIN username_cluster_profiles p ON c.cluster_id = p.cluster_id
            WHERE c.username = ?
        """, [target]).fetchone()

        if not target_row:
            # Distinguish "never seen" from "seen but too sparse to cluster".
            # A bare 404 for a username sitting in the ranked table right above
            # looks like a bug.
            seen = conn.execute("""
                SELECT COUNT(DISTINCT date), SUM(attacks)
                FROM daily_username_attacks WHERE username = ?
            """, [target]).fetchone()
            conn.close()

            if seen and seen[0]:
                return jsonify({
                    'error': f'"{target}" was seen on only {seen[0]} day '
                             f'({int(seen[1] or 0):,} attacks), which is too sparse '
                             f'to characterise.',
                    'reason': 'excluded_single_day',
                    'active_days': seen[0],
                    'detail': 'Behavioural clustering needs at least 2 active days, '
                              'because day-to-day attacker stability cannot be measured '
                              'from a single day. 46,935 of 97,517 usernames (48.1%) '
                              'fall into this category.'
                }), 404

            return jsonify({
                'error': f'Username "{target}" not found.',
                'reason': 'not_found'
            }), 404

        cluster_id = target_row[0]
        target_centroid_dist = float(target_row[1])
        target_vec = np.array(target_row[2:2 + n_feat], dtype=float)
        profile_name = target_row[2 + n_feat]
        profile_desc = target_row[3 + n_feat]
        cluster_size = target_row[4 + n_feat]

        # ------------------------------------------------------------------
        # 2. Cluster members -- features only, no aggregation
        # ------------------------------------------------------------------
        members = conn.execute(f"""
            SELECT c.username, {feat_sql}
            FROM username_clusters c
            WHERE c.cluster_id = ? AND c.username != ?
        """, [cluster_id, target]).fetchall()

        if not members:
            conn.close()
            return jsonify({
                'target_username': target,
                'cluster': {
                    'cluster_id': cluster_id,
                    'profile_name': profile_name,
                    'profile_description': profile_desc,
                    'cluster_size': cluster_size,
                    'distance_from_centroid': round(target_centroid_dist, 3),
                },
                'quality': {'note': 'This username is alone in its cluster.'},
                'similar_usernames': [],
                'total_in_cluster': 0,
            })

        names = [m[0] for m in members]
        M = np.array([m[1:1 + n_feat] for m in members], dtype=float)

        # Vectorised Euclidean distance across the whole cluster at once.
        dists = np.linalg.norm(M - target_vec, axis=1)
        sims = np.clip(100.0 - (dists / MAX_DISTANCE) * 100.0, 0.0, 100.0)

        # Take a generous slice, then re-sort with a real tie-break below.
        top_idx = np.argsort(-sims)[:max(limit * 3, limit)]
        shortlist = [(names[i], float(sims[i]), float(dists[i])) for i in top_idx]

        # ------------------------------------------------------------------
        # 3. Display metrics -- only for the shortlist, plus the target
        # ------------------------------------------------------------------
        wanted = [s[0] for s in shortlist] + [target]
        ph = ', '.join(['?'] * len(wanted))

        detail_rows = conn.execute(f"""
            WITH ud AS (
                -- Collapse the (country, asn_name) fragments to one row per
                -- username-day before any AVG or MAX.
                SELECT username, date, SUM(attacks) AS attacks
                FROM daily_username_attacks
                WHERE username IN ({ph})
                GROUP BY username, date
            ),
            agg AS (
                SELECT
                    username,
                    SUM(attacks)         AS total_attacks,
                    AVG(attacks)         AS avg_daily,
                    MAX(attacks)         AS max_daily,
                    COUNT(DISTINCT date) AS active_days,
                    MIN(date)            AS first_seen,
                    MAX(date)            AS last_seen
                FROM ud GROUP BY username
            )
            SELECT
                a.username, a.total_attacks, a.avg_daily, a.max_daily,
                a.active_days, a.first_seen::VARCHAR, a.last_seen::VARCHAR,
                sm.unique_ips, sm.unique_countries, sm.unique_asns,
                sm.ip_stability, sm.country_stability,
                sm.country_concentration, sm.ip_concentration
            FROM agg a
            LEFT JOIN username_stability_metrics sm ON a.username = sm.username
        """, wanted).fetchall()
        conn.close()

        detail = {r[0]: r for r in detail_rows}
        t = detail.get(target)

        t_total = float(t[1]) if t and t[1] else 0.0
        t_uips = float(t[7]) if t and t[7] else 0.0
        t_ipstab = float(t[10]) if t and t[10] is not None else 0.0
        t_country = _top_of_concentration(t[12]) if t else None
        t_pers = (t[4] / TOTAL_DAYS * 100) if t and t[4] else 0.0
        t_per_ip = (t_total / t_uips) if t_uips else 0.0

        # ------------------------------------------------------------------
        # 4. Build results
        # ------------------------------------------------------------------
        out = []
        for name, sim, dist in shortlist:
            d = detail.get(name)
            if not d:
                continue

            total = float(d[1]) if d[1] else 0.0
            avg_daily = float(d[2]) if d[2] else 0.0
            max_daily = float(d[3]) if d[3] else 0.0
            active_days = d[4] or 0
            uips = float(d[7]) if d[7] else 0.0
            ipstab = float(d[10]) if d[10] is not None else None
            cstab = float(d[11]) if d[11] is not None else None
            country = _top_of_concentration(d[12])
            per_ip = (total / uips) if uips else 0.0
            pers = active_days / TOTAL_DAYS * 100

            # Reasons compare TARGET against CANDIDATE. A property the candidate
            # merely happens to have is not a similarity.
            reasons = []

            if t_country and country and t_country == country:
                reasons.append(f"Same lead source ({country})")

            if _ratio_within(total, t_total):
                reasons.append("Comparable volume")

            if _ratio_within(uips, t_uips):
                if uips >= 2000:
                    reasons.append(f"Botnet-scale sourcing (~{int(uips):,} IPs)")
                elif uips < 20:
                    reasons.append(f"Narrow attacker base ({int(uips)} IPs)")
                else:
                    reasons.append(f"Similar attacker breadth (~{int(uips):,} IPs)")

            if ipstab is not None:
                if t_ipstab > 0.50 and ipstab > 0.50:
                    reasons.append("Stable attacker set")
                elif t_ipstab < 0.15 and ipstab < 0.15:
                    reasons.append("Volatile attacker set")

            if _ratio_within(per_ip, t_per_ip) and per_ip >= 100:
                reasons.append(f"Concentrated ({per_ip:,.0f} attacks/IP)")

            if pers > 60 and t_pers > 60:
                reasons.append(f"Persistent ({pers:.0f}% of days)")

            if not reasons:
                # Never leave the cell blank -- the IP panel does, and an empty
                # "Why Similar?" reads as a rendering fault.
                reasons.append("Same behavioural cluster")

            out.append({
                'username': name,
                'similarity': round(sim, 1),
                'distance': round(dist, 3),
                'total_attacks': int(total),
                'avg_daily': round(avg_daily, 2),
                'max_daily': int(max_daily),
                'active_days': active_days,
                'persistence_pct': round(pers, 1),
                'first_seen': d[5],
                'last_seen': d[6],
                'unique_ips': int(uips) if uips else None,
                'unique_countries': d[8],
                'unique_asns': d[9],
                'attacks_per_ip': round(per_ip, 1),
                'ip_stability': round(ipstab, 3) if ipstab is not None else None,
                'country_stability': round(cstab, 3) if cstab is not None else None,
                'top_country': country,
                'country_concentration': d[12],
                'ip_concentration': d[13],
                'reasons': reasons[:3],
            })

        # Ties on similarity break on volume, so equal scores never fall back to
        # whatever order the database happened to return.
        out.sort(key=lambda r: (-r['similarity'], -r['total_attacks']))
        out = out[:limit]

        # ------------------------------------------------------------------
        # 5. Honesty about match quality
        # ------------------------------------------------------------------
        best = out[0]['similarity'] if out else 0.0
        is_outlier = target_centroid_dist > OUTLIER_DISTANCE
        weak = best < WEAK_MATCH_SIMILARITY

        note = None
        if is_outlier and weak:
            note = (f'"{target}" sits unusually far from its cluster centre '
                    f'({target_centroid_dist:.2f}), and its closest match is only '
                    f'{best:.1f}%. Treat these as the least-dissimilar usernames '
                    f'in the cluster rather than as genuine matches.')
        elif is_outlier:
            note = (f'"{target}" sits unusually far from its cluster centre '
                    f'({target_centroid_dist:.2f}), so it is atypical for the '
                    f'"{profile_name}" profile.')
        elif weak:
            note = (f'Closest match is only {best:.1f}%. This username has no '
                    f'close behavioural neighbours.')

        return jsonify({
            'target_username': target,
            'cluster': {
                'cluster_id': cluster_id,
                'profile_name': profile_name,
                'profile_description': profile_desc,
                'cluster_size': cluster_size,
                'distance_from_centroid': round(target_centroid_dist, 3),
            },
            'quality': {
                'target_is_outlier': bool(is_outlier),
                'best_similarity': round(best, 1),
                'weak_matches': bool(weak),
                'note': note,
            },
            'similar_usernames': out,
            'total_in_cluster': len(members),
        })

    @app.route('/api/username_cluster_info/<int:cluster_id>', methods=['GET'])
    def get_username_cluster_info(cluster_id):
        """Profile plus the heaviest members of one cluster."""
        conn = get_db()

        p = conn.execute("""
            SELECT cluster_id, cluster_size, avg_total_attacks, avg_persistence_pct,
                   avg_burst_intensity, avg_unique_ips, avg_ip_stability,
                   avg_country_stability, avg_attacks_per_ip, avg_activity_span,
                   dominant_country, dominant_country_pct,
                   profile_name, profile_description
            FROM username_cluster_profiles
            WHERE cluster_id = ?
        """, [cluster_id]).fetchone()

        if not p:
            conn.close()
            return jsonify({'error': f'Cluster {cluster_id} not found'}), 404

        samples = conn.execute("""
            WITH ud AS (
                SELECT d.username, d.date, SUM(d.attacks) AS attacks
                FROM daily_username_attacks d
                JOIN username_clusters c ON d.username = c.username
                WHERE c.cluster_id = ?
                GROUP BY d.username, d.date
            )
            SELECT username, SUM(attacks) AS total
            FROM ud GROUP BY username
            ORDER BY total DESC
            LIMIT 10
        """, [cluster_id]).fetchall()
        conn.close()

        return jsonify({
            'cluster_id': p[0],
            'cluster_size': p[1],
            'avg_total_attacks': p[2],
            'avg_persistence_pct': p[3],
            'avg_burst_intensity': p[4],
            'avg_unique_ips': p[5],
            'avg_ip_stability': p[6],
            'avg_country_stability': p[7],
            'avg_attacks_per_ip': p[8],
            'avg_activity_span': p[9],
            'dominant_country': p[10],
            'dominant_country_pct': p[11],
            'profile_name': p[12],
            'profile_description': p[13],
            'sample_usernames': [
                {'username': r[0], 'total_attacks': int(r[1])} for r in samples
            ],
        })