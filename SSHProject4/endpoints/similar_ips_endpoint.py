"""
Similar IPs Endpoint - CLUSTERING-BASED
Finds IPs similar to a given target IP using pre-computed clusters
"""

from flask import jsonify, request
from utils.db import get_db
import numpy as np


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
            'similar_ips': similar_ips[:limit],
            'total_in_cluster': len(similar_ips)
        }
        
        conn.close()
        
        return jsonify(response)
    
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