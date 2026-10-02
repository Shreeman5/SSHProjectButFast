"""
Similar IPs Endpoint - CLUSTERING-BASED
Finds IPs similar to a given target IP using pre-computed clusters

Two kinds of similarity:

  * Behavioural (`similarity`): distance between the 17 clustering features,
    searched within the target's cluster. Unchanged.
  * Username (`username_similarity`): TF-IDF weighted cosine overlap of the
    usernames two IPs try (utils/username_similarity.py). Added as a column to
    the behavioural results, and searchable across ALL IPs via
    /api/find_ips_by_usernames -- which is how IPs from unrelated clusters,
    ASNs and countries that share a username list are found.
"""

from flask import jsonify, request
from utils.db import get_db
from utils import username_similarity as usim
import numpy as np

# The 17 clustering features, in ip_clusters column order.
FEATURE_COLS = [
    'f1_log_total_attacks', 'f2_log_avg_daily', 'f3_log_max_daily', 'f4_persistence_pct',
    'f5_burst_intensity', 'f6_log_max_abs_change', 'f7_max_pct_change',
    'f8_username_stability', 'f9_username_rotation', 'f10_log_unique_usernames',
    'f11_username_top1_pct', 'f12_trend_slope', 'f13_is_cloud_asn', 'f14_is_major_country',
    'f15_log_activity_span', 'f16_recency_ratio', 'f17_log_recent_attacks',
]

# Same scale as the behavioural score in find_similar_ips, so the two agree.
BEHAVIOUR_MAX_DISTANCE = 4.1

USERNAME_SEARCH_DEFAULT = 50
USERNAME_SEARCH_MAX = 200


def _behavioural_similarity(a, b):
    return round(max(0.0, 100 - (float(np.linalg.norm(a - b)) / BEHAVIOUR_MAX_DISTANCE) * 100), 1)


