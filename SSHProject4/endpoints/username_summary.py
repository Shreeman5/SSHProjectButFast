"""
Username Summary Endpoint
Returns comprehensive data for all usernames with discovery metrics
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
                s.country_count
            FROM username_stats s
            LEFT JOIN volatility_metrics vm ON s.username = vm.username
            LEFT JOIN last_7_days l7 ON s.username = l7.username
            ORDER BY s.total_attacks DESC
        """
        
        # Execute with parameters (repeat usernames for each IN clause)
        params = usernames + usernames + usernames  # 3 IN clauses
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
            'countries': row[11]
        } for row in result]
        
        return jsonify(data)