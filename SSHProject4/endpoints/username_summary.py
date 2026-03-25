"""
Username Summary Endpoint
Returns comprehensive data for all usernames with discovery metrics + stability metrics
OPTIMIZED: Only processes the usernames that will be returned
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_username_summary(app):
    """Register username summary endpoint for discovery tables"""
    
    @app.route('/api/username_count', methods=['GET'])
    def get_username_count():
        """Get total count of unique usernames (for debugging)"""
        start, end = parse_date_params()
        
        conn = get_db()
        
        query = f"""
            SELECT COUNT(DISTINCT username) as total_usernames
            FROM daily_username_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
        """
        
        result = conn.execute(query).fetchone()
        conn.close()
        
        total = result[0]
        print(f"[USERNAME_COUNT] Total unique usernames: {total:,}")
        
        return jsonify({
            'total_usernames': total,
            'date_range': {
                'start': start,
                'end': end
            }
        })
    
    @app.route('/api/username_summary', methods=['GET'])
    def get_username_summary():
        """Get comprehensive summary data for all usernames"""
        start, end = parse_date_params()
        limit = request.args.get('limit', type=int, default=1000)
        offset = request.args.get('offset', type=int, default=0)
        
        conn = get_db()
        
        # DEBUG: Get total count of unique usernames
        count_query = f"""
            SELECT COUNT(DISTINCT username) as total_usernames
            FROM daily_username_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
        """
        total_count = conn.execute(count_query).fetchone()[0]
        print(f"[USERNAME_SUMMARY] Total unique usernames in dataset: {total_count:,}")
        print(f"[USERNAME_SUMMARY] Requested limit={limit}, offset={offset}")
        print(f"[USERNAME_SUMMARY] Will return usernames {offset + 1} to {offset + limit}")
        
        # Step 1: Get the top N usernames by total attacks
        top_query = f"""
            SELECT username
            FROM daily_username_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
            GROUP BY username
            ORDER BY SUM(attacks) DESC
            LIMIT {limit}
            OFFSET {offset}
        """
        
        top_result = conn.execute(top_query).fetchall()
        print(f"[USERNAME_SUMMARY] Retrieved {len(top_result)} usernames from offset {offset}")
        
        if not top_result:
            conn.close()
            print(f"[USERNAME_SUMMARY] No usernames found at offset {offset}")
            return jsonify([])
        
        # Get list of usernames
        usernames = [row[0] for row in top_result]
        
        # Create placeholder string for parameterized query
        placeholders = ', '.join(['?' for _ in usernames])
        
        # Step 2: Calculate stats only for these usernames
        stats_query = f"""
            WITH username_stats AS (
                SELECT 
                    username,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    COUNT(DISTINCT date) as active_days,
                    MIN(date) as first_seen,
                    MAX(date) as last_seen,
                    MAX(attacks) as max_daily,
                    COUNT(DISTINCT country) as country_count
                FROM daily_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND username IN ({placeholders})
                GROUP BY username
            ),
            day_over_day AS (
                SELECT 
                    username,
                    attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date) as absolute_change,
                    CASE 
                        WHEN LAG(attacks) OVER (PARTITION BY username ORDER BY date) = 0 
                        THEN (attacks - 1.0) / 1.0 * 100
                        ELSE (attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date)) 
                             / LAG(attacks) OVER (PARTITION BY username ORDER BY date) * 100
                    END as pct_change
                FROM daily_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND username IN ({placeholders})
            ),
            volatility_metrics AS (
                SELECT 
                    username,
                    MAX(absolute_change) as max_absolute_change,
                    MAX(pct_change) as max_pct_change
                FROM day_over_day
                WHERE absolute_change IS NOT NULL
                GROUP BY username
            ),
            last_7_days AS (
                SELECT 
                    username,
                    SUM(attacks) as recent_attacks
                FROM daily_username_attacks
                WHERE date BETWEEN (DATE '{end}' - INTERVAL 6 DAY) AND DATE '{end}'
                  AND username IN ({placeholders})
                GROUP BY username
            ),
            sparkline_data AS (
                -- Get attack counts at 7-day intervals for sparkline
                SELECT 
                    username,
                    STRING_AGG(
                        CAST(total_attacks AS VARCHAR),
                        ','
                        ORDER BY week_num
                    ) as sparkline_values
                FROM (
                    SELECT 
                        username,
                        FLOOR((date - DATE '{start}') / 7) as week_num,
                        SUM(attacks) as total_attacks
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}'
                      AND username IN ({placeholders})
                    GROUP BY username, week_num
                ) intervals
                GROUP BY username
            )
            SELECT 
                s.username,
                s.total_attacks,
                ROUND(s.avg_daily, 2) as avg_daily,
                s.first_seen::VARCHAR as first_seen,
                s.last_seen::VARCHAR as last_seen,
                s.max_daily,
                COALESCE(ROUND(vm.max_absolute_change, 2), 0) as max_absolute_change,
                COALESCE(ROUND(vm.max_pct_change, 2), 0) as max_pct_change,
                ROUND((s.active_days::FLOAT / 69.0) * 100, 1) as persistence_pct,
                COALESCE(l7.recent_attacks, 0) as recent_attacks,
                s.active_days,
                s.country_count,
                CASE WHEN s.avg_daily > 0 THEN ROUND(s.max_daily::FLOAT / s.avg_daily, 1) ELSE 0 END as burst_intensity,
                sd.sparkline_values,
                
                -- Stability metrics from username_stability_metrics table
                sm.unique_countries,
                sm.unique_asns,
                sm.unique_ips,
                sm.country_concentration,
                sm.country_top1_pct,
                sm.asn_concentration,
                sm.asn_top1_pct,
                sm.ip_concentration,
                sm.ip_top1_pct,
                sm.country_stability,
                sm.asn_stability,
                sm.ip_stability,
                sm.country_rotation,
                sm.asn_rotation,
                sm.ip_rotation
                
            FROM username_stats s
            LEFT JOIN volatility_metrics vm ON s.username = vm.username
            LEFT JOIN last_7_days l7 ON s.username = l7.username
            LEFT JOIN sparkline_data sd ON s.username = sd.username
            LEFT JOIN username_stability_metrics sm ON s.username = sm.username
            ORDER BY s.total_attacks DESC
        """
        
        # Execute with parameters (repeat usernames for each IN clause - now 4 times)
        params = usernames + usernames + usernames + usernames  # 4 IN clauses
        result = conn.execute(stats_query, params).fetchall()
        conn.close()
        
        print(f"[USERNAME_SUMMARY] Processed {len(result)} usernames successfully")
        print(f"[USERNAME_SUMMARY] Progress: {offset + len(result):,} / {total_count:,} ({((offset + len(result)) / total_count * 100):.1f}%)")
        
        data = [{
            'username': row[0],
            'total_attacks': row[1],
            'avg_daily': row[2],
            'first_seen': row[3],
            'last_seen': row[4],
            'max_daily': row[5],
            'max_absolute_change': row[6],
            'max_pct_change': row[7],
            'persistence_pct': row[8],
            'recent_attacks': row[9],
            'active_days': row[10],
            'countries': row[11],
            'burst_intensity': row[12],
            'sparkline_values': row[13],
            
            # Stability metrics (14 new fields)
            'unique_countries': row[14],
            'unique_asns': row[15],
            'unique_ips': row[16],
            'country_concentration': row[17],
            'country_top1_pct': round(row[18], 1) if row[18] is not None else None,
            'asn_concentration': row[19],
            'asn_top1_pct': round(row[20], 1) if row[20] is not None else None,
            'ip_concentration': row[21],
            'ip_top1_pct': round(row[22], 1) if row[22] is not None else None,
            'country_stability': round(row[23], 3) if row[23] is not None else None,
            'asn_stability': round(row[24], 3) if row[24] is not None else None,
            'ip_stability': round(row[25], 3) if row[25] is not None else None,
            'country_rotation': round(row[26], 1) if row[26] is not None else None,
            'asn_rotation': round(row[27], 1) if row[27] is not None else None,
            'ip_rotation': round(row[28], 1) if row[28] is not None else None
        } for row in result]
        
        return jsonify(data)