def register_similar_ips(app):
    """Register similar IPs endpoint"""
    
    @app.route('/api/find_similar_ips', methods=['GET'])
    def find_similar_ips():
        """Find IPs similar to the target IP"""
        target_ip = request.args.get('ip')
        limit = request.args.get('limit', type=int, default=20)
        
        if not target_ip:
            return jsonify({'error': 'Missing ip parameter'}), 400
        
        conn = get_db()
        
        # Step 1: Get target IP's cluster info and metadata
        target_query = """
            SELECT 
                c.cluster_id,
                c.distance_from_centroid,
                c.f1_log_total_attacks,
                c.f2_log_avg_daily,
                c.f3_log_max_daily,
                c.f4_persistence_pct,
                c.f5_burst_intensity,
                c.f6_log_max_abs_change,
                c.f7_max_pct_change,
                c.f8_username_stability,
                c.f9_username_rotation,
                c.f10_log_unique_usernames,
                c.f11_username_top1_pct,
                c.f12_trend_slope,
                c.f13_is_cloud_asn,
                c.f14_is_major_country,
                c.f15_log_activity_span,
                c.f16_recency_ratio,
                c.f17_log_recent_attacks,
                p.profile_name,
                p.profile_description,
                p.cluster_size,
                i.country,
                i.asn_name
            FROM ip_clusters c
            JOIN cluster_profiles p ON c.cluster_id = p.cluster_id
            LEFT JOIN (
                SELECT 
                    ip,
                    MODE() WITHIN GROUP (ORDER BY country) as country,
                    MODE() WITHIN GROUP (ORDER BY asn_name) as asn_name
                FROM daily_ip_attacks
                GROUP BY ip
            ) i ON c.ip = i.ip
            WHERE c.ip = ?
        """
        
        target_result = conn.execute(target_query, [target_ip]).fetchone()
        
        if not target_result:
            conn.close()
            return jsonify({'error': f'IP {target_ip} not found in clusters'}), 404
        
        cluster_id = target_result[0]
        target_country = target_result[22]
        target_asn = target_result[23]
        
        # Extract all 17 normalized features
        target_features = np.array([
            target_result[2],   # f1_log_total_attacks
            target_result[3],   # f2_log_avg_daily
            target_result[4],   # f3_log_max_daily
            target_result[5],   # f4_persistence_pct
            target_result[6],   # f5_burst_intensity
            target_result[7],   # f6_log_max_abs_change
            target_result[8],   # f7_max_pct_change
            target_result[9],   # f8_username_stability
            target_result[10],  # f9_username_rotation
            target_result[11],  # f10_log_unique_usernames
            target_result[12],  # f11_username_top1_pct
            target_result[13],  # f12_trend_slope
            target_result[14],  # f13_is_cloud_asn
            target_result[15],  # f14_is_major_country
            target_result[16],  # f15_log_activity_span
            target_result[17],  # f16_recency_ratio
            target_result[18]   # f17_log_recent_attacks
        ])
        
        # Step 2: Get all IPs in same cluster (excluding target)
        cluster_members_query = """
            SELECT 
                c.ip,
                c.distance_from_centroid,
                c.f1_log_total_attacks,
                c.f2_log_avg_daily,
                c.f3_log_max_daily,
                c.f4_persistence_pct,
                c.f5_burst_intensity,
                c.f6_log_max_abs_change,
                c.f7_max_pct_change,
                c.f8_username_stability,
                c.f9_username_rotation,
                c.f10_log_unique_usernames,
                c.f11_username_top1_pct,
                c.f12_trend_slope,
                c.f13_is_cloud_asn,
                c.f14_is_major_country,
                c.f15_log_activity_span,
                c.f16_recency_ratio,
                c.f17_log_recent_attacks,
                
                -- Get IP metrics for display
                i.total_attacks,
                i.avg_daily,
                i.persistence_pct,
                i.max_daily,
                i.country,
                i.asn_name,
                
                -- Stability metrics
                sm.unique_usernames,
                sm.username_stability,
                sm.username_concentration,
                
                -- Computed burst
                CASE WHEN i.avg_daily > 0 
                    THEN ROUND(i.max_daily::FLOAT / i.avg_daily, 1)
                    ELSE 0 
                END as burst_intensity
                
            FROM ip_clusters c
            JOIN (
                SELECT 
                    ip,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    MAX(attacks) as max_daily,
                    MODE() WITHIN GROUP (ORDER BY country) as country,
                    MODE() WITHIN GROUP (ORDER BY asn_name) as asn_name,
                    ROUND((COUNT(DISTINCT date)::FLOAT / 69.0) * 100, 1) as persistence_pct
                FROM daily_ip_attacks
                GROUP BY ip
            ) i ON c.ip = i.ip
            LEFT JOIN ip_stability_metrics sm ON c.ip = sm.ip
            WHERE c.cluster_id = ?
              AND c.ip != ?
        """
        
        members_result = conn.execute(cluster_members_query, [cluster_id, target_ip]).fetchall()
        
        # Step 3: Calculate similarity scores
        similar_ips = []
        
        for row in members_result:
            member_features = np.array([
                row[2],   # f1_log_total_attacks
                row[3],   # f2_log_avg_daily
                row[4],   # f3_log_max_daily
                row[5],   # f4_persistence_pct
                row[6],   # f5_burst_intensity
                row[7],   # f6_log_max_abs_change
                row[8],   # f7_max_pct_change
                row[9],   # f8_username_stability
                row[10],  # f9_username_rotation
                row[11],  # f10_log_unique_usernames
                row[12],  # f11_username_top1_pct
                row[13],  # f12_trend_slope
                row[14],  # f13_is_cloud_asn
                row[15],  # f14_is_major_country
                row[16],  # f15_log_activity_span
                row[17],  # f16_recency_ratio
                row[18]   # f17_log_recent_attacks
            ])
            
            # Euclidean distance in normalized feature space
            distance = np.linalg.norm(target_features - member_features)
            
            # Convert distance to similarity score (0-100)
            # Smaller distance = higher similarity
            # Max expected distance in 17D normalized space ≈ sqrt(17) ≈ 4.1
            similarity = max(0, 100 - (distance / 4.1) * 100)
            
            # Determine matching reasons (ONLY if they match target)
            reasons = []
            
            # Same country (only if matches target)
            if row[23] and target_country and row[23] == target_country:
                reasons.append(f"Same region")
            
            # Same ASN (only if matches target)
            if row[24] and target_asn and row[24] == target_asn:
                asn_short = row[24][:40] + '...' if len(row[24]) > 40 else row[24]
                reasons.append(f"Same ASN ({asn_short})")
            
            # Similar volume
            vol_ratio = row[19] / 1_000_000  # total_attacks in millions
            if vol_ratio > 1:
                reasons.append(f"High volume ({vol_ratio:.1f}M attacks)")
            
            # Similar targeting
            if row[26] and row[26] > 0.7:  # username_stability
                reasons.append(f"Focused targeting")
            elif row[26] and row[26] < 0.3:
                reasons.append(f"Exploratory targeting")
            
            # Similar persistence
            if row[21] and row[21] > 80:  # persistence_pct
                reasons.append(f"Persistent ({row[21]:.0f}% of days)")
            
            similar_ips.append({
                'ip': row[0],
                'similarity': round(similarity, 1),
                'total_attacks': row[19],
                'avg_daily': round(row[20], 2) if row[20] else 0,
                'persistence_pct': row[21],
                'burst_intensity': row[28],
                'country': row[23],
                'asn_name': row[24],
                'unique_usernames': row[25],
                'username_stability': round(row[26], 3) if row[26] else None,
                'username_concentration': row[27],
                'reasons': reasons[:3]  # Top 3 reasons
            })
        
        # Sort by similarity (highest first)
        similar_ips.sort(key=lambda x: x['similarity'], reverse=True)
        
        top = similar_ips[:limit]

        # Step 3b: Username similarity to the target, for the rows returned.
        # Display only; the behavioural ranking above is unchanged.
        username_ready = usim.tables_ready(conn)
        if username_ready:
            u_sims = usim.similarity_to(conn, target_ip, [r['ip'] for r in top])
            for r in top:
                r.update(u_sims[r['ip']])

        # The searched IP itself, shown as a pinned reference row above the results.
        t_total = conn.execute("SELECT SUM(attacks) FROM daily_ip_attacks WHERE IP = ?", [target_ip]).fetchone()[0]
        target_out = {
            'ip': target_ip,
            'country': target_country,
            'asn_name': target_asn,
            'cluster_id': cluster_id,
            'total_attacks': int(t_total) if t_total is not None else None,
        }
        if username_ready:
            t_prof = usim.target_profile(conn, target_ip)
            target_out['weighted_usernames'] = t_prof[1] if t_prof else 0
            target_out['distinctive_usernames'] = usim.distinctive_count(conn, target_ip)
            target_out.update(usim.own_usernames(conn, target_ip))

        # Step 4: Prepare response
        response = {
            'target_ip': target_ip,
            'cluster': {
                'cluster_id': cluster_id,
                'profile_name': target_result[19],
                'profile_description': target_result[20],
                'cluster_size': target_result[21],
                'distance_from_centroid': round(target_result[1], 3)
            },
            'similar_ips': top,
            'total_in_cluster': len(similar_ips),
            'target': target_out,
            'username_similarity_available': username_ready,
        }
        
        conn.close()
        
        return jsonify(response)
    
    @app.route('/api/find_ips_by_usernames', methods=['GET'])
    def find_ips_by_usernames():
        """IPs across ALL clusters whose username lists most resemble the target's."""
        target_ip = request.args.get('ip')
        limit = request.args.get('limit', type=int, default=USERNAME_SEARCH_DEFAULT)
        # On unless explicitly turned off: drop matches that share only common usernames.
        require_distinctive = request.args.get('require_distinctive', '1') not in ('0', 'false', 'no')
        if not target_ip:
            return jsonify({'error': 'Missing ip parameter'}), 400
        limit = max(1, min(limit, USERNAME_SEARCH_MAX))

        conn = get_db()
        if not usim.tables_ready(conn):
            conn.close()
            return jsonify({'error': usim.NOT_READY_MESSAGE, 'reason': 'not_built'}), 503

        found = usim.search(conn, target_ip, limit, require_distinctive)
        if found is None:
            conn.close()
            return jsonify({
                'error': f'IP {target_ip} has no distinctive usernames to compare.',
                'reason': 'no_usernames',
                'detail': 'Either it has no username data, or it only tried usernames '
                          'that every IP tries, which carry no weight.'
            }), 404

        ips = [f[0] for f in found]
        shared = usim.similarity_to(conn, target_ip, ips)
        everyone = ips + [target_ip]
        ph = ', '.join(['?'] * len(everyone))

        meta = {r[0]: r for r in conn.execute(f"""
            SELECT IP,
                   SUM(attacks) AS total_attacks,
                   MODE() WITHIN GROUP (ORDER BY country) AS country,
                   MODE() WITHIN GROUP (ORDER BY asn_name) AS asn_name
            FROM daily_ip_attacks
            WHERE IP IN ({ph})
            GROUP BY IP
        """, everyone).fetchall()}

        feats = {r[0]: (r[1], np.array(r[2:], dtype=float)) for r in conn.execute(f"""
            SELECT ip, cluster_id, {', '.join(FEATURE_COLS)}
            FROM ip_clusters WHERE ip IN ({ph})
        """, everyone).fetchall()}

        t_norm = usim.target_profile(conn, target_ip)
        t_distinctive = usim.distinctive_count(conn, target_ip)
        t_own = usim.own_usernames(conn, target_ip)
        conn.close()

        t_meta = meta.get(target_ip)
        t_country = t_meta[2] if t_meta else None
        t_asn = t_meta[3] if t_meta else None
        t_cluster, t_vec = feats.get(target_ip, (None, None))

        results = []
        for ip, u_sim, n_usernames in found:
            m = meta.get(ip)
            country = m[2] if m else None
            asn = m[3] if m else None
            cluster, vec = feats.get(ip, (None, None))
            results.append({
                'ip': ip,
                'username_similarity': u_sim,
                'shared_username_count': shared[ip]['shared_username_count'],
                'distinctive_shared_count': shared[ip]['distinctive_shared_count'],
                'shared_usernames': shared[ip]['shared_usernames'],
                'rare_shared_usernames': shared[ip]['rare_shared_usernames'],
                'weighted_usernames': n_usernames,
                'total_attacks': int(m[1]) if m else None,
                'country': country,
                'asn_name': asn,
                'cluster_id': cluster,
                # Behavioural similarity across clusters too, on the same scale
                # as find_similar_ips. High username + low behavioural overlap
                # is the interesting combination.
                'similarity': (_behavioural_similarity(t_vec, vec)
                               if t_vec is not None and vec is not None else None),
                'same_cluster': cluster is not None and cluster == t_cluster,
                'different_asn': bool(asn and t_asn and asn != t_asn),
                'different_country': bool(country and t_country and country != t_country),
            })

        return jsonify({
            'target_ip': target_ip,
            'target': {
                'ip': target_ip,
                'country': t_country,
                'asn_name': t_asn,
                'cluster_id': t_cluster,
                'total_attacks': int(t_meta[1]) if t_meta else None,
                'weighted_usernames': t_norm[1] if t_norm else 0,
                'distinctive_usernames': t_distinctive,
                **t_own,
            },
            'filters': {
                'require_distinctive': require_distinctive,
                'distinctive_max_share_pct': usim.DISTINCTIVE_MAX_SHARE * 100,
            },
            'results': results,
        })

    @app.route('/api/cluster_info/<int:cluster_id>', methods=['GET'])
    def get_cluster_info(cluster_id):
        """Get detailed information about a specific cluster"""
        
        conn = get_db()
        
        # Get cluster profile
        profile_query = """
            SELECT *
            FROM cluster_profiles
            WHERE cluster_id = ?
        """
        
        profile = conn.execute(profile_query, [cluster_id]).fetchone()
        
        if not profile:
            conn.close()
            return jsonify({'error': f'Cluster {cluster_id} not found'}), 404
        
        # Get sample IPs from cluster
        sample_query = """
            SELECT 
                c.ip,
                i.total_attacks,
                i.country,
                i.asn_name
            FROM ip_clusters c
            JOIN (
                SELECT 
                    ip,
                    SUM(attacks) as total_attacks,
                    MODE() WITHIN GROUP (ORDER BY country) as country,
                    MODE() WITHIN GROUP (ORDER BY asn_name) as asn_name
                FROM daily_ip_attacks
                GROUP BY ip
            ) i ON c.ip = i.ip
            WHERE c.cluster_id = ?
            ORDER BY i.total_attacks DESC
            LIMIT 10
        """
        
        samples = conn.execute(sample_query, [cluster_id]).fetchall()
        
        conn.close()
        
        response = {
            'cluster_id': cluster_id,
            'profile_name': profile[11],
            'profile_description': profile[12],
            'cluster_size': profile[1],
            'avg_total_attacks': profile[2],
            'avg_persistence_pct': profile[3],
            'avg_burst_intensity': profile[4],
            'avg_username_stability': profile[5],
            'dominant_country': profile[8],
            'dominant_asn': profile[10],
            'sample_ips': [
                {
                    'ip': row[0],
                    'total_attacks': row[1],
                    'country': row[2],
                    'asn_name': row[3]
                }
                for row in samples
            ]
        }
        
        return jsonify(response)